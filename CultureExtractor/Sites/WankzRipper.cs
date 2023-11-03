using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using System.Globalization;
using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

/**
 * Site notes:
 * - After a handful of downloads, the download speed was limited to 2 MB/s.
 **/
[PornSite("wankzvr")]
public class WankzRipper : ISubSiteScraper
{
    private readonly IDownloader _downloader;
    private IRepository _repository;

    public WankzRipper(IDownloader downloader, IRepository repository)
    {
        _downloader = downloader;
        _repository = repository;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var loginLink = page.GetByRole(AriaRole.Banner).GetByRole(AriaRole.Link, new() { Name = "Log In" });
        if (await loginLink.IsVisibleAsync())
        {
            await page.GetByRole(AriaRole.Banner).GetByRole(AriaRole.Link, new() { Name = "Log In" })
                .ClickAsync();

            await page.GetByRole(AriaRole.Textbox, new() { Name = "Username" }).FillAsync(site.Username);
            await page.GetByLabel("Password").FillAsync(site.Password);

            await page.GetByRole(AriaRole.Button, new() { Name = "Log In" }).ClickAsync();
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator("ul.navbar-nav > li.nav-item > a.nav-link").Nth(0).ClickAsync();
        await page.WaitForLoadStateAsync();

        var lastPageElement = await page.QuerySelectorAsync("ul.pagination li.page-item div.dropdown div.dropdown-menu a:last-of-type");
        var lastPage = await lastPageElement.TextContentAsync();

        return int.Parse(lastPage);
    }

    public async Task DownloadAdditionalFilesAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene, IReadOnlyList<IRequest> requests)
    {
        var previewElement = await scenePage.Locator("dl8-video").ElementHandleAsync();
        var url = await previewElement.GetAttributeAsync("poster");
        var fullUrl = $"https:{url}";
        
        var userAgent = await scenePage.EvaluateAsync<string>("() => navigator.userAgent");
        var cookieString = await scenePage.EvaluateAsync<string>("() => document.cookie");

        var headers = new Dictionary<HttpRequestHeader, string>
        {
            { HttpRequestHeader.Referer, scenePage.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };
        
        await _downloader.DownloadSceneImageAsync(scene, fullUrl, scenePage.Url, headers);
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var sceneHandles = await page.Locator("div.scene").ElementHandlesAsync();

        var indexScenes = new List<IndexScene>();
        foreach (var sceneHandle in sceneHandles.Reverse())
        {
            var sceneIdAndUrl = await GetSceneIdAsync(site, sceneHandle);
            indexScenes.Add(new IndexScene(null, sceneIdAndUrl.Id, sceneIdAndUrl.Url, sceneHandle));
        }

        return indexScenes.AsReadOnly();
    }

    public async Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        // read attribute data-id
        var sceneId = await currentScene.GetAttributeAsync("data-id");
        
        var aElement = await currentScene.QuerySelectorAsync("a.thumbnail__link");
        var url = await aElement.GetAttributeAsync("href");

        return new SceneIdAndUrl(sceneId, url);
    }

    public async Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response)
    {
        return null;
    }

    public async Task<Scene> ScrapeSceneAsync(Guid sceneUuid, Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var releaseDateElement = await page.QuerySelectorAsync("meta[property='video:release_date']");
        string releaseDateRaw = await releaseDateElement.GetAttributeAsync("content");
        DateOnly releaseDate = DateOnly.ParseExact(releaseDateRaw, "yyyy-MM-dd", CultureInfo.InvariantCulture);

        var durationElement = await page.QuerySelectorAsync("meta[property='video:duration']");
        var durationRaw = await durationElement.GetAttributeAsync("content");
        var durationSeconds = int.Parse(durationRaw);
        var duration = TimeSpan.FromSeconds(durationSeconds);

        var titleElement = await page.QuerySelectorAsync("meta[property='og:title']");
        var titleRaw = await titleElement.GetAttributeAsync("content");
        var title = titleRaw.Split("-")[0].Trim();

        // read multiple meta elements with video:actor property
        var performersRaw = await page.QuerySelectorAllAsync("meta[property='video:actor']");
        

        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersRaw)
        {
            var name = await performerElement.GetAttributeAsync("content");
            var shortName = name.ToLower().Replace(" ", "-");
            performers.Add(new SitePerformer(shortName, name, $"/{shortName}"));
        }

        // read script element with type application/ld+json
        var scriptElement = await page.QuerySelectorAsync("script[type='application/ld+json']");
        var scriptRaw = await scriptElement.InnerTextAsync();
        var rootObject = JsonSerializer.Deserialize<RootObject>(scriptRaw);

        string description = rootObject.description;

        var tags = new List<SiteTag>();
        foreach (var tag in rootObject.keywords.Split(", "))
        {
            var tagId = tag.Replace(" ", "-").ToLower();
            var tagUrl = $"/{tagId}";
            tags.Add(new SiteTag(tagId, tag, tagUrl));
        }
       
        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
            sceneUuid,
            site,
            subSite,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            "{}",
            DateTime.Now);
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        var cookieString = await page.EvaluateAsync<string>("() => document.cookie");
        
        var headers = new Dictionary<HttpRequestHeader, string>
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };
        
        return await _downloader.DownloadSceneDirectAsync(scene, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        await page.Locator("a").Filter(new() { HasTextRegex = new Regex("^Download$") }).ClickAsync();

        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        var downloadCategories = await page.QuerySelectorAllAsync("div.accordion");
        foreach (var downloadCategory in downloadCategories)
        {
            var heading = await downloadCategory.QuerySelectorAsync("div.accordion__heading h6");
            var headingText = await heading.TextContentAsync();
            
            var downloads = await downloadCategory.QuerySelectorAllAsync("div.accordion__content");
            foreach (var download in downloads)
            {
                var descriptionElement = await download.QuerySelectorAsync("div.text-lightest");
                var description = await descriptionElement.TextContentAsync();
                
                var specs = await download.QuerySelectorAllAsync("div.accordion__group-specs span");
                var codec = await specs[0].TextContentAsync();
                var sizeRaw = await specs[1].TextContentAsync();
                var size = HumanParser.ParseFileSizeMaybe(sizeRaw).IsSome(out var fileSizeValue) ? fileSizeValue : -1;
                
                var resolutionHeightRaw = description.Split(" ")[1];               
                var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionHeightRaw);

                // The class name has a typo in the original HTML code.
                var downloadLinks = await download.QuerySelectorAllAsync("div.accodion__right-content a");
                var downloadLink = downloadLinks.First(f => f.TextContentAsync().Result.Contains("Primary"));
                var url = await downloadLink.GetAttributeAsync("href");

                availableDownloads.Add(
                    new DownloadDetailsAndElementHandle(
                        new DownloadOption(
                            $"{headingText} {description}",
                            -1,
                            resolutionHeight,
                            size,
                            -1,
                            codec,
                            "https://www.wankzvr.com" + url),
                        downloadLink));
            }
        }
        
        return availableDownloads
            .OrderByDescending(d => d.DownloadOption.Codec)
            .ThenByDescending(d => d.DownloadOption.FileSize).ToList();
    }

    public async Task<IReadOnlyList<SubSite>> GetSubSitesAsync(Site site, IPage page)
    {
        await page.GotoAsync("/");
        await Task.Delay(5000);
        
        var existingSubSites = await _repository.GetSubSitesAsync(site.Uuid);
        
        var svgIconPremiumElements = await page.QuerySelectorAllAsync("svg.icon.premium");
        var linksWithSvgIconPremium = new List<IElementHandle>();
        
        foreach (var svgIconPremiumElement in svgIconPremiumElements)
        {
            var parentLink = await svgIconPremiumElement.EvaluateHandleAsync("element => element.parentNode");
            if (parentLink != null)
            {
                linksWithSvgIconPremium.Add(parentLink.AsElement());
            }
        }

        // Output the valid links
        var subSites = new List<SubSite>();
        foreach (var link in linksWithSvgIconPremium)
        {
            var href = await link.GetAttributeAsync("href");
            var shortName = href.Substring(1);
            
            var name = await link.TextContentAsync();
            var uuid = existingSubSites.FirstOrDefault(s => s.ShortName == shortName)?.Uuid ?? UuidGenerator.Generate();
            subSites.Add(new SubSite(uuid, shortName, name, site));
        }

        return subSites;
    }

    public async Task<int> NavigateToSubSiteAndReturnPageCountAsync(Site site, SubSite subSite, IPage page)
    {
        // o=d stands for order=date
        await page.GotoAsync($"/{subSite.ShortName}?o=d");

        var pageLinkHandles = await page.QuerySelectorAllAsync("div.pagination a.pagination__page:not(.next)");
        if (pageLinkHandles.Count == 0)
        {
            throw new InvalidOperationException($"Could not find page links for subsite {subSite.Name}.");
        }

        var lastPageLinkHandle = pageLinkHandles.Last();
        var lastPageLinkText = await lastPageLinkHandle.TextContentAsync();
        return int.Parse(lastPageLinkText);
    }

    public async Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/{subSite.ShortName}?o=d&p={pageNumber}");
        await Task.Delay(1000);
    }
    
    public record RootObject(
        string _context,
        string _type,
        string name,
        string description,
        string duration,
        string thumbnailUrl,
        string embedUrl,
        string contentUrl,
        string uploadDate,
        string keywords,
        InteractionStatistic[] interactionStatistic,
        Author author,
        Actor[] actor
    );

    public record InteractionStatistic(
        string _type,
        string interactionType,
        int userInteractionCount
    );

    public record Author(
        string _type,
        string name
    );

    public record Actor(
        string _id,
        string name
    );
}
