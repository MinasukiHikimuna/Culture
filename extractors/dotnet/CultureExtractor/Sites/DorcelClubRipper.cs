using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;
using CultureExtractor.Models;
using System.Net;
using Polly;
using System.Collections.Immutable;
using System.Web;
using Polly.Retry;

namespace CultureExtractor.Sites;

[Site("dorcelclub")]
[Site("itspov")]
public class DorcelClubRipper : IYieldingScraper
{
    private static readonly HttpClient Client = new();

    private readonly ICaptchaSolver _captchaSolver;
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloadPlanner _downloadPlanner;
    private readonly IDownloader _downloader;

    public DorcelClubRipper(ICaptchaSolver captchaSolver, IPlaywrightFactory playwrightFactory, IRepository repository, IDownloadPlanner downloadPlanner, IDownloader downloader)
    {
        _captchaSolver = captchaSolver;
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _downloadPlanner = downloadPlanner;
        _downloader = downloader;
    }

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        var requests = await CaptureRequestsAsync(site, page);
        SetHeadersFromActualRequest(requests);
        await foreach (var scene in ScrapeScenesAsync(site, page, scrapeOptions))
        {
            yield return scene;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        await GoToVideosAsync(page);
        await page.WaitForLoadStateAsync();

        IPage? releasePage = await page.Context.NewPageAsync();

        try
        {
            while (await IsMoreAvailableAsync(page))
            {
                var pageElements = await page.QuerySelectorAllAsync("div#scenes div.list div.items");
                var pageNumber = pageElements.Count;

                var releaseHandles = await page.Locator($"div.items[data-page='{pageNumber}'] > div.scene").ElementHandlesAsync();

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

                Log.Information($"Page {pageNumber} contains {releaseHandles.Count} releases");

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


                    try
                    {
                        await releasePage.GotoAsync(sceneToBeScraped.Url);
                        await ClickOnEnterIfVisibleAsync(page);
                        scene = await ScrapeSceneAsync(releasePage, site, sceneToBeScraped.ShortName, sceneToBeScraped.Url, releaseGuid);
                    }
                    catch (Exception ex)
                    {
                        Log.Error(ex, $"Failed to scrape scene {sceneToBeScraped.Url}");
                    }

                    if (scene != null)
                    {
                        yield return scene;
                    }
                }

                if (await IsMoreAvailableAsync(page))
                {
                    await ClickSeeMoreAsync(page);
                }
            }
        }
        finally
        {
            releasePage?.CloseAsync();
        }
    }

    private static Task<bool> IsMoreAvailableAsync(IPage page)
    {
        ILocator seeMoreLocator = SeeMoreLocator(page);
        return seeMoreLocator.IsVisibleAsync();
    }

    private static async Task ClickSeeMoreAsync(IPage page)
    {
        ILocator seeMoreLocator = SeeMoreLocator(page);
        await seeMoreLocator.ClickAsync();
    }

    private static ILocator SeeMoreLocator(IPage page)
    {
        return page.GetByRole(AriaRole.Button, new() { NameString = "See more" });
    }

    private static async Task<Release> ScrapeSceneAsync(IPage releasePage, Site site, string releaseShortName, string releaseUrl, Guid releaseGuid)
    {
        await Task.Delay(3000);
        await releasePage.WaitForLoadStateAsync();

        var releaseDateRaw = await releasePage.Locator("div.right > span.publish_date").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw);

        var durationRaw = await releasePage.Locator("div.right > span.duration").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await releasePage.Locator("h1.title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performersRaw = await releasePage.Locator("div.player > div.actress > a").ElementHandlesAsync();

        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersRaw)
        {
            var performerUrl = await performerElement.GetAttributeAsync("href");
            var shortName = performerUrl.Replace("/en/pornstar/", "");
            var name = await performerElement.TextContentAsync();
            performers.Add(new SitePerformer(shortName, name, performerUrl, "{}"));
        }

        var fullTextLocator = releasePage.Locator("div.content-description > div.content-text > span.full");
        var briefDescriptionLocator = releasePage.Locator("div.content-description > div.content-text");

        string description = string.Empty;
        if (await fullTextLocator.IsVisibleAsync())
        {
            description = await fullTextLocator.TextContentAsync();
        }
        else if (await briefDescriptionLocator.IsVisibleAsync())
        {
            description = await briefDescriptionLocator.TextContentAsync();
        }
        description = description.Replace("\n", "").Trim();

        var posterElement = await releasePage.Locator("div.player_video_container div.poster").ElementHandleAsync();
        var posterStyle = await posterElement.GetAttributeAsync("style");
        var posterUrl = ParseUrlFromStyle(posterStyle);
        var availablePosterFile = new AvailableImageFile("image", "scene", "poster", posterUrl, null, null, null);

        var availableVideoFiles = await ParseAvailableDownloadsAsync(releasePage);

        return new Release(
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
            new List<SiteTag>(),
            availableVideoFiles
                .Concat(new List<IAvailableFile> { availablePosterFile })
                .ToList(),
            "{}",
            DateTime.Now);
    }

    private static string ParseUrlFromStyle(string style)
    {
        var match = Regex.Match(style, @"background-image: url\(""(.+?)""\);");
        if (match.Success)
        {
            return match.Groups[1].Value;
        }
        return string.Empty;
    }

    private static async Task<List<IRequest>> CaptureRequestsAsync(Site site, IPage page)
    {
        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });

        await GoToVideosAsync(page);
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        await page.UnrouteAsync("**/*");
        return requests;
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

    private static Dictionary<string, string> SetHeadersFromActualRequest(IList<IRequest> requests)
    {
        var videosHtmlRequest = requests.SingleOrDefault(r => r.Url.EndsWith("/videos"));
        if (videosHtmlRequest == null)
        {
            var requestUrls = requests.Select(r => r.Url + Environment.NewLine).ToList();
            throw new InvalidOperationException($"Could not read videos HTML request from following requests:{Environment.NewLine}{string.Join("", requestUrls)}");
        }

        Client.DefaultRequestHeaders.Clear();
        foreach (var key in videosHtmlRequest.Headers.Keys)
        {
            Client.DefaultRequestHeaders.Add(key, videosHtmlRequest.Headers[key]);
        }

        return videosHtmlRequest.Headers;
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        var downloadedReleases = 0;

        var convertedHeaders = new WebHeaderCollection();
        var requests = await CaptureRequestsAsync(site, page);

        var headers = SetHeadersFromActualRequest(requests);
        convertedHeaders = ConvertHeaders(headers);

        IPage releasePage = await page.Context.NewPageAsync();

        try
        {
            foreach (var release in releases)
            {
                var releaseDownloadPlan = PlanDownloads(release, downloadConditions);
                var releaseMissingDownloadsPlan = await _downloadPlanner.PlanMissingDownloadsAsync(releaseDownloadPlan);

                if (!releaseMissingDownloadsPlan.AvailableFiles.Any())
                {
                    continue;
                }

                var retryPolicy = Policy
                    .Handle<PlaywrightException>()
                    .WaitAndRetryAsync(3, retryAttempt => TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)));
                await retryPolicy.ExecuteAsync(async () => await releasePage.GotoAsync(release.Url));

                Release? updatedScrape;
                try
                {
                    await ClickOnEnterIfVisibleAsync(releasePage);
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
                foreach (var videoDownload in await DownloadVideosAsync(releasePage, downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
                {
                    yield return videoDownload;
                }
                await foreach (var imageDownload in DownloadImagesAsync(updatedScrape, existingDownloadEntities, convertedHeaders))
                {
                    yield return imageDownload;
                }

                downloadedReleases++;
                Log.Information($"{downloadedReleases} releases downloaded in this session.");
            }
        }
        finally
        {
            await releasePage.CloseAsync();
        }
    }

    private async Task<IEnumerable<Download>> DownloadVideosAsync(IPage releasePage, DownloadConditions downloadConditions, Release release, IReadOnlyList<DownloadEntity> existingDownloadEntities, WebHeaderCollection headers)
    {
        IEnumerable<Download>? downloads = null;

        do
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
            var suffix = ".mp4";

            if (!selectedVideo.Variant.ToUpperInvariant().Contains("MP4"))
            {
                Log.Warning("Release {Site} {ReleaseDate} {Release} is not an MP4 video.", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                Console.ReadLine();
                return new List<Download>();
            }

            var performersStr = release.Performers.Count() > 1
                ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
                  release.Performers.Last().Name
                : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
            var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.Variant);

            var fileInfo = await _downloader.TryDownloadAsync(release, selectedVideo, selectedVideo.Url, fileName, headers);
            if (fileInfo == null)
            {
                return new List<Download>();
            }

            VideoHashes? videoHashes = Hasher.Phash(@"""" + fileInfo.FullName + @"""");
            if (videoHashes != null)
            {
                downloads = new List<Download>
                {
                    new(release, suggestedFileName, fileInfo.Name, selectedVideo, videoHashes)
                };
            }
            else
            {
                try
                {
                    Log.Warning("Checking if downloads are blocked due to CAPTCHA...");
                    await releasePage.GotoAsync(selectedVideo.Url);
                    await HandleCaptchaAsync(releasePage);
                }
                catch (Exception ex)
                {
                    Log.Error(ex, "Failed to check if downloads are blocked due to CAPTCHA. Skipping!");
                    break;
                }
            }
        } while (downloads == null);

        if (downloads == null)
        {
            Log.Error("Failed to download video.");
            return new List<Download>();
        }

        return downloads;
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
        var sceneFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "scene").ToList();

        var selectedSceneFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? sceneFiles.Take(1)
            : sceneFiles.TakeLast(1);
        var otherFiles = release.AvailableFiles
            .Except(sceneFiles)
            .ToList();

        var availableFiles = new List<IAvailableFile>()
            .Concat(selectedSceneFiles)
            .Concat(otherFiles)
            .ToImmutableList();

        return new ReleaseDownloadPlan(release, availableFiles);
    }

    private static async Task ClickOnEnterIfVisibleAsync(IPage page)
    {
        var enterButton = page.FrameLocator("iframe").GetByRole(AriaRole.Link, new() { Name = "Enter" });
        await ClickIfVisibleAsync(enterButton);
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await ClickOnEnterIfVisibleAsync(page);

        var agreeButton = page.FrameLocator("iframe").GetByRole(AriaRole.Link, new() { Name = "Enter and accept cookies" });
        await ClickIfVisibleAsync(agreeButton);

        var loginButton = page.Locator("a.login");
        if (await loginButton.IsVisibleAsync())
        {
            await loginButton.ClickAsync();

            await HandleBeingPossiblyBlockedAsync(page);

            var usernameInput = page.Locator("#username");
            var passwordInput = page.Locator("#password");
            var confirmButton = page.GetByRole(AriaRole.Button, new() { Name = "Confirm" });

            if (await usernameInput.IsVisibleAsync())
            {
                await usernameInput.ClickAsync();
                await usernameInput.FillAsync(site.Username);
                await passwordInput.ClickAsync();
                await passwordInput.FillAsync(site.Password);

                if (await page.Locator("div.captcha").IsVisibleAsync())
                {
                    Log.Warning("CAPTCHA required!");
                    await _captchaSolver.SolveCaptchaIfNeededAsync(page);
                }

                await ClickIfVisibleAsync(confirmButton);

                // Sometimes there is another CAPTCHA after login.
                if (await page.Locator("div.captcha").IsVisibleAsync())
                {
                    Log.Warning("CAPTCHA required!");
                    await _captchaSolver.SolveCaptchaIfNeededAsync(page);
                }

                await ClickIfVisibleAsync(confirmButton);

                Log.Information($"Logged into {site.Name}.");

                await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

                await ClickIfVisibleAsync(agreeButton);

                await GoToVideosAsync(page);
            }

            if (site.ShortName == "dorcelclub")
            {
                if (!(await page.Locator("div.languages > .selected-item").TextContentAsync()).Contains("English"))
                {
                    await page.Keyboard.DownAsync("End");
                    await page.GetByRole(AriaRole.Img, new() { NameString = "close" }).ClickAsync();
                    await page.GetByText("English").ClickAsync();
                }
            }
        }
    }

    private static async Task ClickIfVisibleAsync(ILocator locator)
    {
        if (await locator.IsVisibleAsync())
        {
            await locator.ClickAsync();
        }
    }

    private async Task HandleBeingPossiblyBlockedAsync(IPage page)
    {
        var blockedHeader = await page.QuerySelectorAsync("h1.title");
        if (blockedHeader == null || !(await blockedHeader.IsVisibleAsync()))
        {
            return;
        }

        var blockedHeaderText = await blockedHeader.TextContentAsync();
        if (blockedHeaderText?.Trim().ToUpperInvariant() != "YOU ARE CURRENTLY BLOCKED")
        {
            return;
        }

        await HandleCaptchaAsync(page);
    }

    private async Task HandleCaptchaAsync(IPage page)
    {
        if (await page.Locator("div.g-recaptcha").IsVisibleAsync())
        {
            Log.Warning("CAPTCHA required!");
            await _captchaSolver.SolveCaptchaIfNeededAsync(page);
            var continueButton = page.GetByRole(AriaRole.Button, new() { Name = "Continue" });
            await continueButton.ClickAsync();
        }
    }

    private static async Task GoToVideosAsync(IPage page)
    {
        await ClickOnEnterIfVisibleAsync(page);

        await page.GotoAsync("/videos");
    }
    
    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle currentRelease)
    {
        var thumbLinkElement = await currentRelease.QuerySelectorAsync("a.thumb");
        var url = await thumbLinkElement.GetAttributeAsync("href");
        var pattern = @"\/videos\/(\d+)\/[0-9a-z\-]+";
        Match match = Regex.Match(url, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Could not parse numerical ID from {url} using pattern {pattern}.");
        }

        string shortName = match.Groups[1].Value;
        return new ReleaseIdAndUrl(shortName, url);
    }

    private static async Task<IReadOnlyList<IAvailableFile>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadLinks = await page.Locator("div.qualities.selectors div.filter").ElementHandlesAsync();
        var availableDownloads = new List<IAvailableFile>();
        foreach (var downloadLink in downloadLinks)
        {
            var language = await downloadLink.GetAttributeAsync("data-lang");

            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", "").Trim() + $" (Language: {language})";

            var resolutionHeightRaw = await downloadLink.GetAttributeAsync("data-quality");
            var resolutionHeight = int.Parse(resolutionHeightRaw);

            var url = await downloadLink.GetAttributeAsync("data-slug");
            availableDownloads.Add(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        description,
                        url,
                        -1,
                        resolutionHeight,
                        HumanParser.ParseFileSize(description),
                        -1,
                        string.Empty));
        }
        return availableDownloads;
    }
}
