using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

[PornNetwork("kink")]
[PornSite("kink")]
public class KinkRipper : ISiteScraper, ISubSiteScraper
{
    private readonly IDownloader _downloader;

    public KinkRipper(IDownloader downloader)
    {
        _downloader = downloader;
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

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator("ul.navbar-nav > li.nav-item > a.nav-link").Nth(0).ClickAsync();
        await page.WaitForLoadStateAsync();

        var lastPageElement = await page.QuerySelectorAsync("ul.pagination li.page-item div.dropdown div.dropdown-menu a:last-of-type");
        var lastPage = await lastPageElement.TextContentAsync();

        return int.Parse(lastPage);
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene, IReadOnlyList<IRequest> requests)
    {
        var previewElement = await scenePage.Locator("div.vjs-poster").ElementHandleAsync();
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
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var sceneHandles = await page.Locator("div.shoot-card").ElementHandlesAsync();

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
        var aElement = await currentScene.QuerySelectorAsync("a.shoot-link");
        var url = await aElement.GetAttributeAsync("href");

        var shortName = url.Replace("/shoot/", "");

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

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
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

        return new Scene(
            null,
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
            metadataJson,
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

        var suggestedFilename = selectedDownload.DownloadOption.Url.Substring(selectedDownload.DownloadOption.Url.LastIndexOf("/") + 1);
        suggestedFilename = suggestedFilename.Substring(0, suggestedFilename.IndexOf("?"));
        var suffix = Path.GetExtension(suggestedFilename);

        var performerNames = scene.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1
            ? string.Join(", ", performerNames.SkipLast(1)) + " & " + performerNames.Last()
            : performerNames.FirstOrDefault();

        if (string.IsNullOrWhiteSpace(performersStr))
        {
            performersStr = "Unknown";
        }

        var subSiteName = scene.SubSite != null ? " - " + scene.SubSite.Name : "";

        var nameWithoutSuffix =
            string.Concat(
                Regex.Replace(
                    $"{scene.Site.Name}{subSiteName} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - #{scene.ShortName} - {scene.Name} - {performersStr}",
                    @"\s+",
                    " "
                ).Split(Path.GetInvalidFileNameChars()));

        var name = (nameWithoutSuffix + suffix).Length > 244
            ? nameWithoutSuffix[..(244 - suffix.Length - "...".Length)] + "..." + suffix
            : nameWithoutSuffix + suffix;

        return await _downloader.DownloadSceneDirectAsync(scene, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url, fileName: name);
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
        await page.ScreenshotAsync(new PageScreenshotOptions { Path = @"B:\kink_before_channels.png" });

        await page.GotoAsync("/channels");

        await page.GetByRole(AriaRole.Heading, new() { NameString = "Channel Type" }).ClickAsync();
        await page.GetByLabel("Kink Originals").CheckAsync();

        await page.Locator("#searchDropdown").SelectOptionAsync(new[] { "alphabetical" });

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

            subSites.Add(new SubSite(null, siteName, name, site));
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

    public async Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/search?type=shoots&channelIds={subSite.ShortName.Replace("-", "")}&sort=published&page={pageNumber}");
        await Task.Delay(1000);
    }
}
