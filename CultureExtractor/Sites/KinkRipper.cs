using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

/**
 * Site notes:
 * - Does not support guest mode fully. At least durations will be currently be based on trailers and not the full video.
 **/
[PornSite("kink")]
public class KinkRipper : ISiteScraper, ISubSiteScraper
{
    private readonly IDownloader _downloader;
    private readonly IRepository _repository;

    public KinkRipper(IDownloader downloader, IRepository repository)
    {
        _downloader = downloader;
        _repository = repository;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var acceptRecommendSettingsButton = page.GetByRole(AriaRole.Button, new() { NameString = "Accept Recommended Settings" });
        if (await acceptRecommendSettingsButton.IsVisibleAsync())
        {
            await acceptRecommendSettingsButton.ClickAsync();
        }

        var enterKinkButton = page.GetByRole(AriaRole.Button, new() { NameString = "Enter Kink" });
        if (await enterKinkButton.IsVisibleAsync())
        {
            await enterKinkButton.ClickAsync();
        }

        var logInLink = page.GetByRole(AriaRole.Menuitem, new() { NameString = "Log In" });
        if (await logInLink.IsVisibleAsync())
        {
            await logInLink.ClickAsync();

            var usernameInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Username or Email" });
            if (await usernameInput.IsVisibleAsync())
            {
                await usernameInput.ClickAsync();
                await usernameInput.FillAsync(site.Username);

                var passwordInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Password" });
                await passwordInput.ClickAsync();
                await passwordInput.FillAsync(site.Password);

                await page.GetByRole(AriaRole.Button, new() { NameString = "log in" }).ClickAsync();
                await page.WaitForLoadStateAsync();

                await Task.Delay(5000);
            }
        }
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator("ul.navbar-nav > li.nav-item > a.nav-link").Nth(0).ClickAsync();
        await page.WaitForLoadStateAsync();

        var lastPageElement = await page.QuerySelectorAsync("ul.pagination li.page-item div.dropdown div.dropdown-menu a:last-of-type");
        var lastPage = await lastPageElement.TextContentAsync();

        return int.Parse(lastPage);
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, subSite, pageNumber);
        
        var sceneHandles = await page.Locator("div.shoot-card").ElementHandlesAsync();

        var indexScenes = new List<ListedRelease>();
        foreach (var sceneHandle in sceneHandles.Reverse())
        {
            var sceneIdAndUrl = await GetSceneIdAsync(sceneHandle);
            indexScenes.Add(new ListedRelease(null, sceneIdAndUrl.Id, sceneIdAndUrl.Url, sceneHandle));
        }

        return indexScenes.AsReadOnly();
    }

    private static async Task GoToPageAsync(IPage page, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/search?type=shoots&channelIds={subSite.ShortName.Replace("-", "")}&sort=published&page={pageNumber}");
        await Task.Delay(1000);
    }

    private static async Task<SceneIdAndUrl> GetSceneIdAsync(IElementHandle currentScene)
    {
        var aElement = await currentScene.QuerySelectorAsync("a.shoot-link");
        var url = await aElement.GetAttributeAsync("href");

        var shortName = url.Replace("/shoot/", "");

        return new SceneIdAndUrl(shortName, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        if (await page.Locator("div.four-oh-four h1").IsVisibleAsync())
        {
            Log.Warning("Scene page returns 404 even though scene has been listed on index page.");
            return null;
        }

        // fix this:
        var releaseDateElement = await page.QuerySelectorAsync("span.shoot-date");
        string releaseDateRaw = await releaseDateElement.TextContentAsync();
        DateOnly releaseDate = DateOnly.Parse(releaseDateRaw);

        var durationElement = await page.QuerySelectorAsync("span.vjs-duration-display");
        var durationRaw = await durationElement.TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performerContainer = page.Locator("span.names");

        var performers = new List<SitePerformer>();
        var performersRaw = await page.QuerySelectorAllAsync("span.names a");

        foreach (var performerElement in performersRaw)
        {
            var performerUrl = await performerElement.GetAttributeAsync("href");
            var nameRaw = await performerElement.TextContentAsync();
            var name = nameRaw.Trim().Replace(",", "");

            // parse number 5235 from url like /model/5235/Princess-Donna-Dolore
            var shortName = performerUrl.Split("/").Reverse().Skip(1).First();

            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        var descriptionRaw = await page.Locator("span.description-text").TextContentAsync();
        string description = descriptionRaw.Trim();

        var tagElements = await page.QuerySelectorAllAsync("p.tag-list a.tag");
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Replace("/studios/videos?niche=", "");
            var tagNameRaw = await tagElement.TextContentAsync();
            var tagName = tagNameRaw.Replace("\n", "").Trim();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        string directorName = null;
        if (await page.Locator("span.director-name").IsVisibleAsync())
        {
            directorName = await page.Locator("span.director-name").TextContentAsync();
        }

        string directorUrl = null;
        if (await page.Locator("span.director-name a").IsVisibleAsync())
        {
            directorUrl = await page.Locator("span.director-name a").GetAttributeAsync("href");
        }

        var metadata = new { director = new { name = directorName, url = directorUrl } };
        var metadataJson = JsonSerializer.Serialize(metadata);

        var scene = new Release(
            releaseUuid,
            site,
            subSite,
            releaseDate,
            releaseShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            metadataJson,
            DateTime.Now);
        
        var previewElement = await page.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var originalImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");
        var fullSizeCandidateImageUrl = Regex.Replace(originalImageUrl, @"w=\d+", "");

        try
        {
            await _downloader.DownloadSceneImageAsync(scene, fullSizeCandidateImageUrl, scene.Url);
        }
        catch (WebException)
        {
            await _downloader.DownloadSceneImageAsync(scene, originalImageUrl, scene.Url);
        }
        
        return scene;
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
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

        var suggestedFilename = selectedDownload.DownloadOption.Url.Substring(selectedDownload.DownloadOption.Url.LastIndexOf("/") + 1);
        suggestedFilename = suggestedFilename.Substring(0, suggestedFilename.IndexOf("?"));
        var suffix = Path.GetExtension(suggestedFilename);
        var name = ReleaseNamer.Name(release, suffix);

        return await _downloader.DownloadSceneDirectAsync(release, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url, fileName: name);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadLinks = await page.QuerySelectorAllAsync("ul.full-movie li a");
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", " ").Trim();

            var resolutionHeight = HumanParser.ParseResolutionHeight(description);

            var url = await downloadLink.GetAttributeAsync("href");

            if (string.IsNullOrWhiteSpace(url))
            {
                continue;
            }

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        -1,
                        resolutionHeight,
                        -1,
                        -1,
                        string.Empty,
                        url),
                    downloadLink));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.ResolutionHeight).ToList();
    }

    public async Task<IReadOnlyList<SubSite>> GetSubSitesAsync(Site site, IPage page)
    {
        await page.GotoAsync("/channels");

        await page.GetByRole(AriaRole.Heading, new() { NameString = "Channel Type" }).ClickAsync();
        await page.GetByLabel("Kink Originals").CheckAsync();

        await page.Locator("#searchDropdown").SelectOptionAsync(new[] { "alphabetical" });

        var existingSubSites = await _repository.GetSubSitesAsync(site.Uuid);
        
        var channelHandles = await page.Locator("div.channel-tile").ElementHandlesAsync();
        List<SubSite> subSites = new List<SubSite>();
        foreach (var channelHandle in channelHandles)
        {
            // get the <a> element inside the current studio container
            var aElementHandle = await channelHandle.QuerySelectorAsync("a");
            if (aElementHandle == null)
            {
                continue;
            }

            // These require separate subscription.
            var exclusiveTag = await channelHandle.QuerySelectorAsync("span.kink-tag__exclusive");
            if (exclusiveTag != null)
            {
                continue;
            }

            // get the href attribute of the <a> element
            var hrefProperty = await aElementHandle.GetPropertyAsync("href");
            var hrefValue = await hrefProperty.JsonValueAsync<string>();

            // extract the subsite URL and site name from the href value
            var subsiteUrl = hrefValue;
            if (subsiteUrl.StartsWith(site.Url))
            {
                subsiteUrl = subsiteUrl.Substring(site.Url.Length);
            }

            var siteName = subsiteUrl.Replace("/channel/", "");

            var h3Handle = await channelHandle.QuerySelectorAsync("h3");
            var name = await h3Handle.TextContentAsync();

            var uuid = existingSubSites.FirstOrDefault(s => s.ShortName == siteName)?.Uuid ?? UuidGenerator.Generate();
            subSites.Add(new SubSite(uuid, siteName, name, site));
        }

        var uniqueSubSites = subSites
            .GroupBy(s => s.Name)
            .Select(g => g.First())
            .OrderBy(s => s.Name)
            .ToList();

        return uniqueSubSites.AsReadOnly();
    }

    public async Task<int> NavigateToSubSiteAndReturnPageCountAsync(Site site, SubSite subSite, IPage page)
    {
        await page.GotoAsync($"/channel/{subSite.ShortName}");
        await page.GetByRole(AriaRole.Heading, new() { NameString = "Recently Added\nview all" }).GetByRole(AriaRole.Link, new()
        {
            NameString = "view all"
        }).ClickAsync();
        
        var pageLinkHandles = await page.QuerySelectorAllAsync("nav.paginated-nav ul li:not(.disabled) a");
        if (pageLinkHandles.Count == 0)
        {
            throw new InvalidOperationException($"Could not find page links for subsite {subSite.Name}.");
        }

        // take second to last page link, because the last one is "next"
        var lastPageLinkHandle = pageLinkHandles[pageLinkHandles.Count - 2];
        var lastPageLinkText = await lastPageLinkHandle.TextContentAsync();
        return int.Parse(lastPageLinkText);
    }
}
