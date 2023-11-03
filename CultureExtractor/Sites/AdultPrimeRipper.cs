using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Globalization;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[PornSite("adultprime")]
public class AdultPrimeRipper : ISiteScraper, ISubSiteScraper
{
    private readonly IDownloader _downloader;

    public AdultPrimeRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var enterAdultPrimeLink = page.GetByRole(AriaRole.Link, new() { NameString = "Enter AdultPrime" });
        if (await enterAdultPrimeLink.IsVisibleAsync())
        {
            await enterAdultPrimeLink.ClickAsync();
            await Task.Delay(5000);
        }

        var loginLink = page.GetByRole(AriaRole.Link, new() { NameString = "LOG IN" });
        if (await loginLink.IsVisibleAsync())
        {
            await loginLink.ClickAsync();

            var usernameInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Email" });
            if (await usernameInput.IsVisibleAsync())
            {
                await usernameInput.ClickAsync();
                await usernameInput.FillAsync(site.Username);

                var passwordInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Password" });
                await passwordInput.ClickAsync();
                await passwordInput.FillAsync(site.Password);

                Log.Warning("CAPTCHA required! Enter manually!");
                Console.ReadLine();

                await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
                await page.WaitForLoadStateAsync();

                await Task.Delay(5000);
            }
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
        var previewElement = await scenePage.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");

        await _downloader.DownloadSceneImageAsync(scene, backgroundImageUrl, scene.Url);
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var sceneHandles = await page.Locator("div.row.portal-grid div.portal-video-wrapper").ElementHandlesAsync();

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
        var overlayElement = await currentScene.QuerySelectorAsync("div.overlay");
        var aElement = await overlayElement.QuerySelectorAsync("a");
        var url = await aElement.GetAttributeAsync("href");

        var shortName = await overlayElement.GetAttributeAsync("data-id");

        return new SceneIdAndUrl(shortName, url);
    }

    public async Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response)
    {
        if (response.Url == "https://site-api.project1service.com/v2/releases/" + sceneShortName)
        {
            var bodyBuffer = await response.BodyAsync();
            var body = System.Text.Encoding.UTF8.GetString(bodyBuffer);
            return new CapturedResponse(Enum.GetName(AdultTimeRequestType.SceneMetadata)!, response);
        }

        return null;
    }

    public async Task<Scene> ScrapeSceneAsync(Guid sceneUuid, Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var releaseDateElement = await page.QuerySelectorAsync("p.update-info-line:nth-of-type(1) i.fa-calendar + b");
        string releaseDateRaw = await releaseDateElement.TextContentAsync();
        DateOnly releaseDate = DateOnly.ParseExact(releaseDateRaw, "dd.MM.yyyy", CultureInfo.InvariantCulture);

        var durationElement = await page.QuerySelectorAsync("p.update-info-line:nth-of-type(1) i.fa-clock-o + b");
        var durationRaw = await durationElement.TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("h2.update-info-title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        IElementHandle performerContainer = null;
        ILocator performerContainerLocator = page.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Performer:" });
        ILocator performersContainerLocator = page.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Performers:" });
        if (await performerContainerLocator.IsVisibleAsync())
        {
            performerContainer = await performerContainerLocator.ElementHandleAsync();
        }
        else if (await performersContainerLocator.IsVisibleAsync())
        {
            performerContainer = await performersContainerLocator.ElementHandleAsync();
        }

        var performers = new List<SitePerformer>();
        if (performerContainer != null)
        {
            var performersRaw = await performerContainer.QuerySelectorAllAsync("a");

            foreach (var performerElement in performersRaw)
            {
                var performerUrl = await performerElement.GetAttributeAsync("href");
                var nameRaw = await performerElement.TextContentAsync();
                var name = nameRaw.Trim();
                var shortName = name.Replace(" ", "+");
                performers.Add(new SitePerformer(shortName, name, performerUrl));
            }
        }

        var descriptionRaw = await page.Locator("p.ap-limited-description-text").TextContentAsync();
        string description = descriptionRaw.Trim();

        var tagsContainer = await page.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Niches:" }).ElementHandleAsync();
        var tagElements = await tagsContainer.QuerySelectorAllAsync("a");
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

        return await _downloader.DownloadSceneAsync(scene, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            await selectedDownload.ElementHandle.ClickAsync();
        });
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadIcon = await page.Locator("i.fa-download").ElementHandleAsync();
        var downloadContainer = await downloadIcon.EvaluateHandleAsync("element => element.parentNode");
        var downloadLinks = await downloadContainer.AsElement().QuerySelectorAllAsync("a");
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", " ").Trim();

            var resolutionHeight = HumanParser.ParseResolutionHeight(description);

            var url = await downloadLink.GetAttributeAsync("href");

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
        await page.GotoAsync("/studios");
        await Task.Delay(5000);

        var studioHandles = await page.Locator("div.studio-item-container").ElementHandlesAsync();
        List<SubSite> subSites = new List<SubSite>();
        foreach (var studioHandle in studioHandles)
        {
            // get the <a> element inside the current studio container
            var aElementHandle = await studioHandle.QuerySelectorAsync("a");
            if (aElementHandle == null)
            {
                continue;
            }

            var imgElementHandle = await studioHandle.QuerySelectorAsync(":scope > img");
            if (imgElementHandle != null)
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

            var siteName = subsiteUrl.Replace("/studios/studio/", "");

            subSites.Add(new SubSite(UuidGenerator.Generate(), siteName, siteName, site));
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
        await page.GotoAsync($"/studios/videos?website={subSite.Name}");

        var pageLinkHandles = await page.QuerySelectorAllAsync("div#api-pagination ul li:not(.disabled) a.page-link:not(.next)");
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
        await page.GotoAsync($"/studios/videos?website={subSite.Name}&page={pageNumber}");
        await Task.Delay(1000);
    }
}
