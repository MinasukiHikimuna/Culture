using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using System.Text.RegularExpressions;
using CultureExtractor.Models;
using Serilog;
using Polly;

namespace CultureExtractor.Sites;

[Site("allfinegirls")]
[Site("wowgirls")]
[Site("wowporn")]
[Site("ultrafilms")]
public class WowNetworkRipper : ISiteScraper, IYieldingScraper
{
    private readonly ILegacyDownloader _legacyDownloader;
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;

    public WowNetworkRipper(ILegacyDownloader legacyDownloader, IPlaywrightFactory playwrightFactory, IRepository repository)
    {
        _legacyDownloader = legacyDownloader;
        _playwrightFactory = playwrightFactory;
        _repository = repository;
    }

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        await foreach (var release in ScrapeScenesAsync(site, page, scrapeOptions))
        {
            yield return release;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        await page.GotoAsync(site.Url + "/films/");
        await page.WaitForLoadStateAsync();

        await SetSiteFilter(site, page);
        var totalPages = await GetTotalPagesAsync(page);

        for (var pageNumber = 1; pageNumber <= totalPages; pageNumber++)
        {
            await GoToPageAsync(page, site, pageNumber);

            var releaseHandles = await page.Locator("section.cf_content > ul > li > div.content_item > a.icon").ElementHandlesAsync();

            var listedReleases = new List<ListedRelease>();
            foreach (var releaseHandle in releaseHandles)
            {
                var releaseIdAndUrl = await GetReleaseIdAsync(site, releaseHandle);
                listedReleases.Add(new ListedRelease(null, releaseIdAndUrl.Id, releaseIdAndUrl.Url, releaseHandle));
            }

            var listedReleasesDict = listedReleases
                .ToDictionary(
                    listedRelease => listedRelease.ShortName,
                    listedRelease => listedRelease);

            Log.Information($"Page {pageNumber}/{totalPages} contains {releaseHandles.Count} releases");

            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, listedReleasesDict.Keys.ToList());


            var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);

            var scenesToBeScraped = listedReleasesDict
                .Where(g => !existingReleasesDictionary.ContainsKey(g.Key) || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated)
                .Select(g => g.Value)
                .ToList();

            foreach (var sceneToBeScraped in scenesToBeScraped)
            {
                var releaseGuid = existingReleasesDictionary.TryGetValue(sceneToBeScraped.ShortName, out var existingRelease)
                    ? existingRelease.Uuid
                    : UuidGenerator.Generate();

                Release? scene = null;
                IPage? scenePage = null;

                try
                {
                    scenePage = await page.Context.NewPageAsync();
                    await scenePage.GotoAsync(sceneToBeScraped.Url);
                    scene = await ScrapeSceneAsync(scenePage, site, sceneToBeScraped, releaseGuid);
                }
                catch (Exception ex)
                {
                    Log.Error(ex, $"Failed to scrape scene {sceneToBeScraped.Url}");
                }
                finally
                {
                    scenePage?.CloseAsync();
                }

                if (scene != null)
                {
                    yield return scene;
                }
            }
        }
    }

    private async Task<Release> ScrapeSceneAsync(IPage scenePage, Site site, ListedRelease listedRelease, Guid releaseGuid)
    {
        await scenePage.WaitForLoadStateAsync();

        var releaseDate = await ScrapeReleaseDateAsync(scenePage);
        var duration = await ScrapeDurationAsync(scenePage);
        var description = await ScrapeDescriptionAsync(scenePage);
        var title = await ScrapeTitleAsync(scenePage);
        var performers = await ScrapePerformersAsync(scenePage);
        var tags = await ScrapeTagsAsync(scenePage);
        var availableVideoFiles = await ParseAvailableDownloadsAsync(scenePage);

        var previewElement = await scenePage.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "").Replace(" background-size: cover;", "");
        var availableImageFile = new AvailableImageFile("image", "scene", "preview", backgroundImageUrl, null, null, null);

        var scene = new Release(
            releaseGuid,
            site,
            null,
            releaseDate,
            listedRelease.ShortName,
            title,
            listedRelease.Url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            availableVideoFiles.Concat(new List<IAvailableFile> { availableImageFile }).ToList(),
            "{}",
            DateTime.Now);

        return scene;
    }

    public IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        throw new NotImplementedException();
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var signInButton = page.GetByRole(AriaRole.Link, new() { NameString = "Sign in" });
        var emailInput = page.GetByPlaceholder("E-Mail");
        var passwordInput = page.GetByPlaceholder("Password");
        var getInsideButton = page.GetByText("Get Inside");

        if (await signInButton.IsVisibleAsync())
        {
            await signInButton.ClickAsync();
            await page.WaitForLoadStateAsync();
        }

        if (await getInsideButton.IsVisibleAsync())
        {
            await emailInput.FillAsync(site.Username);
            await passwordInput.FillAsync(site.Password);
            await getInsideButton.ClickAsync();
            await page.WaitForLoadStateAsync();
        }
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = "Films" }).Nth(1).ClickAsync();
        await page.WaitForLoadStateAsync();

        while ((await page.Locator(".cf_s_site").ElementHandlesAsync()).Count() > 0)
        {
            var elementHandles = await page.Locator(".cf_s_site").ElementHandlesAsync();
            var elementHandle = elementHandles[0];

            await elementHandle.ClickAsync();
            await elementHandle.IsHiddenAsync();
            await page.WaitForLoadStateAsync();
            await Task.Delay(5000);
        }

        var siteName = site.ShortName switch
        {
            "allfinegirls" => "All Fine Girls",
            "wowgirls" => "Wow Girls",
            "wowporn" => "Wow Porn",
            _ => string.Empty
        };

        if (!string.IsNullOrWhiteSpace(siteName))
        {
            await page.GetByRole(AriaRole.Complementary).GetByText(siteName).ClickAsync();
            await page.WaitForSelectorAsync(".cf_s_site");
            await page.WaitForLoadStateAsync();
        }

        var totalPagesStr = await page.Locator("div.pages > span").Last.TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);
        return totalPages;
    }

    private async Task SetSiteFilter(Site site, IPage page)
    {
        // Unselect existing site filters
        while ((await page.Locator(".cf_s_site").ElementHandlesAsync()).Count > 0)
        {
            var elementHandles = await page.Locator(".cf_s_site").ElementHandlesAsync();
            var elementHandle = elementHandles[0];

            await elementHandle.ClickAsync();
            await elementHandle.IsHiddenAsync();
            await page.WaitForLoadStateAsync();
            await Task.Delay(5000);
        }

        var siteName = site.ShortName switch
        {
            "allfinegirls" => "All Fine Girls",
            "wowgirls" => "Wow Girls",
            "wowporn" => "Wow Porn",
            _ => string.Empty
        };

        if (!string.IsNullOrWhiteSpace(siteName))
        {
            await page.GetByRole(AriaRole.Complementary).GetByText(siteName).ClickAsync();
            await page.WaitForSelectorAsync(".cf_s_site");
            await page.WaitForLoadStateAsync();
        }
    }

    private async Task<int> GetTotalPagesAsync(IPage page)
    {
        var totalPagesStr = await page.Locator("div.pages > span").Last.TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);
        return totalPages;
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, site, subSite, pageNumber);
        
        var releaseHandles = await page.Locator("section.cf_content > ul > li > div.content_item > a.icon").ElementHandlesAsync();

        var listedReleases = new List<ListedRelease>();
        foreach (var releaseHandle in releaseHandles.Reverse())
        {
            var releaseIdAndUrl = await GetReleaseIdAsync(site, releaseHandle);
            listedReleases.Add(new ListedRelease(null, releaseIdAndUrl.Id, releaseIdAndUrl.Url, releaseHandle));
        }

        return listedReleases.AsReadOnly();
    }

    private async Task GoToPageAsync(IPage page, Site site, int targetPageNumber)
    {
        await page.WaitForLoadStateAsync();

        // Parse the initial state of the paginator
        var (currentPage, visiblePages, hasNext, hasPrevious) = await ParseVisiblePagesAndNavigation(page);
        if (currentPage == targetPageNumber)
        {
            return;
        }

        while (!visiblePages.Contains(targetPageNumber))
        {
            if (currentPage == targetPageNumber)
            {
                break;
            }

            var distances = visiblePages.Select(p => Math.Abs(p - targetPageNumber));
            var closestPageNumber = visiblePages[distances.ToList().IndexOf(distances.Min())];
            await ClickPageNumberAsync(page, closestPageNumber);

            (currentPage, visiblePages, hasNext, hasPrevious) = await ParseVisiblePagesAndNavigation(page);
        }

        // Click on the target page number
        await ClickPageNumberAsync(page, targetPageNumber);
    }

    private static async Task ClickPageNumberAsync(IPage page, int pageNumber)
    {
        var retryPolicy = Policy
            .Handle<PlaywrightException>()
            .WaitAndRetryAsync(3, retryAttempt => TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)));

        await retryPolicy.ExecuteAsync(async () =>
        {
            var pageElement = await page.QuerySelectorAsync($".paginator .pages .page[data-ca-state='paginator.page={pageNumber}']");
            if (pageElement != null)
            {
                await pageElement.ClickAsync();
            }
        });
    }

    private async Task<(int currentPage, int[] visiblePages, bool hasNext, bool hasPrevious)> ParseVisiblePagesAndNavigation(IPage page)
    {
        // Get the list of visible page elements
        var pageElements = await page.QuerySelectorAllAsync(".pages .page");

        // Parse the visible pages and find the active one
        List<int> visiblePages = new List<int>();
        int currentPage = 0;
        foreach (var pageElement in pageElements)
        {
            string pageText = await pageElement.InnerTextAsync();
            if (int.TryParse(pageText, out int pageNumber))
            {
                visiblePages.Add(pageNumber);
                // Check if the class 'active' is present
                bool isActive = await pageElement.EvaluateAsync<bool>("el => el.classList.contains('active')");
                if (isActive)
                {
                    currentPage = pageNumber;
                }
            }
        }

        // Determine the presence of the "next" navigation button
        bool hasNext = await page.QuerySelectorAsync(".nav.next.enabled") != null;

        // Determine the presence of the "prev" navigation button
        bool hasPrevious = await page.QuerySelectorAsync(".nav.prev.enabled") != null;

        return (currentPage, visiblePages.ToArray(), hasNext, hasPrevious);
    }

    // LEGACY
    private Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        throw new NotImplementedException();
    }
    
    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(Site site, IElementHandle currentRelease)
    {
        var relativeUrl = await currentRelease.GetAttributeAsync("href");
        var url = site.Url + relativeUrl;

        string pattern = @"/film/(?<id>\w+)/.*";
        Match match = Regex.Match(relativeUrl, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Could not parse ID from {url} using pattern {pattern}.");
        }

        return new ReleaseIdAndUrl(match.Groups["id"].Value, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        await page.WaitForLoadStateAsync();

        var releaseDate = await ScrapeReleaseDateAsync(page);
        var duration = await ScrapeDurationAsync(page);
        var description = await ScrapeDescriptionAsync(page);
        var title = await ScrapeTitleAsync(page);
        var performers = await ScrapePerformersAsync(page);
        var tags = await ScrapeTagsAsync(page);
        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsyncLegacy(page);

        var scene = new Release(
            releaseUuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.AvailableVideoFile).ToList(),
            "{}",
            DateTime.Now);
        
        if (_legacyDownloader.SceneImageExists(scene))
        {
            return scene;
        }

        // TODO: Fix this
        /*var previewElement = await currentRelease.QuerySelectorAsync("span > img");
        var originalUrl = await previewElement.GetAttributeAsync("src");

        string regexPattern = "icon_\\d+x\\d+.jpg";

        // We can't be sure which are found so we need to cycle through them.
        var candidates = new List<string>()
            {
                "icon_3840x2160.jpg",
                "icon_1920x1080.jpg",
                "icon_1280x720.jpg",
            }
            .Select(fileName => Regex.Replace(originalUrl, regexPattern, fileName))
            .Concat(new List<string> { originalUrl });

        foreach (var candidate in candidates)
        {
            try
            {

                await _downloader.DownloadSceneImageAsync(scene, candidate);
                Log.Debug($"Successfully downloaded preview from {candidate}.");
                break;
            }
            catch (WebException ex)
            {
                if (ex.Status == WebExceptionStatus.ProtocolError && (ex.Response as HttpWebResponse)?.StatusCode == HttpStatusCode.NotFound)
                {
                    Log.Debug($"Got 404 for preview from {candidate}.");
                    continue;
                }

                throw;
            }
        }*/
        
        return scene;
    }

    private async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var releaseDateRaw = await page.Locator("ul.details > li.date").TextContentAsync();
        return DateOnly.Parse(releaseDateRaw);
    }

    private async Task<string> ScrapeTitleAsync(IPage page)
    {
        var title = await page.Locator("section.content_header > div.content_info > div.title").TextContentAsync();
        return title;
    }

    private async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page)
    {
        var castElements = await page.Locator("section.content_header > div.content_info > ul.details > li.models > a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");
            var castId = castUrl.Substring(castUrl.LastIndexOf("/girl/") + "/girl/".Length);
            var castName = await castElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl));
        }
        return performers.AsReadOnly();
    }

    private async Task<IList<SiteTag>> ScrapeTagsAsync(IPage page)
    {
        var tagElements = await page.Locator("section.content_header > div.content_info > ul.genres > li > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = await tagElement.TextContentAsync();
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }
        return tags;
    }

    private async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var duration = await page.Locator("ul.details > li.duration").TextContentAsync();
        if (TimeSpan.TryParse(duration, out TimeSpan timespan))
        {
            return timespan;
        }

        return TimeSpan.FromSeconds(0);
    }

    private async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        if (!await page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).IsVisibleAsync())
        {
            return string.Empty;
        }

        await page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).ClickAsync();
        var elementHandles = await page.Locator("div.movie-details div.info-container div p").ElementHandlesAsync();
        var descriptionParagraphs = new List<string>();
        foreach (var elementHandle in elementHandles)
        {
            var descriptionParagraph = await elementHandle.TextContentAsync();
            if (!string.IsNullOrWhiteSpace(descriptionParagraph))
            {
                descriptionParagraphs.Add(descriptionParagraph);
            }
        }
        return string.Join("\r\n\r\n", descriptionParagraphs);
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        await page.GotoAsync(release.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var performerNames = release.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        var availableDownloads = await ParseAvailableDownloadsAsyncLegacy(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        return await _legacyDownloader.DownloadSceneAsync(release, page, selectedDownload.AvailableVideoFile, downloadConditions.PreferredDownloadQuality, async () =>
            await selectedDownload.ElementHandle.ClickAsync()
);
    }

    private static async Task<IList<IAvailableFile>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.ct_dl_items > ul > li").ElementHandlesAsync();
        var availableFiles = new List<IAvailableFile>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadLinkElement = await downloadItem.QuerySelectorAsync("a");
            var downloadUrl = await downloadLinkElement.GetAttributeAsync("href");
            var resolutionRaw = await downloadLinkElement.TextContentAsync();
            resolutionRaw = resolutionRaw.Replace("\n", "").Trim();
            var resolutionWidth = HumanParser.ParseResolutionWidth(resolutionRaw);
            var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionRaw);
            var codecElement = await downloadItem.QuerySelectorAsync("span.format");
            var codecRaw = await codecElement.InnerTextAsync();
            var codec = HumanParser.ParseCodec(codecRaw);
            var fpsElement = await downloadItem.QuerySelectorAsync("span.fps");
            var fpsRaw = await fpsElement.InnerTextAsync();
            var sizeElement = await downloadItem.QuerySelectorAsync("span.size");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var description = $"{codec.ToUpperInvariant()} {resolutionWidth}x{resolutionHeight} {fpsRaw}";

            availableFiles.Add(
                new AvailableVideoFile(
                    "video",
                    "scene",
                    description,
                    downloadUrl,
                    resolutionWidth,
                    resolutionHeight,
                    size,
                    double.Parse(fpsRaw.Replace("fps", "")),
                    codec)
            );
        }
        return availableFiles;
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsyncLegacy(IPage page)
    {
        var downloadItems = await page.Locator("div.ct_dl_items > ul > li").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadLinkElement = await downloadItem.QuerySelectorAsync("a");
            var downloadUrl = await downloadLinkElement.GetAttributeAsync("href");
            var resolutionRaw = await downloadLinkElement.TextContentAsync();
            resolutionRaw = resolutionRaw.Replace("\n", "").Trim();
            var resolutionWidth = HumanParser.ParseResolutionWidth(resolutionRaw);
            var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionRaw);
            var codecElement = await downloadItem.QuerySelectorAsync("span.format");
            var codecRaw = await codecElement.InnerTextAsync();
            var codec = HumanParser.ParseCodec(codecRaw);
            var fpsElement = await downloadItem.QuerySelectorAsync("span.fps");
            var fpsRaw = await fpsElement.InnerTextAsync();
            var sizeElement = await downloadItem.QuerySelectorAsync("span.size");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var description = $"{codec.ToUpperInvariant()} {resolutionWidth}x{resolutionHeight} {fpsRaw}";

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        description,
                        downloadUrl,
                        resolutionWidth,
                        resolutionHeight,
                        size,
                        double.Parse(fpsRaw.Replace("fps", "")),
                        codec),
                    downloadLinkElement));
        }
        return availableDownloads.OrderByDescending(d => d.AvailableVideoFile.ResolutionWidth).ThenByDescending(d => d.AvailableVideoFile.Fps).ToList();
    }
}
