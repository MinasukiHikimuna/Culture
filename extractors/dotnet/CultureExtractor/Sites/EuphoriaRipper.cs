using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using System.Text.RegularExpressions;
using CultureExtractor.Models;
using Serilog;
using Polly;
using System.Collections.Immutable;
using System.Net;
using System.Web;

namespace CultureExtractor.Sites;

[Site("sensuallove")]
[Site("angelslove")]
public class EuphoriaRipper : IYieldingScraper
{
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloadPlanner _downloadPlanner;
    private readonly IDownloader _downloader;

    public EuphoriaRipper(IPlaywrightFactory playwrightFactory, IRepository repository, IDownloadPlanner downloadPlanner, IDownloader downloader)
    {
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _downloadPlanner = downloadPlanner;
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var emailInputLocator = page.GetByPlaceholder("E-Mail");

        if (await emailInputLocator.IsVisibleAsync())
        {
            await page.GetByPlaceholder("E-Mail").ClickAsync();
            await page.GetByPlaceholder("E-Mail").FillAsync(site.Username);
            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            await page.GetByText("Get Inside").ClickAsync();

            await page.WaitForLoadStateAsync();
            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }
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
        await page.GetByRole(AriaRole.Navigation).GetByRole(AriaRole.Link, new() { Name = "Content" }).ClickAsync();
        await page.GetByText("Movies").First.ClickAsync();
        // await SetSiteFilter(site, page);

        var totalPages = await GetTotalPagesAsync(page);
        for (var pageNumber = 1; pageNumber <= totalPages; pageNumber++)
        {
            await GoToPageAsync(page, site, pageNumber);

            var scenesLocator = page.Locator("div.content-view-lg > div.content-view-grid > div.content-grid-item-wrapper");
            await scenesLocator.First.WaitForAsync(new() { State = WaitForSelectorState.Visible });
            var releaseHandles = await scenesLocator.ElementHandlesAsync();

            var listedReleases = new List<ListedRelease>();
            foreach (var releaseHandle in releaseHandles)
            {
                var releaseIdAndUrl = await GetReleaseIdAsync(releaseHandle);
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

    private async Task SetSiteFilter(Site site, IPage page)
    {
        var locator = "div.sorter-filter:has(div.sort-filter-label:text-is('Site:')) > div.sort-filter-widget";
        await page.Locator(locator).ClickAsync();

        var siteName = site.ShortName switch
        {
            "sensuallove" => "Sensual.Love",
            "angelslove" => "Angels.Love",
            _ => throw new ArgumentException($"Site {site.ShortName} not supported.")
        };

        var elementHandles = await page.Locator(locator)
            .Locator(".sort-filter-selector-option")
            .ElementHandlesAsync();

        foreach (var elementHandle in elementHandles)
        {
            var text = await elementHandle.InnerTextAsync();
            if (text.Equals(siteName, StringComparison.OrdinalIgnoreCase))
            {
                await elementHandle.ClickAsync();
                return;
            }
        }

        throw new InvalidOperationException($"Could not find site {siteName} in the filter options.");
    }

    private async IAsyncEnumerable<Release> ScrapeGalleriesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        await page.GetByRole(AriaRole.Navigation).GetByRole(AriaRole.Link, new() { Name = "Content" }).ClickAsync();
        await page.GetByText("Photos").First.ClickAsync();
        // await SetSiteFilter(site, page);

        var totalPages = await GetTotalPagesAsync(page);
        for (var pageNumber = 1; pageNumber <= totalPages; pageNumber++)
        {
            await GoToPageAsync(page, site, pageNumber);

            var releaseHandles = await page.Locator("div.content-view-lg > div.content-view-grid > div.content-grid-item-wrapper").ElementHandlesAsync();

            var listedReleases = new List<ListedRelease>();
            foreach (var releaseHandle in releaseHandles)
            {
                var releaseIdAndUrl = await GetReleaseIdAsync(releaseHandle);
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

     private static async Task<int> GetTotalPagesAsync(IPage page)
    {
        var totalPagesStr = await page.Locator("span.total-pages").First.TextContentAsync();
        totalPagesStr = totalPagesStr.Replace("of ", "");
        var totalPages = int.Parse(totalPagesStr);
        return totalPages;
    }

    private static async Task GoToPageAsync(IPage page, Site site, int pageNumber)
    {
        await page.GotoAsync($"{site.Url}content?page={pageNumber}");
    }

    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle currentRelease)
    {
        var linkElement = await currentRelease.QuerySelectorAsync("a");
        var url = await linkElement.GetAttributeAsync("href");
        var id = url.Replace("/members/content/item/", "");
        return new ReleaseIdAndUrl(id, url);
    }

    private async Task<Release> ScrapeSceneAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseUuid)
    {
        DateOnly releaseDate = await ScrapeReleaseDateAsync(releasePage);
        TimeSpan duration = await ScrapeDurationAsync(releasePage);
        string? title = await ScrapeTitleAsync(releasePage);
        List<SitePerformer> performers = await ScrapePerformersAsync(releasePage);
        List<SiteTag> tags = await ScrapeTagsAsync(releasePage);

        var availableVideoFiles = await ParseAvailableDownloadsAsync(releasePage);

        var previewElement = await releasePage.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "").Replace(" background-size: cover;", "");
        var availableImageFile = new AvailableImageFile("image", "scene", "preview", backgroundImageUrl, null, null, null);

        var release = new Release(
            releaseUuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            releaseUrl,
            string.Empty,
            duration.TotalSeconds,
            performers,
            tags,
            availableVideoFiles.Concat(new List<IAvailableFile> { availableImageFile }).ToList(),
            "{}",
            DateTime.Now);

        return release;
    }

    private static async Task<List<SiteTag>> ScrapeTagsAsync(IPage releasePage)
    {
        var tagElements = await releasePage.Locator("div.metadata div.tags > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Substring(tagUrl.LastIndexOf("?action=bytag_") + "?action=bytag_".Length);
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        return tags;
    }

    private static async Task<List<SitePerformer>> ScrapePerformersAsync(IPage releasePage)
    {
        var performerElements = await releasePage.Locator("div.metadata div.models > a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var performerElement in performerElements)
        {
            var castUrl = await performerElement.GetAttributeAsync("href");
            var castId = castUrl.Substring(castUrl.LastIndexOf("/") + 1);
            var castName = await performerElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl, "{}"));
        }

        return performers;
    }

    private static async Task<string?> ScrapeTitleAsync(IPage releasePage)
    {
        return await releasePage.Locator("div.metadata div.title").GetAttributeAsync("title");
    }

    private static async Task<TimeSpan> ScrapeDurationAsync(IPage releasePage)
    {
        var durationRaw = await releasePage.Locator("div.video-duration > div.count").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);
        return duration;
    }

    private static async Task<DateOnly> ScrapeReleaseDateAsync(IPage releasePage)
    {
        var releaseDateRaw = await releasePage.Locator("div.release-date > div.date").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw!);
        return releaseDate;
    }

    private static async Task<Release> ScrapeGalleryAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid)
    {
        await releasePage.WaitForLoadStateAsync();

        var releaseDate = await ScrapeReleaseDateAsync(releasePage);
        var title = await ScrapeTitleAsync(releasePage);
        var performers = await ScrapePerformersAsync(releasePage);
        var tags = await ScrapeTagsAsync(releasePage);
        var availableGalleryFiles = await ParseAvailableGalleryFilesAsync(releasePage);

        var scene = new Release(
            releaseGuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            releaseUrl,
            string.Empty,
            -1,
            performers,
            tags,
            availableGalleryFiles,
            "{}",
            DateTime.Now);

        return scene;
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.download-center > div.download-buttons > div.download-button-wrapper").ElementHandlesAsync();
        var availableFiles = new List<AvailableVideoFile>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadButtonElement = await downloadItem.QuerySelectorAsync("div.clickable");
            var downloadUrl = await downloadButtonElement.GetAttributeAsync("data-href");
            var resolutionWidth = HumanParser.ParseResolutionWidth(downloadUrl);
            var resolutionHeight = HumanParser.ParseResolutionHeight(downloadUrl);
            var codecElement = await downloadItem.QuerySelectorAsync("div.format-name");
            var codecRaw = await codecElement.InnerTextAsync();
            var codec = HumanParser.ParseCodec(codecRaw);
            if (codec == string.Empty)
            {
                codec = HumanParser.ParseCodec("H.264");
            }
            var sizeElement = await downloadItem.QuerySelectorAsync("div.info");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var descriptionRaw = await downloadItem.TextContentAsync();
            var description = Regex.Replace(descriptionRaw, @"\s+", " ");

            availableFiles.Add(
                new AvailableVideoFile(
                    "video",
                    "scene",
                    description,
                    downloadUrl,
                    resolutionWidth,
                    resolutionHeight,
                    size,
                    -1,
                    codec));
        }
        return availableFiles.OrderByDescending(d => d.ResolutionWidth).ThenByDescending(d => d.Fps).ToList();
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableGalleryFilesAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.download-center > div.download-buttons > div.download-button-wrapper").ElementHandlesAsync();
        var availableFiles = new List<AvailableGalleryZipFile>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadButtonElement = await downloadItem.QuerySelectorAsync("div.clickable");
            var downloadUrl = await downloadButtonElement.GetAttributeAsync("data-href");

            var sizeElement = await downloadItem.QuerySelectorAsync("div.info");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var descriptionRaw = await downloadItem.TextContentAsync();
            var description = Regex.Replace(descriptionRaw, @"\s+", " ");

            availableFiles.Add(
                new AvailableGalleryZipFile(
                    "zip",
                    "gallery",
                    description,
                    downloadUrl,
                    -1,
                    -1,
                    size)
            );
        }
        return availableFiles.OrderByDescending(d => d.FileSize).ToList();
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

            // this is now done on every scene despite we might already have all files
            // the reason for updated scrape is that the links are timebombed and we need to refresh those
            Release? updatedScrape;
            try
            {
                updatedScrape = release.AvailableFiles.Any(availableFile => availableFile.ContentType == "scene")
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
            await foreach(var galleryDownload in DownloadGalleryAsync(downloadConditions, updatedScrape, existingDownloadEntities))
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

    private static ReleaseDownloadPlan PlanDownloads(Release release, DownloadConditions downloadConditions)
    {
        var sceneFiles = release.AvailableFiles.OfType<AvailableVideoFile>().ToList();
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
}
