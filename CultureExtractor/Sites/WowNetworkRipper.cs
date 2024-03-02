using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using System.Text.RegularExpressions;
using CultureExtractor.Models;
using Serilog;
using Polly;
using Microsoft.EntityFrameworkCore;
using System.Net;
using System.Collections.Immutable;
using System.Web;

namespace CultureExtractor.Sites;

[Site("allfinegirls")]
[Site("wowgirls")]
[Site("wowporn")]
[Site("ultrafilms")]
public class WowNetworkRipper : IYieldingScraper
{
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloader _downloader;
    private readonly IDownloadPlanner _downloadPlanner;

    public WowNetworkRipper(
        IPlaywrightFactory playwrightFactory,
        IRepository repository,
        IDownloader downloader,
        IDownloadPlanner downloadPlanner)
    {
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _downloader = downloader;
        _downloadPlanner = downloadPlanner;
    }

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        await foreach (var release in ScrapeScenesAsync(site, page, scrapeOptions))
        {
            yield return release;
        }
        await foreach (var release in ScrapeGalleriesAsync(site, page, scrapeOptions))
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
                IPage? releasePage = null;

                try
                {
                    releasePage = await page.Context.NewPageAsync();
                    await releasePage.GotoAsync(sceneToBeScraped.Url);
                    scene = await ScrapeSceneAsync(releasePage, site, sceneToBeScraped.ShortName, sceneToBeScraped.Url, releaseGuid);
                }
                catch (Exception ex)
                {
                    Log.Error(ex, $"Failed to scrape scene {sceneToBeScraped.Url}");
                }
                finally
                {
                    releasePage?.CloseAsync();
                }

                if (scene != null)
                {
                    yield return scene;
                }
            }
        }
    }

    private static async Task<Release> ScrapeSceneAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid)
    {
        await releasePage.WaitForLoadStateAsync();

        var releaseDate = await ScrapeReleaseDateAsync(releasePage);
        var duration = await ScrapeDurationAsync(releasePage);
        var description = await ScrapeDescriptionAsync(releasePage);
        var title = await ScrapeTitleAsync(releasePage);
        var performers = await ScrapePerformersAsync(releasePage);
        var tags = await ScrapeTagsAsync(releasePage);
        var availableVideoFiles = await ParseAvailableDownloadsAsync(releasePage);

        var previewElement = await releasePage.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "").Replace(" background-size: cover;", "");
        var availableImageFile = new AvailableImageFile("image", "scene", "preview", backgroundImageUrl, null, null, null);

        var scene = new Release(
            releaseGuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            releaseUrl,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            availableVideoFiles.Concat(new List<IAvailableFile> { availableImageFile }).ToList(),
            "{}",
            DateTime.Now);

        return scene;
    }

    private async IAsyncEnumerable<Release> ScrapeGalleriesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        await page.GotoAsync(site.Url + "/galleries/");
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
                IPage? releasePage = null;

                try
                {
                    releasePage = await page.Context.NewPageAsync();
                    await releasePage.GotoAsync(sceneToBeScraped.Url);
                    scene = await ScrapeGalleryAsync(releasePage, site, sceneToBeScraped.ShortName, sceneToBeScraped.Url, releaseGuid);
                }
                catch (Exception ex)
                {
                    Log.Error(ex, $"Failed to scrape scene {sceneToBeScraped.Url}");
                }
                finally
                {
                    releasePage?.CloseAsync();
                }

                if (scene != null)
                {
                    yield return scene;
                }
            }
        }
    }

    private static async Task<Release> ScrapeGalleryAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid)
    {
        await releasePage.WaitForLoadStateAsync();

        var releaseDate = await ScrapeReleaseDateAsync(releasePage);
        var description = await ScrapeDescriptionAsync(releasePage);
        var title = await ScrapeTitleAsync(releasePage);
        var performers = await ScrapePerformersAsync(releasePage);
        var tags = await ScrapeTagsAsync(releasePage);
        var availableGalleryFiles = await ParseAvailableGalleryDownloadsAsync(releasePage);

        var scene = new Release(
            releaseGuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            releaseUrl,
            description,
            -1,
            performers,
            tags,
            availableGalleryFiles,
            "{}",
            DateTime.Now);

        return scene;
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        var downloadedReleases = 0;
        foreach (var release in releases)
        {
            var releaseDownloadPlan = PlanDownloads(release, downloadConditions);
            var releaseMissingDownloadsPlan = await _downloadPlanner.PlanMissingDownloadsAsync(releaseDownloadPlan);

            if (!releaseMissingDownloadsPlan.AvailableFiles.Any())
            {
                continue;
            }

            IPage releasePage = await page.Context.NewPageAsync();
            var retryPolicy = Policy
                .Handle<PlaywrightException>()
                .WaitAndRetryAsync(3, retryAttempt => TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)));

            await retryPolicy.ExecuteAsync(async () => await releasePage.GotoAsync(release.Url));

            Release? updatedScrape;
            try
            {
                updatedScrape = release.Url.Contains("/film/")
                    ? await ScrapeSceneAsync(releasePage, site, release.ShortName, release.Url, release.Uuid)
                    : await ScrapeGalleryAsync(releasePage, site, release.ShortName, release.Url, release.Uuid);
            }
            catch (Exception ex)
            {
                Log.Warning(ex, "Could not scrape {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                continue;
            }
            await Task.Delay(10000);

            var existingDownloadEntities = await _downloadPlanner.GetExistingDownloadsAsync(release);
            Log.Information("Downloading: {Site} - {ReleaseDate} - {Release} [{Uuid}]", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name, release.Uuid);
            foreach (var videoDownload in await DownloadVideosAsync(downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return videoDownload;
            }
            await foreach (var galleryDownload in DownloadGalleryAsync(downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return galleryDownload;
            }
            await foreach (var imageDownload in DownloadImagesAsync(updatedScrape, existingDownloadEntities))
            {
                yield return imageDownload;
            }

            downloadedReleases++;
            Log.Information($"{downloadedReleases} releases downloaded in this session.");

            await releasePage.CloseAsync();
        }
    }

    private static ReleaseDownloadPlan PlanDownloads(Release release, DownloadConditions downloadConditions)
    {
        var sceneFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "scene").ToList();
        var galleryFiles = release.AvailableFiles.OfType<AvailableGalleryZipFile>().ToList();
        var imageFiles = release.AvailableFiles.OfType<AvailableImageFile>().ToList();

        var selectedSceneFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? sceneFiles.Take(1)
            : sceneFiles.TakeLast(1);
        var selectedGalleryFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? galleryFiles.Take(1)
            : galleryFiles.TakeLast(1);

        var availableFiles = new List<IAvailableFile>()
            .Concat(selectedSceneFiles)
            .Concat(selectedGalleryFiles)
            .Concat(imageFiles)
            .ToImmutableList();

        return new ReleaseDownloadPlan(release, availableFiles);
    }

    private async Task<IEnumerable<Download>> DownloadVideosAsync(DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "scene" });
        var selectedVideo = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableVideos.FirstOrDefault()
            : availableVideos.LastOrDefault();
        if (selectedVideo == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedVideo))
        {
            return new List<Download>();
        }

        var uri = new Uri(selectedVideo.Url);
        var queryParameters = HttpUtility.ParseQueryString(uri.Query);
        var suggestedFileName = queryParameters["filename"];
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.Variant);

        var headers = new WebHeaderCollection
        {
            { HttpRequestHeader.Referer, release.Url }
        };
        var fileInfo = await _downloader.TryDownloadAsync(release, selectedVideo, selectedVideo.Url, fileName, headers);
        if (fileInfo == null)
        {
            return new List<Download>();
        }

        var videoHashes = Hasher.Phash(@"""" + fileInfo.FullName + @"""");
        return new List<Download>
        {
            new(release, suggestedFileName, fileInfo.Name, selectedVideo, videoHashes)
        };
    }

    private async IAsyncEnumerable<Download> DownloadGalleryAsync(DownloadConditions downloadConditions, Release release,
        IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableGalleries = release.AvailableFiles
            .OfType<AvailableGalleryZipFile>()
            .Where(d => d is { FileType: "zip", ContentType: "gallery" });
        var selectedGallery = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableGalleries.FirstOrDefault()
            : availableGalleries.LastOrDefault();
        if (selectedGallery == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedGallery))
        {
            yield break;
        }

        var uri = new Uri(selectedGallery.Url);
        var queryParameters = HttpUtility.ParseQueryString(uri.Query);
        var suggestedFileName = queryParameters["filename"];
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedGallery.Variant);

        var headers = new WebHeaderCollection
        {
            { HttpRequestHeader.Referer, release.Url }
        };
        var fileInfo = await _downloader.TryDownloadAsync(release, selectedGallery, selectedGallery.Url, fileName, headers);
        if (fileInfo == null)
        {
            yield break;
        }

        var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
        var metadata = new GalleryZipFileMetadata(sha256Sum);
        yield return new Download(release, suggestedFileName, fileInfo.Name, selectedGallery, metadata);
    }

    private async IAsyncEnumerable<Download> DownloadImagesAsync(Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var imageFiles = release.AvailableFiles.OfType<AvailableImageFile>();
        foreach (var imageFile in imageFiles)
        {
            if (!_downloadPlanner.NotDownloadedYet(existingDownloadEntities, imageFile))
            {
                continue;
            }

            var uri = new Uri(imageFile.Url);
            var suggestedFileName = Path.GetFileName(uri.LocalPath);
            var suffix = Path.GetExtension(suggestedFileName);

            var headers = new WebHeaderCollection
            {
                { HttpRequestHeader.Referer, release.Url }
            };
            var fileName = string.IsNullOrWhiteSpace(imageFile.Variant) ? $"{imageFile.ContentType}{suffix}" : $"{imageFile.ContentType}_{imageFile.Variant}{suffix}";
            var fileInfo = await _downloader.TryDownloadAsync(release, imageFile, imageFile.Url, fileName, headers);
            if (fileInfo == null)
            {
                yield break;
            }

            var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
            var metadata = new ImageFileMetadata(sha256Sum);
            yield return new Download(release, $"{imageFile.ContentType}.jpg", fileInfo.Name, imageFile, metadata);
        }
    }

    private async Task LoginAsync(Site site, IPage page)
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

            await page.WaitForLoadStateAsync();
            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }
    }

    private static async Task SetSiteFilter(Site site, IPage page)
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
            _ => throw new ArgumentException($"Site {site.ShortName} not supported.")
        };

        if (!string.IsNullOrWhiteSpace(siteName))
        {
            await page.GetByRole(AriaRole.Complementary).GetByText(siteName).ClickAsync();
            await page.WaitForSelectorAsync(".cf_s_site");
            await page.WaitForLoadStateAsync();
        }
    }

    private static async Task<int> GetTotalPagesAsync(IPage page)
    {
        var totalPagesStr = await page.Locator("div.pages > span").Last.TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);
        return totalPages;
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

    private static async Task<(int currentPage, int[] visiblePages, bool hasNext, bool hasPrevious)> ParseVisiblePagesAndNavigation(IPage page)
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
    
    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(Site site, IElementHandle currentRelease)
    {
        var relativeUrl = await currentRelease.GetAttributeAsync("href");
        var url = site.Url + relativeUrl;

        string pattern = @"/(film|gallery)/(?<id>\w+)/.*";
        Match match = Regex.Match(relativeUrl, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Could not parse ID from {url} using pattern {pattern}.");
        }

        return new ReleaseIdAndUrl(match.Groups["id"].Value, url);
    }

    private static async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var releaseDateRaw = await page.Locator("ul.details > li.date").TextContentAsync();
        return DateOnly.Parse(releaseDateRaw);
    }

    private static async Task<string> ScrapeTitleAsync(IPage page)
    {
        var title = await page.Locator("section.content_header > div.content_info > div.title").TextContentAsync();
        return title;
    }

    private static async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page)
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

    private static async Task<IList<SiteTag>> ScrapeTagsAsync(IPage page)
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

    private static async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var duration = await page.Locator("ul.details > li.duration").TextContentAsync();
        if (TimeSpan.TryParse(duration, out TimeSpan timespan))
        {
            return timespan;
        }

        return TimeSpan.FromSeconds(0);
    }

    private static async Task<string> ScrapeDescriptionAsync(IPage page)
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

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.ct_dl_items > ul > li").ElementHandlesAsync();
        var availableFiles = new List<AvailableVideoFile>();
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

        availableFiles = availableFiles.OrderByDescending(f => f.Fps).ThenByDescending(f => f.ResolutionWidth).ToList();

        return availableFiles.AsReadOnly();
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableGalleryDownloadsAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.ct_dl_items > ul > li").ElementHandlesAsync();
        var availableFiles = new List<AvailableGalleryZipFile>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadLinkElement = await downloadItem.QuerySelectorAsync("a");
            var downloadUrl = await downloadLinkElement.GetAttributeAsync("href");
            var resolutionRaw = await downloadLinkElement.TextContentAsync();
            resolutionRaw = resolutionRaw.Replace("px", "").Trim();
            int resolutionWidth = -1;
            var description = "Original";
            if (resolutionRaw.ToUpperInvariant() != "ORIGINAL")
            {
                resolutionWidth = int.Parse(resolutionRaw);
                description = $"{resolutionWidth}px";
            }
            
            var sizeElement = await downloadItem.QuerySelectorAsync("span.size");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            availableFiles.Add(
                new AvailableGalleryZipFile(
                    "zip",
                    "gallery",
                    description,
                    downloadUrl,
                    resolutionWidth,
                    -1,
                    size)
            );
        }

        availableFiles = availableFiles.OrderByDescending(f => f.FileSize).ToList();

        return availableFiles.AsReadOnly();
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
