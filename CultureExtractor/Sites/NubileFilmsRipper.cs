using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using System.Text.RegularExpressions;
using CultureExtractor.Models;
using Serilog;
using Polly;
using Microsoft.EntityFrameworkCore;
using System.Net;
using System.Collections.Immutable;
using System.Text.Json;

namespace CultureExtractor.Sites;

[Site("nubilefilms")]
[Site("nfbusty")]
[Site("thatsitcomshow")]
[Site("hotcrazymess")]
[Site("girlsonlyporn")]
public class NubileFilmsRipper : IYieldingScraper
{
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloader _downloader;
    private readonly IDownloadPlanner _downloadPlanner;

    public NubileFilmsRipper(
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

            var releaseHandles = await page.Locator("div.img-wrapper > a").ElementHandlesAsync();

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
        var availableTrailerFiles = await ParseAvailableTrailerAsync(releasePage);
        var availablePosterFiles = await ParseAvailablePosterFilesAsync(releasePage);
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
            duration.TotalSeconds,
            performers,
            tags,
            availableVideoFiles.Concat(availableTrailerFiles).Concat(availablePosterFiles).Concat(availableGalleryFiles).ToList(),
            "{}",
            DateTime.Now);

        return scene;
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailablePosterFilesAsync(IPage releasePage)
    {
        var previewElement = await releasePage.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");
        var availableImageFile = new AvailableImageFile("image", "scene", "preview", backgroundImageUrl, null, null, null);
        var availableImageFiles = new List<IAvailableFile> { availableImageFile };

        return availableImageFiles;
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
                updatedScrape = await ScrapeSceneAsync(releasePage, site, release.ShortName, release.Url, release.Uuid);
                await _repository.UpsertRelease(updatedScrape);
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
            foreach (var trailerDownload in await DownloadTrailersAsync(downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return trailerDownload;
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
        var suggestedFileName = Path.GetFileName(uri.LocalPath);
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

    private async Task<IEnumerable<Download>> DownloadTrailersAsync(DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "trailer" });
        var selectedVideo = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableVideos.FirstOrDefault()
            : availableVideos.LastOrDefault();
        if (selectedVideo == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedVideo))
        {
            return new List<Download>();
        }

        var uri = new Uri(selectedVideo.Url);
        var suggestedFileName = Path.GetFileName(uri.LocalPath);
        var suffix = Path.GetExtension(suggestedFileName);

        var fileName = $"{selectedVideo.ContentType} [{selectedVideo.Variant}]{suffix}";

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
        var suggestedFileName = Path.GetFileName(uri.LocalPath);
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
        var signInButton = page.GetByRole(AriaRole.Button, new() { Name = "Sign In" });
        var emailInput = page.GetByPlaceholder("Email or Username");
        var passwordInput = page.GetByPlaceholder("Password");

        if (await signInButton.IsVisibleAsync())
        {
            await emailInput.FillAsync(site.Username);
            await passwordInput.FillAsync(site.Password);
            await signInButton.ClickAsync();
            await page.WaitForLoadStateAsync();

            await page.WaitForLoadStateAsync();
            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }
    }

    private static async Task<int> GetTotalPagesAsync(IPage page)
    {
        var paginationElement = await page.QuerySelectorAsync("body > div.content-grid-ribbon.mb-2.mt-3.pt-2.py-md-2.position-relative.content-grid-footer > div > div > div.content-grid-ribbon-center.col-12.justify-content-center.mx-auto.mb-2.mb-lg-0 > div > ul > li.page-item.page-item-dropdown > div > button");
        var paginationText = await paginationElement.TextContentAsync();

        var parts = paginationText.Split("of");
        if (parts.Length != 2)
        {
            throw new ArgumentException("Invalid format");
        }

        if (!int.TryParse(parts[1].Trim(), out int numberOfPages))
        {
            throw new ArgumentException("Cannot parse number of pages");
        }

        return numberOfPages;
    }

    private async Task GoToPageAsync(IPage page, Site site, int targetPageNumber)
    {
        var skipAmount = (targetPageNumber - 1) * 12;

        switch (site.ShortName)
        {
            case "nubilefilms":
                await page.GotoAsync(site.Url + $"/video/gallery/website/4/{skipAmount}");
                break;
            case "nfbusty":
                await page.GotoAsync(site.Url + $"/video/gallery/website/20/{skipAmount}");
                break;
            case "thatsitcomshow":
                await page.GotoAsync(site.Url + $"/video/gallery/website/30/{skipAmount}");
                break;
            case "girlsonlyporn":
                await page.GotoAsync(site.Url + $"/video/gallery/website/71/{skipAmount}");
                break;
            case "hotcrazymess":
                await page.GotoAsync(site.Url + $"/video/gallery/website/29/{skipAmount}");
                break;
            default:
                throw new InvalidOperationException($"Site {site.ShortName} is not supported.");
        }
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

        string pattern = @"/video/watch/(?<id>\w+)/.*";
        Match match = Regex.Match(relativeUrl, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Could not parse ID from {url} using pattern {pattern}.");
        }

        return new ReleaseIdAndUrl(match.Groups["id"].Value, url);
    }

    private static async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var releaseDateRaw = await page.Locator("div.clearfix > span.date").TextContentAsync();
        return DateOnly.Parse(releaseDateRaw);
    }

    private static async Task<string> ScrapeTitleAsync(IPage page)
    {
        var title = await page.Locator("h2").TextContentAsync();
        var titleComponents = title.Split(" - ");
        return titleComponents[1].Replace(":", "") + " - " + titleComponents[0];
    }

    private static async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page)
    {
        var castElements = await page.Locator("div.content-pane-performers > a.content-pane-performer").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");

            string pattern = @"/model/profile/(?<id>\w+)/.*";
            Match match = Regex.Match(castUrl, pattern);
            if (!match.Success)
            {
                throw new InvalidOperationException($"Could not parse ID from {castUrl} using pattern {pattern}.");
            }


            var castName = await castElement.TextContentAsync();
            performers.Add(new SitePerformer(match.Groups["id"].Value, castName, castUrl));
        }
        return performers.AsReadOnly();
    }

    private static async Task<IList<SiteTag>> ScrapeTagsAsync(IPage page)
    {
        var tagElements = await page.Locator("div.categories > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");

            string pattern = @"/video/category/(?<id>\w+)/.*";
            Match match = Regex.Match(tagUrl, pattern);
            if (!match.Success)
            {
                throw new InvalidOperationException($"Could not parse ID from {tagUrl} using pattern {pattern}.");
            }

            var tagId = match.Groups["id"].Value;
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagId, tagName.Trim(), tagUrl));
        }
        return tags;
    }

    private static async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var duration = await page.Locator("span.vjs-remaining-time-display").TextContentAsync();
        return HumanParser.ParseDuration(duration);
    }

    private static async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        var descriptionElements = await page.QuerySelectorAllAsync("div.content-pane-description > p");
        var descriptionParts = new List<string>();

        foreach (var element in descriptionElements)
        {
            var text = await element.InnerTextAsync();
            descriptionParts.Add(text);
        }

        return string.Join(Environment.NewLine + Environment.NewLine, descriptionParts);
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.edge-download-item").ElementHandlesAsync();
        var availableFiles = new List<AvailableVideoFile>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadLinkElement = await downloadItem.QuerySelectorAsync("a");
            var downloadUrl = await downloadLinkElement.GetAttributeAsync("href");
            downloadUrl = "https:" + downloadUrl;

            var sizeElement = await downloadItem.QuerySelectorAsync("div.edge-download-item-file-meta");
            var sizeRaw = await sizeElement.TextContentAsync();
            var match = Regex.Match(sizeRaw, @"\((\d+(?:\.\d+)?)\s*(\w+)\)");
            if (!match.Success)
            {
                throw new ArgumentException("Invalid format");
            }

            var size = double.Parse(match.Groups[1].Value);
            var unit = match.Groups[2].Value;
            var fileSize = HumanParser.ParseFileSize($"{size} {unit}");

            var resolutionElement = await downloadItem.QuerySelectorAsync("div.edge-download-item-dimensions");
            var resolutionRaw = await resolutionElement.TextContentAsync();

            var match2 = Regex.Match(resolutionRaw, @"(?<width>\d+)x(?<height>\d+)");
            if (!match2.Success)
            {
                throw new ArgumentException("Invalid format");
            }

            var resolutionWidth = int.Parse(match2.Groups["width"].Value);
            var resolutionHeight = int.Parse(match2.Groups["height"].Value);


            var description = $"{resolutionWidth}x{resolutionHeight}";

            availableFiles.Add(
                new AvailableVideoFile(
                    "video",
                    "scene",
                    description,
                    downloadUrl,
                    resolutionWidth,
                    resolutionHeight,
                    fileSize,
                    null,
                    null)
            );
        }

        availableFiles = availableFiles.OrderByDescending(f => f.ResolutionWidth).ToList();

        return availableFiles.AsReadOnly();
    }

    private record Trailer(string res, string label, string url);

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableTrailerAsync(IPage page)
    {
        var trailerFilesElement = await page.GetByText("Watch Trailer").ElementHandleAsync();
        if (trailerFilesElement == null)
        {
            return new List<IAvailableFile>();
        }

        var trailerFilesJson = await trailerFilesElement.GetAttributeAsync("data-trailer-files");
        var trailers = JsonSerializer.Deserialize<List<Trailer>>(trailerFilesJson);

        return trailers.Select(trailers => new AvailableVideoFile(
            "video",
            "trailer",
            trailers.label,
            "https:" + trailers.url,
            -1,
            int.Parse(trailers.res),
            null,
            null,
            null)).ToList().AsReadOnly();
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableGalleryDownloadsAsync(IPage page)
    {
        var picsElement = await page.GetByText("Pics").ElementHandleAsync();
        if (picsElement == null)
        {
            return new List<IAvailableFile>();
        }

        await picsElement.ClickAsync();

        var downloadItems = await page.Locator("body > div.container.mt-4.mt-lg-2 > div:nth-child(1) > div.col-12.col-md-5.col-lg-7.content-pane-related-links > div:nth-child(5) > div > a").ElementHandlesAsync();
        var availableFiles = new List<AvailableGalleryZipFile>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadUrl = await downloadItem.GetAttributeAsync("href");
            downloadUrl = "https:" + downloadUrl;

            var fileNameElement = await downloadItem.QuerySelectorAsync("span.file-name");
            var fileNameTextContent = await fileNameElement.TextContentAsync();
            var description = fileNameTextContent.Trim();

            var resolutionElement = await downloadItem.QuerySelectorAsync("span.dimensions");
            var resolutionTextContent = await resolutionElement.TextContentAsync();
            var resolutionRaw = resolutionTextContent.Replace("px", "").Trim();

            var match2 = Regex.Match(resolutionRaw, @"(?<width>\d+)x(?<height>\d+)");
            if (!match2.Success)
            {
                throw new ArgumentException("Invalid format");
            }

            var resolutionWidth = int.Parse(match2.Groups["width"].Value);
            var resolutionHeight = int.Parse(match2.Groups["height"].Value);

            availableFiles.Add(
                new AvailableGalleryZipFile(
                    "zip",
                    "gallery",
                    description,
                    downloadUrl,
                    resolutionWidth,
                    resolutionHeight,
                    -1)
            );
        }

        availableFiles = availableFiles.OrderByDescending(f => f.ResolutionWidth).ToList();

        return availableFiles.AsReadOnly();
    }
}
