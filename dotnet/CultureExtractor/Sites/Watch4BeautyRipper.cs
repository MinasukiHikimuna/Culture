using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using CultureExtractor;
using Microsoft.Playwright;
using Serilog;
using System.Globalization;
using System.Net;
using System.Text;
using System.Collections.Immutable;
using CultureExtractor.Exceptions;
using CultureExtractor.Sites;
using System.Text.Json;

[Site("watch4beauty")]
public class Watch4BeautyRipper : IYieldingScraper
{
    private static readonly HttpClient Client = new();

    private static string UpdatesUrl(Site site, int pageNumber) => $"{site.Url}/updates";

    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloader _downloader;
    private readonly IDownloadPlanner _downloadPlanner;

    public Watch4BeautyRipper(
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

    private record W4BUpdate(Watch4BeautyModels.Updates.Latest Raw, UpdateType UpdateType, string ReleaseShortName, string ReleaseUrl)
    {
    }

    private enum UpdateType
    {
        Issue,
        Magazine
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        var requests = await CaptureRequestsAsync(site, page);
        SetHeadersFromActualRequest(requests);

        int pageNumber = 0;
        int pages = 0;

        bool lastPage = false;

        var releasePage = await page.Context.NewPageAsync();

        try
        {
            while (!lastPage)
            {
                pageNumber++;
                await Task.Delay(5000);

                Watch4BeautyModels.Updates.RootObject updatesPage;
                try
                {
                    updatesPage = await GetMoviesPageAsync(site, pageNumber);
                }
                catch (Exception ex)
                {
                    Log.Error(ex, $"Error while fetching page {pageNumber}");
                    continue;
                }

                // Only calculate the total number of pages after fetching the first page
                if (updatesPage.latest.Length == 0)
                {
                    break;
                }

                Log.Information($"Page {pageNumber} contains {updatesPage.latest.Length} releases");

                var w4bUpdates = new List<W4BUpdate>();
                foreach (var update in updatesPage.latest)
                {
                    if (update.issue_id != 0)
                    {
                        var issueUrl = $"{site.Url}/updates/{update.issue_simple_title}";
                        w4bUpdates.Add(new W4BUpdate(update, UpdateType.Issue, update.issue_id.ToString(), issueUrl));
                    }
                    else if (update.magazine_id != 0)
                    {
                        var magazineUrl = $"{site.Url}/stories/{update.magazine_simple_title}";
                        w4bUpdates.Add(new W4BUpdate(update, UpdateType.Magazine, update.magazine_id.ToString(), magazineUrl));
                    }
                    else
                    {
                        Log.Error("Unknown update type: {Update}", update);
                    }
                }

                var updates = w4bUpdates
                    .ToDictionary(r => r.ReleaseShortName, r => r);
                var existingReleases = await _repository
                    .GetReleasesAsync(site.ShortName, updates.Keys.ToList());
                var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);
                var updatesToBeScraped = updates
                    .Where(g => !existingReleasesDictionary.ContainsKey(g.Key) || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated)
                    .Select(g => g.Value)
                    .ToList();

                foreach (var update in updatesToBeScraped)
                {
                    await Task.Delay(1000);
                    var shortName = update.ReleaseShortName;

                    Release? scene = null;
                    try
                    {
                        var releaseGuid = existingReleasesDictionary.TryGetValue(shortName, out var existingRelease)
                            ? existingRelease.Uuid
                            : UuidGenerator.Generate();
                        scene = await ScrapeSceneAsync(update, releasePage, site, shortName, update.ReleaseUrl, releaseGuid);
                    }
                    catch (ExtractorException ex)
                    {
                        switch (ex.ExtractorRetryMode)
                        {
                            case ExtractorRetryMode.RetryLogin:
                                await LoginAsync(site, page);
                                continue;
                            case ExtractorRetryMode.Retry:
                                continue;
                            case ExtractorRetryMode.Skip:
                                Log.Error(ex, $"Error while scraping scene, skipping: {shortName}");
                                continue;
                            default:
                            case ExtractorRetryMode.Abort:
                                throw;
                        }
                    }

                    if (scene != null)
                    {
                        yield return scene;
                    }
                    else
                    {
                        Log.Error("Unable to scrape {Site} scene {ShortName} on page {Page}",
                            site.Name, shortName, pageNumber);
                    }
                }
            }
        }
        finally
        {
            await releasePage.CloseAsync();
        }
    }

    private async Task<Release> ScrapeSceneAsync(W4BUpdate update, IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid)
    {

        try
        {
            await releasePage.GotoAsync(releaseUrl, new PageGotoOptions { Timeout = 10000 });
        }
        catch (System.TimeoutException)
        {
            await releasePage.GotoAsync(releaseUrl, new PageGotoOptions { Timeout = 10000 });
        }
        
        await Task.Delay(3000);
        await releasePage.WaitForLoadStateAsync();

        // Login if necessary
        if (await LoginAsync(site, releasePage))
        {
            await releasePage.GotoAsync(releaseUrl);
            await Task.Delay(3000);
            await releasePage.WaitForLoadStateAsync();
        }

        var releaseDate = update.UpdateType == UpdateType.Issue
            ? DateOnly.FromDateTime(update.Raw.issue_datetime)
            : DateOnly.FromDateTime(update.Raw.magazine_datetime);
        var title = update.UpdateType == UpdateType.Issue
            ? update.Raw.issue_title
            : update.Raw.magazine_title;
        var description = update.UpdateType == UpdateType.Issue
            ? update.Raw.issue_text
            : update.Raw.magazine_text;

        var modelsApiUrl = update.UpdateType == UpdateType.Issue
            ? IssuesModelsApiUrl(site, update.Raw.issue_simple_title)
            : MagazinesModelsApiUrl(site, update.Raw.magazine_simple_title);
        using var response = await Client.GetAsync(modelsApiUrl);
        if (response.StatusCode != HttpStatusCode.OK)
        {
            throw new InvalidOperationException($"Could not read models API response:{Environment.NewLine}Url={modelsApiUrl}{Environment.NewLine}StatusCode={response.StatusCode}{Environment.NewLine}ReasonPhrase={response.ReasonPhrase}");
        }

        var json = await response.Content.ReadAsStringAsync();
        var issues = JsonSerializer.Deserialize<Watch4BeautyModels.Models.Issues[]>(json);
        if (issues == null)
        {
            throw new InvalidOperationException($"Could not read models API response: {json}");
        }

        var performers = issues.Length == 1 
            ? issues[0].Models.Select(m => new SitePerformer(m.model_id.ToString(), m.model_nickname, $"{site.Url}/models/{m.model_simple_nickname}")).ToList()
            : new List<SitePerformer>();

        var baseCoverUrl = "https://mh-c75c2d6726.watch4beauty.com/production/" + releaseDate.ToString("yyyyMMdd");
        var wideCoverUrl = baseCoverUrl + (update.UpdateType == UpdateType.Issue
            ? "-issue-cover-2560.jpg"
            : "-magazine-cover-2560.jpg");
        var coverUrl = baseCoverUrl + (update.UpdateType == UpdateType.Issue
            ? "-issue-cover-wide-2560.jpg"
            : "-magazine-cover-wide-2560.jpg");

        var availableImageFiles = new List<IAvailableFile>
        {
            new AvailableImageFile("image", "scene", "cover", coverUrl, null, null, null),
            new AvailableImageFile("image", "scene", "wide-cover", wideCoverUrl, null, null, null)
        };

        var availableFiles = await ParseAvailableDownloadsAsync(site, releasePage);

        var downloadButton = await releasePage.QuerySelectorAsync("div.action-fix > div > a:nth-child(2)") ?? throw new ExtractorException(ExtractorRetryMode.Retry, "Download button not found");

        return new Release(
            releaseGuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            releaseUrl,
            description,
            double.NaN,
            performers,
            new List<SiteTag>(),
            availableFiles
                .Concat(availableImageFiles)
                .ToList(),
            "{}",
            DateTime.Now);
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableDownloadsAsync(Site site, IPage releasePage)
    {
        // For some reason the download button is not clickable with Playwright.
        await releasePage.EvaluateAsync(@"() => {
            const downloadButton = document.querySelector('div.action-fix > div > a:nth-child(2)');
            if (downloadButton) {
                downloadButton.click();
            } else {
                throw new Error('Download button not found');
            }
        }");

        var downloadElements = await releasePage.QuerySelectorAllAsync("a.button[title='Download']");

        var availableFiles = new List<IAvailableFile>();
        var videoDownloadElements = new List<IElementHandle>();
        var galleryDownloadElements = new List<IElementHandle>();

        foreach (var downloadElement in downloadElements)
        {
            var downloadUrl = await downloadElement.GetAttributeAsync("href");
            if (downloadUrl.Contains(".mp4"))
            {
                videoDownloadElements.Add(downloadElement);
            }
            else if (downloadUrl.Contains(".zip"))
            {
                galleryDownloadElements.Add(downloadElement);
            }
            else
            {
                throw new ExtractorException(ExtractorRetryMode.Abort, $"Unknown download type: {downloadUrl}");
            }
        }

        // Sort videoDownloadElements to ensure the one without "-hd" comes first
        videoDownloadElements.Sort((a, b) =>
        {
            var aUrl = a.GetAttributeAsync("href").Result;
            var bUrl = b.GetAttributeAsync("href").Result;
            bool aIsHd = aUrl.Contains("-hd");
            bool bIsHd = bUrl.Contains("-hd");

            return aIsHd.CompareTo(bIsHd);
        });

        for (int i = 0; i < videoDownloadElements.Count; i++)
        {
            var videoDownloadElement = videoDownloadElements[i];
            var downloadUrl = await videoDownloadElement.GetAttributeAsync("href");
            var quality = i == 0 ? "high" : "low";
            var availableFile = new AvailableVideoFile("video", "scene", quality, $"{site.Url}{downloadUrl}", null, null, null, null, null);
            availableFiles.Add(availableFile);
        }

        foreach (var galleryDownloadElement in galleryDownloadElements)
        {
            var downloadUrl = await galleryDownloadElement.GetAttributeAsync("href");
            var availableFile = new AvailableGalleryZipFile("gallery", "scene", "", $"{site.Url}{downloadUrl}", null, null, null);
            availableFiles.Add(availableFile);
        }

        return availableFiles;
    }



    private static string UpdatesApiUrl(Site site, int pageNumber) => $"{site.Url}/api/updates?skip={(pageNumber - 1) * 50}";
    private static string IssuesModelsApiUrl(Site site, string slug) => $"{site.Url}/api/issues/{slug}/models";
    private static string MagazinesModelsApiUrl(Site site, string slug) => $"{site.Url}/api/magazines/{slug}/models";

    private static async Task<Watch4BeautyModels.Updates.RootObject> GetMoviesPageAsync(Site site, int pageNumber)
    {
        var updatesApiUrl = UpdatesApiUrl(site, pageNumber);

        using var response = await Client.GetAsync(updatesApiUrl);
        if (response.StatusCode != HttpStatusCode.OK)
        {
            throw new InvalidOperationException($"Could not read updates API response:{Environment.NewLine}Url={updatesApiUrl}{Environment.NewLine}StatusCode={response.StatusCode}{Environment.NewLine}ReasonPhrase={response.ReasonPhrase}");
        }

        var json = await response.Content.ReadAsStringAsync();

        var updates = JsonSerializer.Deserialize<Watch4BeautyModels.Updates.RootObject>(json);
        if (updates == null)
        {
            throw new InvalidOperationException("Could not read movies API response: " + json);
        }

        return updates;
    }

    private static async Task<List<IRequest>> CaptureRequestsAsync(Site site, IPage page)
    {
        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });

        await page.GotoAsync(UpdatesUrl(site, 1));
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        await page.UnrouteAsync("**/*");
        return requests;
    }

    private static Dictionary<string, string> SetHeadersFromActualRequest(IList<IRequest> requests)
    {
        var updatesRequest = requests.FirstOrDefault(r => r.Url.StartsWith("https://www.watch4beauty.com/api/updates"));
        if (updatesRequest == null)
        {
            var requestUrls = requests.Select(r => r.Url + Environment.NewLine).ToList();
            throw new InvalidOperationException($"Could not read galleries API request from following requests:{Environment.NewLine}{string.Join("", requestUrls)}");
        }

        Client.DefaultRequestHeaders.Clear();
        foreach (var key in updatesRequest.Headers.Keys)
        {
            Client.DefaultRequestHeaders.Add(key, updatesRequest.Headers[key]);
        }

        return updatesRequest.Headers;
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


    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        var downloadedReleases = 0;
        foreach (var release in releases)
        {
            await page.ReloadAsync();
            await LoginAsync(site, page);

            var requests = await CaptureRequestsAsync(site, page);
            var headers = SetHeadersFromActualRequest(requests);
            var convertedHeaders = ConvertHeaders(headers);

            var releaseDownloadPlan = PlanDownloads(release, downloadConditions);
            var releaseMissingDownloadsPlan = await _downloadPlanner.PlanMissingDownloadsAsync(releaseDownloadPlan);

            if (!releaseMissingDownloadsPlan.AvailableFiles.Any())
            {
                continue;
            }

            var existingDownloadEntities = await _downloadPlanner.GetExistingDownloadsAsync(release);
            Log.Information("Downloading: {Site} - {ReleaseDate} - {Release} [{Uuid}]", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name, release.Uuid);
            foreach (var videoDownload in await DownloadVideosAsync(downloadConditions, release, existingDownloadEntities, convertedHeaders))
            {
                yield return videoDownload;
            }
            foreach (var galleryDownload in await DownloadGalleriesAsync(downloadConditions, release, existingDownloadEntities, convertedHeaders))
            {
                yield return galleryDownload;
            }
            await foreach (var imageDownload in DownloadImagesAsync(release, existingDownloadEntities, convertedHeaders))
            {
                yield return imageDownload;
            }

            downloadedReleases++;
            Log.Information($"{downloadedReleases} releases downloaded in this session.");
        }
    }

    private static WebHeaderCollection ConvertHeaders(Dictionary<string, string> headers)
    {
        var convertedHeaders = new WebHeaderCollection();
        foreach (var header in headers)
        {
            convertedHeaders.Add(header.Key, header.Value);
        }
        return convertedHeaders;
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

    private async Task<IEnumerable<Download>> DownloadVideosAsync(DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities, WebHeaderCollection headers)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "scene" });
        var selectedFile = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableVideos.FirstOrDefault()
            : availableVideos.LastOrDefault();
        if (selectedFile == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedFile))
        {
            return new List<Download>();
        }

        var uri = new Uri(selectedFile.Url);
        var suggestedFileName = Path.GetFileName(uri.LocalPath);
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedFile.Variant);

        var fileInfo = await _downloader.TryDownloadAsync(release, selectedFile, selectedFile.Url, fileName, headers);
        if (fileInfo == null)
        {
            return new List<Download>();
        }

        var videoHashes = Hasher.Phash(@"""" + fileInfo.FullName + @"""");
        return new List<Download>
        {
            new(release, suggestedFileName, fileInfo.Name, selectedFile, videoHashes)
        };
    }

    private async Task<IEnumerable<Download>> DownloadGalleriesAsync(DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities, WebHeaderCollection headers)
    {
        var availableFiles = release.AvailableFiles
            .OfType<AvailableGalleryZipFile>()
            .Where(d => d is { FileType: "gallery", ContentType: "scene" });
        var selectedFile = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableFiles.FirstOrDefault()
            : availableFiles.LastOrDefault();
        if (selectedFile == null || !_downloadPlanner.NotDownloadedYet(existingDownloadEntities, selectedFile))
        {
            return new List<Download>();
        }

        var uri = new Uri(selectedFile.Url);
        var suggestedFileName = Path.GetFileName(uri.LocalPath);
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedFile.Variant);

        var fileInfo = await _downloader.TryDownloadAsync(release, selectedFile, selectedFile.Url, fileName, headers);
        if (fileInfo == null)
        {
            return new List<Download>();
        }

        var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
        var metadata = new GalleryZipFileMetadata(sha256Sum);
        return new List<Download>
        {
            new(release, suggestedFileName, fileInfo.Name, selectedFile, metadata)
        };
    }

    private async IAsyncEnumerable<Download> DownloadImagesAsync(Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities, WebHeaderCollection headers)
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

            var fileInfo = await _downloader.TryDownloadAsync(release, imageFile, imageFile.Url, suggestedFileName, headers);
            if (fileInfo == null)
            {
                yield break;
            }

            var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
            var metadata = new ImageFileMetadata(sha256Sum);
            yield return new Download(release, $"{imageFile.ContentType}.jpg", fileInfo.Name, imageFile, metadata);
        }
    }

    private async Task<bool> LoginAsync(Site site, IPage page)
    {
        var enterButton = page.GetByText("Yes, enter");
        if (await enterButton.IsVisibleAsync())
        {
            await enterButton.ClickAsync();
        }

        var loginMenuButton = page.GetByRole(AriaRole.Link, new() { Name = "Login", Exact = true });
        if (await loginMenuButton.IsVisibleAsync())
        {
            await loginMenuButton.ClickAsync();

            var usernameInput = page.GetByLabel("Username");
            var passwordInput = page.GetByLabel("Password");
            var loginButton = page.GetByRole(AriaRole.Button, new() { Name = "Login" });

            await usernameInput.ClickAsync();
            await usernameInput.FillAsync(site.Username);
            await passwordInput.ClickAsync();
            await passwordInput.FillAsync(site.Password);
            await loginButton.ClickAsync();

            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

            Log.Information($"Logged into {site.Name}.");
            return true;
        }

        return false;
    }
}
