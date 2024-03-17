using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using CultureExtractor.Models;
using Serilog;
using Microsoft.EntityFrameworkCore;
using System.Net;
using System.Collections.Immutable;
using System.Web;
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using System.Reflection.Metadata;
using System.Xml.Linq;
using Newtonsoft.Json.Linq;
using System.Text.Json;

namespace CultureExtractor.Sites;

[Site("kellymadison")]
[Site("pornfidelity")]
[Site("teenfidelity")]
public class PornFidelityNetworkRipper : IYieldingScraper
{
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloader _downloader;
    private readonly IDownloadPlanner _downloadPlanner;

    public PornFidelityNetworkRipper(
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

            var releaseHandles = await page.Locator("div.card.episode a.card-link").ElementHandlesAsync();

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

                var randomDuration = new Random().Next(5000, 10000);
                await Task.Delay(randomDuration);
            }
        }
    }

    private static async Task<Release> ScrapeSceneAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid)
    {
        await releasePage.WaitForLoadStateAsync();

        var cardElement = await releasePage.QuerySelectorAsync("#site-content > section:nth-child(3) > div > div > div.column.is-full-mobile.is-four-fifths-desktop > div > div.card-content > div.columns");
        var leftColumn = await cardElement.QuerySelectorAsync("div.column:nth-child(1)");
        var rightColumn = await cardElement.QuerySelectorAsync("div.column:nth-child(2)");

        var chaptersElement = await leftColumn.QuerySelectorAllAsync("#dropdown-menu-chapters > div > a");

        var duration = await ScrapeDurationAsync(releasePage);

        var description = await rightColumn.TextContentAsync();
        description = description.Replace("Episode Summary", "").Trim();

        var titleElement = await leftColumn.QuerySelectorAsync("ul > li:nth-child(2)");
        var title = await titleElement.TextContentAsync();
        title = title.Replace("Title:", "").Trim();

        var dateElement = await leftColumn.QuerySelectorAsync("ul > li:nth-child(4)");
        var releaseDateRaw = await dateElement.TextContentAsync();
        DateOnly releaseDate;
        if (releaseDateRaw.Contains("Published:"))
        {
            releaseDateRaw = releaseDateRaw.Replace("Published: ", "").Trim();
            releaseDate = DateOnly.Parse(releaseDateRaw);
        }
        else
        {
            releaseDate = DateOnly.MinValue;
        }

        var performersContainerElement = await leftColumn.QuerySelectorAsync("ul > li:nth-child(5)");
        if (performersContainerElement == null || !(await performersContainerElement.TextContentAsync()).Contains("Starring"))
        {
            performersContainerElement = await leftColumn.QuerySelectorAsync("ul > li:nth-child(4)");
        }

        var performersElement = await performersContainerElement.QuerySelectorAllAsync("a");
        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersElement)
        {
            var performerUrl = await performerElement.GetAttributeAsync("href");
            var shortName = performerUrl.Substring(performerUrl.LastIndexOf("/") + 1);
            var name = await performerElement.TextContentAsync();
            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        var chapters = new List<Chapter>();
        foreach (var chapterElement in chaptersElement)
        {
            var chapterName = await chapterElement.TextContentAsync();
            chapterName = chapterName.Substring(0, chapterName.IndexOf("(")).Trim();
            var startRaw = await chapterElement.GetAttributeAsync("data-skip");
            var start = int.Parse(startRaw);
            chapters.Add(new Chapter(chapterName, start));
        }

        var tags = new List<SiteTag>();
        foreach (var chapter in chapters)
        {
            tags.Add(new SiteTag(chapter.Name, chapter.Name, string.Empty));
        }

        List<IAvailableFile> availableFiles = new List<IAvailableFile>();

        var availableVideoFiles = await ScrapeSceneVideosAsync(releasePage);
        availableFiles.AddRange(availableVideoFiles);

        var previewImages = await ScrapePreviewImagesAsync(releasePage);
        availableFiles.AddRange(previewImages);

        var trailerVideos = await ScrapeTrailersAsync(releasePage);
        availableFiles.AddRange(trailerVideos);

        var episodePhotosets = await ScrapeEpisodePhotosetsAsync(releasePage, releaseUrl);
        availableFiles.AddRange(episodePhotosets);

        var btsPhotosets = await ScrapeBtsPhotosetsAsync(releasePage, releaseUrl);
        availableFiles.AddRange(btsPhotosets);


        // This would require HTML parsing from search results. Previews seem to be very short and probably automatically generated which
        // makes them not very useful.
        /*var previewVideo = await elementHandle.QuerySelectorAsync("video");
        if (previewVideo != null)
        {
            var previewVideoUrl = await previewVideo.GetAttributeAsync("src");
            var availablePreviewFile = new AvailableVideoFile("video", "preview", string.Empty, previewVideoUrl, null, null, null, null, null);
            availableFiles.Add(availablePreviewFile);
        }*/

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
            availableFiles,
            JsonSerializer.Serialize(new Metadata(chapters)),
            DateTime.Now);

        return scene;
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ScrapePreviewImagesAsync(IPage releasePage)
    {
        var availableFiles = new List<IAvailableFile>();
        var previewElement = await releasePage.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        if (style == null)
        {
            return availableFiles;
        }

        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");
        var availableImageFile = new AvailableImageFile("image", "preview", string.Empty, backgroundImageUrl, null, null, null);
        availableFiles.Add(availableImageFile);
        return availableFiles;
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ScrapeTrailersAsync(IPage releasePage)
    {
        var availableFiles = new List<AvailableVideoFile>();
        var trailerElements = await releasePage.QuerySelectorAllAsync("#download-modal > div.modal-content > div > div > div:nth-child(2) > div > div > div > ul:nth-child(5) > li > a");
        foreach (var trailerElement in trailerElements)
        {
            var downloadDescription = await trailerElement.TextContentAsync();
            downloadDescription = downloadDescription.Trim();

            var pattern = @"(\w+)\s+(\w+)\s+\(([\d.]+\s[GMT]B)\)";

            var match = Regex.Match(downloadDescription, pattern);

            if (match.Success)
            {
                string format = match.Groups[1].Value;     // Any format like MP4
                string resolution = match.Groups[2].Value; // Any resolution like 5k
                string size = match.Groups[3].Value;       // Any file size like 14.08 GB

                var (width, height) = resolution.ToUpperInvariant() switch
                {
                    "5K" => (5120, 2880),
                    "4K" => (3840, 2160),
                    "1080P" => (1920, 1080),
                    "720P" => (1280, 720),
                    "480P" => (720, 480),
                    "360P" => (640, 360),
                    _ => throw new InvalidOperationException($"Unknown quality value {resolution}")
                };
                var fileSize = HumanParser.ParseFileSize(size);

                var trailerUrl = await trailerElement.GetAttributeAsync("href");
                var availableTrailerFile = new AvailableVideoFile("video", "trailer", resolution, trailerUrl, width, height, fileSize, null, null);
                availableFiles.Add(availableTrailerFile);
            }
        }

        availableFiles = availableFiles
            .OrderByDescending(f => f.FileSize)
            .ToList();
        return availableFiles;
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ScrapeBtsPhotosetsAsync(IPage releasePage, string releaseUrl)
    {
        var availableFiles = new List<AvailableGalleryZipFile>();
        var btsPhotoSetPage = await releasePage.Context.NewPageAsync();
        await btsPhotoSetPage.GotoAsync(releaseUrl + "/bts_photoset");

        var btsGalleryDownloadLinks = await btsPhotoSetPage.QuerySelectorAllAsync("#dropdown-menu2 > div > a.dropdown-item");
        foreach (var btsGalleryDownloadLink in btsGalleryDownloadLinks)
        {
            var btsGalleryDownloadUrl = await btsGalleryDownloadLink.GetAttributeAsync("href");
            if (!btsGalleryDownloadUrl.Contains("/download/photoset/"))
            {
                continue;
            }

            var photosetVariant = await btsGalleryDownloadLink.TextContentAsync();
            var components = photosetVariant.Replace("\n", "").Trim().Split(" (");
            var fileSize = HumanParser.ParseFileSize(components[1].Replace(")", "").Trim());
            var availableGalleryFile = new AvailableGalleryZipFile("zip", "gallery-bts", components[0], btsGalleryDownloadUrl, -1, -1, fileSize);
            availableFiles.Add(availableGalleryFile);
        }

        await btsPhotoSetPage.CloseAsync();
        return availableFiles.OrderByDescending(f => f.FileSize).ToList().AsReadOnly();
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ScrapeEpisodePhotosetsAsync(IPage releasePage, string releaseUrl)
    {
        var availableFiles = new List<AvailableGalleryZipFile>();
        var episodePhotoSetPage = await releasePage.Context.NewPageAsync();
        await episodePhotoSetPage.GotoAsync(releaseUrl + "/episode_photoset");
        var galleryDownloadLinks = await episodePhotoSetPage.QuerySelectorAllAsync("#dropdown-menu2 > div > a.dropdown-item");
        foreach (var galleryDownloadLink in galleryDownloadLinks)
        {
            var galleryDownloadUrl = await galleryDownloadLink.GetAttributeAsync("href");
            if (!galleryDownloadUrl.Contains("/download/photoset/"))
            {
                continue;
            }

            var photosetVariant = await galleryDownloadLink.TextContentAsync();
            var components = photosetVariant.Replace("\n", "").Trim().Split(" (");
            var fileSize = HumanParser.ParseFileSize(components[1].Replace(")", "").Trim());
            var availableGalleryFile = new AvailableGalleryZipFile("zip", "gallery-episode", components[0], galleryDownloadUrl, -1, -1, fileSize);
            availableFiles.Add(availableGalleryFile);
        }
        return availableFiles.OrderByDescending(f => f.FileSize).ToList().AsReadOnly();
    }

    private record Metadata(IReadOnlyList<Chapter> Chapters);

    private record Chapter(string Name, int Start);

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        // IPage searchPage = await page.Context.NewPageAsync();

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
            await releasePage.GotoAsync(release.Url);

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
            foreach (var videoDownload in await DownloadSceneVideosAsync(releasePage, downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return videoDownload;
            }
            await foreach (var galleryDownload in DownloadEpisodeGalleryAsync(releasePage, downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return galleryDownload;
            }
            await foreach (var galleryDownload in DownloadBtsGalleryAsync(releasePage, downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return galleryDownload;
            }
            await foreach (var imageDownload in DownloadImagesAsync(releasePage, updatedScrape, existingDownloadEntities, downloadConditions))
            {
                yield return imageDownload;
            }
            foreach (var trailerDownload in await DownloadTrailerAsync(releasePage, updatedScrape, existingDownloadEntities, downloadConditions))
            {
                yield return trailerDownload;
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

    private async Task<IEnumerable<Download>> DownloadSceneVideosAsync(IPage page, DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
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
        var suffix = ".mp4";

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.Variant);

        var cookies = await page.Context.CookiesAsync();
        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        string cookieString = string.Join("; ", cookies.Select(c => $"{c.Name}={c.Value}"));

        var headers = new WebHeaderCollection()
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
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

    private async Task<IEnumerable<Download>> DownloadTrailerAsync(IPage page, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities, DownloadConditions downloadConditions)
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
        var suggestedFileName = uri.LocalPath.Substring(uri.LocalPath.LastIndexOf("/") + 1);
        var suffix = Path.GetExtension(suggestedFileName);

        var fileName = $"{selectedVideo.ContentType} [{selectedVideo.Variant}]{suffix}";

        var cookies = await page.Context.CookiesAsync();
        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        string cookieString = string.Join("; ", cookies.Select(c => $"{c.Name}={c.Value}"));

        var headers = new WebHeaderCollection()
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
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

    private async IAsyncEnumerable<Download> DownloadEpisodeGalleryAsync(IPage page, DownloadConditions downloadConditions, Release release,
        IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableGalleries = release.AvailableFiles
            .OfType<AvailableGalleryZipFile>()
            .Where(d => d is { FileType: "zip", ContentType: "gallery-episode" });
        var selectedGallery = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableGalleries.FirstOrDefault()
            : availableGalleries.LastOrDefault();
        if (selectedGallery == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedGallery))
        {
            yield break;
        }

        var uri = new Uri(selectedGallery.Url);
        var suggestedFileName = uri.LocalPath.Substring(uri.LocalPath.LastIndexOf("/") + 1);
        var suffix = ".zip";

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, "Episode - " + selectedGallery.Variant);

        var cookies = await page.Context.CookiesAsync();
        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        string cookieString = string.Join("; ", cookies.Select(c => $"{c.Name}={c.Value}"));

        var headers = new WebHeaderCollection()
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };
        var fileInfo = await _downloader.TryDownloadAsync(release, selectedGallery, selectedGallery.Url, fileName, headers);
        if (fileInfo == null)
        {
            yield return null;
        }

        var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
        var metadata = new GalleryZipFileMetadata(sha256Sum);
        yield return new Download(release, suggestedFileName, fileInfo.Name, selectedGallery, metadata);
    }

    private async IAsyncEnumerable<Download> DownloadBtsGalleryAsync(IPage page, DownloadConditions downloadConditions, Release release,
    IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableGalleries = release.AvailableFiles
            .OfType<AvailableGalleryZipFile>()
            .Where(d => d is { FileType: "zip", ContentType: "gallery-bts" });
        var selectedGallery = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableGalleries.FirstOrDefault()
            : availableGalleries.LastOrDefault();
        if (selectedGallery == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedGallery))
        {
            yield break;
        }

        var uri = new Uri(selectedGallery.Url);
        var suggestedFileName = uri.LocalPath.Substring(uri.LocalPath.LastIndexOf("/") + 1);
        var suffix = ".zip";

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, "BTS - " + selectedGallery.Variant);

        var cookies = await page.Context.CookiesAsync();
        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        string cookieString = string.Join("; ", cookies.Select(c => $"{c.Name}={c.Value}"));

        var headers = new WebHeaderCollection()
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
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

    private async IAsyncEnumerable<Download> DownloadImagesAsync(IPage page, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities, DownloadConditions downloadConditions)
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

            var cookies = await page.Context.CookiesAsync();
            var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
            string cookieString = string.Join("; ", cookies.Select(c => $"{c.Name}={c.Value}"));

            var headers = new WebHeaderCollection()
            {
                { HttpRequestHeader.Referer, page.Url },
                { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
                { HttpRequestHeader.UserAgent, userAgent },
                { HttpRequestHeader.Cookie, cookieString }
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
        Log.Warning("Automatic login not supported! Log in manually!");
        Console.ReadLine();

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

        /*
        await page.GetByText("Remember me").ClickAsync();

        var usernameInput = page.GetByPlaceholder("Username");
        var passwordInput = page.GetByPlaceholder("Password");

        var signInButton = page.GetByRole(AriaRole.Button, new() { Name = "Login" });

        if (await signInButton.IsVisibleAsync())
        {
            await usernameInput.FillAsync(site.Username);
            await passwordInput.FillAsync(site.Password);
            await signInButton.ClickAsync();
            await page.WaitForLoadStateAsync();



            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }
        */
    }

    private static async Task<int> GetTotalPagesAsync(IPage page)
    {
        var totalPagesStr = await page.Locator("ul.pagination-list > li:not(.is-hidden-mobile)").Last.TextContentAsync();
        totalPagesStr = totalPagesStr.Replace("\n", "").Trim();
        var totalPages = int.Parse(totalPagesStr);
        return totalPages;
    }

    private static async Task GoToPageAsync(IPage page, Site site, int targetPageNumber)
    {
        await page.GotoAsync($"{site.Url}&page={targetPageNumber}");
    }

    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(Site site, IElementHandle currentRelease)
    {
        var url = await currentRelease.GetAttributeAsync("href");
        var number = url.Substring(url.LastIndexOf('/') + 1);
        return new ReleaseIdAndUrl(number, url);
    }

    private static async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var liElement = await page.QuerySelectorAsync("li:has(span.icon > i.fa-calendar)");
        var rawContent = await liElement.TextContentAsync();
        rawContent = rawContent.Replace("\n", "").Trim().Replace("Published: ", "");

        return DateOnly.Parse(rawContent);
    }

    private static async Task<string> ScrapeTitleAsync(IPage page)
    {
        var titleMeta = await page.QuerySelectorAsync("meta[itemprop='name']");
        var title = await titleMeta.GetAttributeAsync("content");
        return title.Trim();
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
        var durationElement = await page.QuerySelectorAsync("span.vjs-duration-display");
        var rawContent = await durationElement.TextContentAsync();
        return HumanParser.ParseDuration(rawContent);
    }

    private static async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        var targetText = "Episode Summary";
        var h5Element = await page.QuerySelectorAsync($"//h5[text()='{targetText}']");
        if (h5Element == null)
        {
            Log.Warning("Could not find element with text {TargetText}", targetText);
            return string.Empty;
        }

        var parentElement = await h5Element.QuerySelectorAsync("xpath=..");
        var description = await parentElement.TextContentAsync();
        description = description.Replace(targetText, "").Replace("\n", "").Trim();
        return description;
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ScrapeSceneVideosAsync(IPage page)
    {
        var sizesByResolution = new Dictionary<string, string>();
        var formatsByResolution = new Dictionary<string, string>();

        // Note: downloads are limited to 15 per week so we cannot download these. We just scrape the sizes.
        try
        {
            var downloadsElements = await page.QuerySelectorAllAsync("#download-modal > div.modal-content > div > div > div:nth-child(2) > div > div > div > ul:nth-child(3) > li > a");
            foreach (var downloadsElement in downloadsElements)
            {
                var downloadDescription = await downloadsElement.TextContentAsync();
                downloadDescription = downloadDescription.Trim();

                var pattern = @"(\w+)\s+(\w+)\s+\(([\d.]+\s[GMT]B)\)";

                var match = Regex.Match(downloadDescription, pattern);

                if (match.Success)
                {
                    string format = match.Groups[1].Value;     // Any format like MP4
                    string resolution = match.Groups[2].Value; // Any resolution like 5k
                    string size = match.Groups[3].Value;       // Any file size like 14.08 GB

                    sizesByResolution.Add(resolution, size);
                    formatsByResolution.Add(resolution, format);
                }

            }
        }
        catch (Exception ex)
        {
            Log.Warning(ex, "Could not find downloads element");
        }


        var availableFiles = new List<AvailableVideoFile>();
        var qualitySelectors = await page.QuerySelectorAllAsync(".vjs-quality-selector .vjs-menu ul li");
        foreach (var qualitySelector in qualitySelectors)
        {
            // These are hidden and blocked by other elements. Click through JavaScript.
            await qualitySelector.EvaluateHandleAsync("el => el.click()");

            var quality = await qualitySelector.TextContentAsync();
            // These can contain text like "5k, selected"
            quality = quality.Substring(0, quality.IndexOf(","));

            var videoPlayerElement = await page.QuerySelectorAsync("video#player_html5_api");
            var source = await videoPlayerElement.GetAttributeAsync("src");

            var (width, height) = quality.ToUpperInvariant() switch
            {
                "5K" => (5120, 2880),
                "4K" => (3840, 2160),
                "1080P" => (1920, 1080),
                "720P" => (1280, 720),
                "480P" => (720, 480),
                "360P" => (640, 360),
                _ => throw new InvalidOperationException($"Unknown quality value {quality}")
            };

            var size = sizesByResolution.TryGetValue(quality, out var sizeStr) ? HumanParser.ParseFileSize(sizeStr) : -1;
            var format = formatsByResolution.TryGetValue(quality, out var formatStr) ? formatStr : "mp4";

            availableFiles.Add(
                new AvailableVideoFile(
                    "video",
                    "scene",
                    $"{format} {width}x{height}",
                    source,
                    width,
                    height,
                    size,
                    -1,
                    format)
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
