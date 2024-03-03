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

[Site("private")]
public class PrivateRipper : IYieldingScraper
{
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloader _downloader;
    private readonly IDownloadPlanner _downloadPlanner;

    public PrivateRipper(
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
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        await GoToPageAsync(page, site, 1);
        await page.WaitForLoadStateAsync();

        var totalPages = await GetTotalPagesAsync(page);

        for (var pageNumber = 1; pageNumber <= totalPages; pageNumber++)
        {
            await GoToPageAsync(page, site, pageNumber);

            var releaseHandles = await page.Locator("div.scene > a[data-track='SCENE_LINK']").ElementHandlesAsync();

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
                    scene = await ScrapeSceneAsync(releasePage, site, sceneToBeScraped.ShortName, sceneToBeScraped.Url, releaseGuid, sceneToBeScraped.ElementHandle);
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

    private static async Task<Release> ScrapeSceneAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid, IElementHandle elementHandle)
    {
        await releasePage.WaitForLoadStateAsync();

        await releasePage.GetByRole(AriaRole.Button, new() { Name = "Play Video" }).ClickAsync();
        await releasePage.GetByRole(AriaRole.Button, new() { Name = "Pause" }).ClickAsync();

        var releaseDate = await ScrapeReleaseDateAsync(releasePage);
        var duration = await ScrapeDurationAsync(releasePage);
        var description = await ScrapeDescriptionAsync(releasePage);
        var title = await ScrapeTitleAsync(releasePage);
        var performers = await ScrapePerformersAsync(releasePage);
        var tags = await ScrapeTagsAsync(releasePage);
        var availableVideoFiles = await ParseAvailableDownloadsAsync(releasePage);

        var ogImageMeta = await releasePage.QuerySelectorAsync("meta[property='og:image']");
        var ogImageUrl = await ogImageMeta.GetAttributeAsync("content");
        var availableImageFile = new AvailableImageFile("image", "scene", "preview", ogImageUrl, null, null, null);

        var ogTrailerMeta = await releasePage.QuerySelectorAsync("meta[property='og:video']");
        var ogTrailerUrl = await ogTrailerMeta.GetAttributeAsync("content");
        var availableTrailerFile = new AvailableVideoFile("video", "trailer", string.Empty, ogTrailerUrl, null, null, null, null, null);

        var galleryDownloadLink = await releasePage.QuerySelectorAsync("div.download-pictures a");
        var galleryDownloadUrl = await galleryDownloadLink.GetAttributeAsync("href");
        var availableGalleryFile = new AvailableGalleryZipFile("zip", "gallery", "original", galleryDownloadUrl, null, null, null);

        var previewVideo = await elementHandle.QuerySelectorAsync("video source");
        var previewVideoUrl = await previewVideo.GetAttributeAsync("src");
        var availablePreviewFile = new AvailableVideoFile("video", "preview", string.Empty, previewVideoUrl, null, null, null, null, null);

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
            availableVideoFiles
                .Concat(new List<IAvailableFile> { availableImageFile })
                .Concat(new List<IAvailableFile> { availablePreviewFile })
                .Concat(new List<IAvailableFile> { availableGalleryFile })
                .Concat(new List<IAvailableFile> { availableTrailerFile })
                .ToList(),
            "{}",
            DateTime.Now);

        return scene;
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        IPage searchPage = await page.Context.NewPageAsync();

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

            
            string encodedString = HttpUtility.HtmlEncode(release.Name);
            await searchPage.GotoAsync("/en/search.php?query=" + encodedString);
            await searchPage.WaitForLoadStateAsync();
            var searchResults = await searchPage.Locator("div.scene > a[data-track='SCENE_LINK']").ElementHandlesAsync();
            if (searchResults.Count == 0)
            {
                Log.Warning("Could not find {Release} on {Site}", release.Name, site.Name);
                continue;
            }
            IElementHandle searchResult = null;

            foreach (var result in searchResults)
            {
                var url = await result.GetAttributeAsync("href");
                if (url != null && url.EndsWith(release.ShortName))
                {
                    searchResult = result;
                    break; // Exit the loop once we find the first match.
                }
            }

            if (searchResult == null)
            {
                Log.Warning("Could not find {Release} on {Site}", release.Name, site.Name);
                continue;
            }

            IPage releasePage = await page.Context.NewPageAsync();
            await releasePage.GotoAsync(release.Url);

            Release? updatedScrape;
            try
            {
                updatedScrape = await ScrapeSceneAsync(releasePage, site, release.ShortName, release.Url, release.Uuid, searchResult);
            }
            catch (Exception ex)
            {
                Log.Warning(ex, "Could not scrape {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                continue;
            }
            await Task.Delay(10000);

            var existingDownloadEntities = await _downloadPlanner.GetExistingDownloadsAsync(release);
            Log.Information("Downloading: {Site} - {ReleaseDate} - {Release} [{Uuid}]", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name, release.Uuid);
            foreach (var videoDownload in await DownloadSceneVideosAsync(downloadConditions, updatedScrape, existingDownloadEntities))
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
            foreach (var trailerDownload in await DownloadTrailerAsync(updatedScrape, existingDownloadEntities))
            {
                yield return trailerDownload;
            }
            foreach (var previewDownload in await DownloadPreviewAsync(updatedScrape, existingDownloadEntities))
            {
                yield return previewDownload;
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

    private async Task<IEnumerable<Download>> DownloadSceneVideosAsync(DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
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
        var suggestedFileName = uri.LocalPath.Substring(uri.LocalPath.LastIndexOf("/") + 1);
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

    private async Task<IEnumerable<Download>> DownloadTrailerAsync(Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "trailer" });
        var selectedVideo = availableVideos.FirstOrDefault();
        if (selectedVideo == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedVideo))
        {
            return new List<Download>();
        }

        var uri = new Uri(selectedVideo.Url);
        var suggestedFileName = uri.LocalPath.Substring(uri.LocalPath.LastIndexOf("/") + 1);
        var suffix = Path.GetExtension(suggestedFileName);

        var fileName = $"{selectedVideo.ContentType}{suffix}";

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

    private async Task<IEnumerable<Download>> DownloadPreviewAsync(Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "preview" });
        var selectedVideo = availableVideos.FirstOrDefault();
        if (selectedVideo == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedVideo))
        {
            return new List<Download>();
        }

        var uri = new Uri(selectedVideo.Url);
        var suggestedFileName = uri.LocalPath.Substring(uri.LocalPath.LastIndexOf("/") + 1);
        var suffix = Path.GetExtension(suggestedFileName);

        var fileName = $"{selectedVideo.ContentType}{suffix}";

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
        var suggestedFileName = uri.LocalPath.Substring(uri.LocalPath.LastIndexOf("/") + 1);
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
        var usernameInput = page.GetByPlaceholder("Username");
        var passwordInput = page.GetByPlaceholder("Password");
        var signInButton = page.GetByRole(AriaRole.Button, new() { Name = "Sign In" });

        if (await signInButton.IsVisibleAsync())
        {
            await usernameInput.FillAsync(site.Username);
            await passwordInput.FillAsync(site.Password);
            await signInButton.ClickAsync();
            await page.WaitForLoadStateAsync();
            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }
    }

    private static async Task<int> GetTotalPagesAsync(IPage page)
    {
        var totalPagesStr = await page.Locator("ul.pagination > li:not(.next):not(.prev)").Last.TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);
        return totalPages;
    }

    private static async Task GoToPageAsync(IPage page, Site site, int targetPageNumber)
    {
        await page.GotoAsync($"{site.Url}/en/scenes/{targetPageNumber}/");
    }

    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(Site site, IElementHandle currentRelease)
    {
        var url = await currentRelease.GetAttributeAsync("href");
        var number = url.Substring(url.LastIndexOf('/') + 1);
        return new ReleaseIdAndUrl(number, url);
    }

    private static async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var uploadDateMeta = await page.QuerySelectorAsync("meta[itemprop='uploadDate']");
        var releaseDateRaw = await uploadDateMeta.GetAttributeAsync("content");
        return DateOnly.Parse(releaseDateRaw);
    }

    private static async Task<string> ScrapeTitleAsync(IPage page)
    {
        var titleMeta = await page.QuerySelectorAsync("meta[property='og:title']");
        var title = await titleMeta.GetAttributeAsync("content");
        return title.Trim().Replace(" HD Videos & Porn Photos - Private Porn Sex Videos", "");
    }

    private static async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page)
    {
        var castElements = await page.Locator("li.tag-models a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");
            var castId = castUrl.Substring(castUrl.LastIndexOf("/") + 1);
            var castName = await castElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl));
        }
        return performers.AsReadOnly();
    }

    private static async Task<IList<SiteTag>> ScrapeTagsAsync(IPage page)
    {
        var tagElements = await page.Locator("li.tag-tags a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Substring(tagUrl.LastIndexOf("/category/") + "/category/".Length);
            tagId = tagId.Substring(0, tagId.Length - 1);
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }
        return tags;
    }

    private static async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var duration = await page.Locator("div#scene_player span.vjs-remaining-time-display").TextContentAsync();
        duration = duration.Replace("-", "");
        return HumanParser.ParseDuration(duration);
    }

    private static async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        var descriptionMeta = await page.QuerySelectorAsync("meta[property='og:description']");
        var description = await descriptionMeta.GetAttributeAsync("content");
        return description;
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableDownloadsAsync(IPage page)
    {
        var availableFiles = new List<AvailableVideoFile>();

        var streams = await page.Locator("video#scene_player_html5_api source").ElementHandlesAsync();
        foreach (var stream in streams)
        {
            var resolution = await stream.GetAttributeAsync("label");
            if (resolution == "4K UHD")
            {
                availableFiles.Add(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        resolution,
                        await stream.GetAttributeAsync("src"),
                        3840,
                        2160,
                        -1,
                        -1,
                        "H.264")
                );
                break;
            }
        }

        var downloadItems = await page.Locator("a.full_download_link").ElementHandlesAsync();
        foreach (var downloadLinkElement in downloadItems)
        {
            var downloadUrl = await downloadLinkElement.GetAttributeAsync("href");
            var descriptionRaw = await downloadLinkElement.InnerTextAsync();
            var sizeElement = await downloadLinkElement.QuerySelectorAsync("small");
            var sizeRaw = await sizeElement.TextContentAsync();

            var resolutionRaw = descriptionRaw.Replace(sizeRaw, "");
            var resolutionWidth = -1;
            var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionRaw);
            var codec = "H.264";
            var size = HumanParser.ParseFileSize(sizeRaw);

            availableFiles.Add(
                new AvailableVideoFile(
                    "video",
                    "scene",
                    resolutionRaw,
                    downloadUrl,
                    resolutionWidth,
                    resolutionHeight,
                    size,
                    -1,
                    codec)
            );
        }

        availableFiles = availableFiles.OrderByDescending(f => f.ResolutionWidth).ToList();

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
