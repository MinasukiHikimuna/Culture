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
using System.Web;
using System.Globalization;
using System.Text;

namespace CultureExtractor.Sites;

[Site("meanawolf")]
public class MeanaWolfRipper : IYieldingScraper
{
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloader _downloader;
    private readonly IDownloadPlanner _downloadPlanner;

    public MeanaWolfRipper(
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

        var totalPages = await GetTotalPagesAsync(page, site);

        for (var pageNumber = 1; pageNumber <= totalPages; pageNumber++)
        {
            await GoToPageAsync(page, site, pageNumber);

            var releaseHandles = await page.Locator("div.videoBlock").ElementHandlesAsync();

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


    public class Downloads
    {
        public string path { get; set; }
        public string showplay { get; set; }
        public string showdownload { get; set; }
        public string movie_width { get; set; }
        public string movie_height { get; set; }
        public string name { get; set; }
        public string type { get; set; }
        public string vtt_file { get; set; }
    }


    private async Task<Release> ScrapeSceneAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid, IElementHandle elementHandle)
    {
        await releasePage.GotoAsync(releaseUrl);
        await releasePage.WaitForLoadStateAsync();
        if (await NeedsLoginAsync(site, releasePage))
        {
            await LoginAsync(site, releasePage);
        }

        var releaseDate = await ScrapeReleaseDateAsync(releasePage);
        var duration = await ScrapeDurationAsync(releasePage);
        var description = await ScrapeDescriptionAsync(releasePage);
        var title = await ScrapeTitleAsync(releasePage);
        var performers = await ScrapePerformersAsync(releasePage);
        var tags = await ScrapeTagsAsync(releasePage);

        var scriptElement = await releasePage.QuerySelectorAsync("body > div.bodyArea.topSpace > div.trailerArea > div.trailer > div > div > script:nth-child(7)");
        var scriptRaw = await scriptElement.InnerTextAsync();
        var pattern = @"movie\[""(.*)""\]\[("".*"")] = (.*);";
        var matches = Regex.Matches(scriptRaw, pattern);

        var availableVideoFiles = new List<IAvailableFile>();
        var availableTrailerFiles = new List<IAvailableFile>();
        foreach (Match match in matches)
        {
            var key = match.Groups[1].Value;
            var id = match.Groups[2].Value;
            var jsonValue = match.Groups[3].Value;

            if (key == "HLS")
            {
                continue;
            }

            var pathPattern = @"path:""(.*)""";
            var videoWidthPattern = @",movie_width:'(\d+)'";
            var videoHeightPattern = @",movie_height:'(\d+)'";

            var pathMatch = Regex.Match(jsonValue, pathPattern);
            var videoWidthMatch = Regex.Match(jsonValue, videoWidthPattern);
            var videoHeightMatch = Regex.Match(jsonValue, videoHeightPattern);

            var path = pathMatch.Groups[1].Value;
            int? videoWidth = !string.IsNullOrWhiteSpace(videoWidthMatch.Groups[1].Value)
                ? int.Parse(videoWidthMatch.Groups[1].Value)
                : null;
            int? videoHeight = !string.IsNullOrWhiteSpace(videoHeightMatch.Groups[1].Value)
                ? int.Parse(videoHeightMatch.Groups[1].Value)
                : null;

            if (key == "trailer")
            {
                var availableTrailerFile = new AvailableVideoFile("video", "trailer", videoHeight + "p", path, videoWidth, videoHeight, null, null, null);
                availableTrailerFiles.Add(availableTrailerFile);
            } 
            else
            {
                var availableVideoFile = new AvailableVideoFile("video", "scene", key, path, videoWidth, videoHeight, null, null, null);
                availableVideoFiles.Add(availableVideoFile);
            }
        }

        var posterPattern = @"useimage = ""(.*)""";
        var posterMatch = Regex.Match(scriptRaw, posterPattern);
        var posterUrl = posterMatch.Groups[1].Value;
        var availablePosterFile = new AvailableImageFile("image", "poster", string.Empty, posterUrl, null, null, null);
        var availablePosterFiles = new List<IAvailableFile> { availablePosterFile };

        var availablePreviewVideoFiles = new List<IAvailableFile>();
        var previewVideo = await elementHandle.QuerySelectorAsync("div.item-video-thumb");
        if (previewVideo != null)
        {
            var previewVideoUrl = await previewVideo.GetAttributeAsync("data-videosrc");
            var availablePreviewVideoFile = new AvailableImageFile("video", "preview", string.Empty, previewVideoUrl, null, null, null);
            availablePreviewVideoFiles.Add(availablePreviewVideoFile);
        }

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
            availableVideoFiles.Concat(availableTrailerFiles).Concat(availablePosterFiles).Concat(availablePreviewVideoFiles).ToList(),
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

            string encodedString = HttpUtility.UrlEncode(RemoveDiacritics(release.Name));
            IElementHandle searchResult = null;
            for (var searchPageIndex = 1; searchPageIndex < 10; searchPageIndex++)
            {
                var searchUrl = $"/search.php?query={encodedString}&page={searchPageIndex}";
                await searchPage.GotoAsync(searchUrl);
                await searchPage.WaitForLoadStateAsync();
                var searchResults = await searchPage.Locator("div.videoBlock").ElementHandlesAsync();
                if (searchResults.Count == 0)
                {
                    break;
                }

                foreach (var result in searchResults)
                {
                    var dataSetId = await result.GetAttributeAsync("data-setid");
                    if (dataSetId != null && dataSetId.EndsWith(release.ShortName))
                    {
                        searchResult = result;
                        break; // Exit the loop once we find the first match.
                    }
                }

                if (searchResult != null)
                {
                    break;
                }
            }

            if (searchResult == null)
            {
                Log.Warning("Could not find {Release} on {Site}", release.Name, site.Name);
                continue;
            }

            IPage releasePage = await page.Context.NewPageAsync();

            Release? updatedScrape;
            try
            {
                updatedScrape = await ScrapeSceneAsync(releasePage, site, release.ShortName, release.Url, release.Uuid, searchResult);
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
            foreach (var previewDownload in await DownloadPreviewsAsync(downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return previewDownload;
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

    private static string RemoveDiacritics(string text)
    {
        var normalizedString = text.Normalize(NormalizationForm.FormD);
        var stringBuilder = new StringBuilder();

        foreach (var c in normalizedString)
        {
            var unicodeCategory = CharUnicodeInfo.GetUnicodeCategory(c);
            if (unicodeCategory != UnicodeCategory.NonSpacingMark)
            {
                stringBuilder.Append(c);
            }
        }

        return stringBuilder.ToString().Normalize(NormalizationForm.FormC);
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

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.ContentType);

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

    private async Task<IEnumerable<Download>> DownloadPreviewsAsync(DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "preview" });
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
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.ContentType);

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
            var performersStr = release.Performers.Count() > 1
                ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
                  release.Performers.Last().Name
                : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
            var fileName = ReleaseNamer.Name(release, suffix, performersStr, imageFile.ContentType);
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

    private async Task<bool> NeedsLoginAsync(Site site, IPage page)
    {
        return await page.Locator("a.join_btn").IsVisibleAsync();
    }

    private async Task LoginAsync(Site site, IPage page)
    {
        if (await NeedsLoginAsync(site, page))
        {
            Log.Warning("Automatic login not supported! Log in manually!");
            Console.ReadLine();

            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }

        /*var signInButton = page.GetByRole(AriaRole.Button, new() { Name = "Sign In" });
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
        }*/
    }

    private static async Task<int> GetTotalPagesAsync(IPage page, Site site)
    {
        var pageElements = await page.QuerySelectorAllAsync("div.pagination ul li.hide_mobile");
        var lastPageElement = pageElements.Last();
        var lastPageText = await lastPageElement.InnerTextAsync();
        if (!int.TryParse(lastPageText, out int lastPageNumber))
        {
            throw new InvalidOperationException($"Could not parse last page number from {lastPageText}");
        }

        return lastPageNumber;
    }

    private async Task GoToPageAsync(IPage page, Site site, int targetPageNumber)
    {
        await page.GotoAsync($"{site.Url}/categories/movies_{targetPageNumber}_d.html");
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
        var dataSetIdText = await currentRelease.GetAttributeAsync("data-setid");

        var linkElement = await currentRelease.QuerySelectorAsync("a");
        var url = await linkElement.GetAttributeAsync("href");

        return new ReleaseIdAndUrl(dataSetIdText, url);
    }

    private static async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var releaseDateRaw = await page.Locator("body > div.bodyArea.topSpace > div.trailerArea > div.videoContent > ul > li:nth-child(3)").TextContentAsync();
        if (!releaseDateRaw.ToUpperInvariant().Contains("ADDED:"))
        {
            // Try alternative selector as some sites have PHOTOS element and others do not.
            releaseDateRaw = await page.Locator("body > div.bodyArea.topSpace > div.trailerArea > div.videoContent > ul > li:nth-child(2)").TextContentAsync();
        }

        releaseDateRaw = releaseDateRaw.Replace("ADDED: ", "");
        return DateOnly.Parse(releaseDateRaw);
    }

    private static async Task<string> ScrapeTitleAsync(IPage page)
    {
        var title = await page.Locator("body > div.bodyArea.topSpace > div.trailerArea > h1").TextContentAsync();
        return title;
    }

    private static async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page)
    {
        var castElements = await page.Locator("body > div.bodyArea.topSpace > div.trailerArea > div.videoContent > ul > li:nth-child(4) > a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        performers.Add(new SitePerformer("meanawolf", "Meana Wolf", "https://meanawolf.com/models/MeanaWolf.html"));
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");
            var castName = await castElement.TextContentAsync();
            var performer = new SitePerformer(castName.ToLower().Replace(" ", "-"), castName, castUrl);

            // Check if performer with the same id already exists in the list
            if (!performers.Any(p => p.ShortName == performer.ShortName))
            {
                performers.Add(performer);
            }
        }

        return performers.AsReadOnly();
    }

    private static async Task<IList<SiteTag>> ScrapeTagsAsync(IPage page)
    {
        var tagElements = await page.Locator("body > div.bodyArea.topSpace > div.trailerArea > div.videoContent > ul > li:nth-child(6) > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagName = await tagElement.TextContentAsync();
            var tagId = tagName.ToLower().Replace(" ", "-");
            tags.Add(new SiteTag(tagId, tagName.Trim(), tagUrl));
        }
        return tags;
    }

    private static async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var durationRaw = await page.Locator("body > div.bodyArea.topSpace > div.trailerArea > div.videoContent > ul > li:nth-child(1)").TextContentAsync();
        durationRaw = durationRaw.Replace("RUNTIME: ", "");
        return HumanParser.ParseDuration(durationRaw);
    }

    private static async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        var description = await page.Locator("body > div.bodyArea.topSpace > div.trailerArea > div.trailerContent > p").TextContentAsync();
        return description;
    }
}
