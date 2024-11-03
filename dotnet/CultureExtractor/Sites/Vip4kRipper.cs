using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Globalization;
using CultureExtractor.Models;
using CultureExtractor.Exceptions;
using System.Collections.Immutable;
using System.Net;
using System.Text;

namespace CultureExtractor.Sites;

[Site("vip4k")]
public class Vip4KRipper : IYieldingScraper
{
    private static readonly HttpClient Client = new();

    private readonly ILegacyDownloader _legacyDownloader;
    private readonly IRepository _repository;
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IDownloadPlanner _downloadPlanner;
    private readonly IDownloader _downloader;

    public Vip4KRipper(
        ILegacyDownloader legacyDownloader,
        IRepository repository,
        IPlaywrightFactory playwrightFactory,
        IDownloadPlanner downloadPlanner,
        IDownloader downloader)
    {
        _legacyDownloader = legacyDownloader;
        _repository = repository;
        _playwrightFactory = playwrightFactory;
        _downloadPlanner = downloadPlanner;
        _downloader = downloader;
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
        var subSites = await GetSubSitesAsync(site, page);

        var releasePage = await page.Context.NewPageAsync();
        var galleryPage = await page.Context.NewPageAsync();
        try
        {
            var filteredSubSites = subSites
                .Where(s => (!scrapeOptions.IncludeSubSites.Any() || scrapeOptions.IncludeSubSites.Any(i => i.ToUpperInvariant() == s.ShortName.ToUpperInvariant())) &&
                            (!scrapeOptions.ExcludeSubSites.Any() || scrapeOptions.ExcludeSubSites.All(e => e.ToUpperInvariant() != s.ShortName.ToUpperInvariant())))
                .ToList();

            foreach (var subSite in filteredSubSites)
            {
                await GoToPageAsync(page, subSite, 1);
                await page.WaitForLoadStateAsync();

                var totalPages = await GetTotalPagesAsync(page, site, subSite);

                for (var pageNumber = 1; pageNumber <= totalPages; pageNumber++)
                {
                    await GoToPageAsync(page, subSite, pageNumber);

                    var releaseHandles = await page.Locator("div.row.portal-grid div.portal-video-wrapper").ElementHandlesAsync();

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

                    var existingReleases = await _repository
                        .GetReleasesAsync(site.ShortName, listedReleasesDict.Keys.ToList());


                    var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);

                    var scenesToBeScraped = listedReleasesDict
                        .Where(g => !existingReleasesDictionary.ContainsKey(g.Key) || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated)
                        .Select(g => g.Value)
                        .ToList();

                    if (pageNumber == 1 && listedReleases.Any() && !scenesToBeScraped.Any())
                    {
                        Log.Information($"Subsite {subSite.Name}: All up-to-date");
                        break;
                    }

                    Log.Information($"Subsite {subSite.Name}: Page {pageNumber}/{totalPages} contains {releaseHandles.Count} releases");

                    foreach (var sceneToBeScraped in scenesToBeScraped)
                    {
                        var releaseGuid = existingReleasesDictionary.TryGetValue(sceneToBeScraped.ShortName, out var existingRelease)
                            ? existingRelease.Uuid
                            : UuidGenerator.Generate();

                        Release? scene = null;

                        try
                        {
                            scene = await ScrapeReleaseAsync(releaseGuid, site, subSite, sceneToBeScraped.Url, sceneToBeScraped.ShortName, releasePage, galleryPage);
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
                }
            }
        }
        finally
        {
            releasePage?.CloseAsync();
            galleryPage?.CloseAsync();
        }
    }

    private async Task<int> GetTotalPagesAsync(IPage page, Site site, SubSite subSite)
    {
        var pageElements = await page.QuerySelectorAllAsync("#api-pagination > ul > li > a:not(.next)");
        if (pageElements.Count == 0)
        {
            Log.Warning("No pages found for site {Site} {SubSite}", site.ShortName, subSite.ShortName);
            return 0;
        }

        var lastPageElement = pageElements.Last();
        var lastPage = await lastPageElement.TextContentAsync();

        return int.Parse(lastPage);
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage? releasePage = null;
        IPage? galleryPage = null;

        try
        {
            releasePage = await _playwrightFactory.CreatePageAsync(site, browserSettings);
            await LoginAsync(site, releasePage);
            galleryPage = await releasePage.Context.NewPageAsync();

            var requests = await CaptureRequestsAsync(site, releasePage);
            var headers = SetHeadersFromActualRequest(requests);
            var convertedHeaders = ConvertHeaders(headers);

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

                Release? updatedScrape;
                try
                {
                    updatedScrape = await ScrapeReleaseAsync(release.Uuid, release.Site, release.SubSite, release.Url, release.ShortName, releasePage, galleryPage);
                }
                catch (ExtractorException ex)
                {
                    switch (ex.ExtractorRetryMode)
                    {
                        case ExtractorRetryMode.RetryLogin:
                            await LoginAsync(site, releasePage);
                            continue;
                        case ExtractorRetryMode.Retry:
                            continue;
                        case ExtractorRetryMode.Skip:
                            Log.Error(ex, $"Error while scraping scene, skipping: {release.ShortName}");
                            continue;
                        default:
                        case ExtractorRetryMode.Abort:
                            throw;
                    }
                }
                catch (Exception ex)
                {
                    Log.Warning(ex, "Could not scrape {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                    continue;
                }

                var existingDownloadEntities = await _downloadPlanner.GetExistingDownloadsAsync(updatedScrape);
                Log.Information("Downloading: {Site} - {ReleaseDate} - {Release} [{Uuid}]", updatedScrape.Site.Name, updatedScrape.ReleaseDate.ToString("yyyy-MM-dd"), updatedScrape.Name, updatedScrape.Uuid);
                foreach (var videoDownload in await DownloadVideosAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
                {
                    yield return videoDownload;
                }
                foreach (var galleryDownload in await DownloadGalleriesAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
                {
                    yield return galleryDownload;
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
            await releasePage?.CloseAsync();
            await galleryPage?.CloseAsync();
        }
    }

    private static async Task<List<IRequest>> CaptureRequestsAsync(Site site, IPage page)
    {
        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });

        await page.GotoAsync("/studios");
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        await page.UnrouteAsync("**/*");
        return requests;
    }

    private static Dictionary<string, string> SetHeadersFromActualRequest(IList<IRequest> requests)
    {
        var adultPrimeRequest = requests.FirstOrDefault(r => r.Url.StartsWith("https://adultprime.com"));
        if (adultPrimeRequest == null)
        {
            var requestUrls = requests.Select(r => r.Url + Environment.NewLine).ToList();
            throw new InvalidOperationException($"Could not read galleries API request from following requests:{Environment.NewLine}{string.Join("", requestUrls)}");
        }

        Client.DefaultRequestHeaders.Clear();
        foreach (var key in adultPrimeRequest.Headers.Keys)
        {
            Client.DefaultRequestHeaders.Add(key, adultPrimeRequest.Headers[key]);
        }

        return adultPrimeRequest.Headers;
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
            .Where(d => d is { FileType: "zip", ContentType: "gallery" });
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


    private async Task LoginAsync(Site site, IPage page)
    {
        await page.WaitForLoadStateAsync();

        if (page.Url.Contains("login"))
        {
            /*var usernameInput = page.GetByPlaceholder("Email / Username");
            await usernameInput.ClickAsync();
            await usernameInput.FillAsync(site.Username);

            var passwordInput = page.GetByPlaceholder("Password");
            await passwordInput.ClickAsync();
            await passwordInput.FillAsync(site.Password);*/

            Log.Warning("CAPTCHA required! Enter manually!");
            Console.ReadLine();

            await page.GetByRole(AriaRole.Button, new() { Name = "Login" }).ClickAsync();
            await page.WaitForLoadStateAsync();

            await Task.Delay(5000);

            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }
    }

    private static async Task GoToPageAsync(IPage page, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/studios/videos?website={subSite.Name}&page={pageNumber}");
        await Task.Delay(1000);
    }

    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle currentRelease)
    {
        var overlayElement = await currentRelease.QuerySelectorAsync("div.overlay");
        var aElement = await overlayElement.QuerySelectorAsync("a");
        var url = await aElement.GetAttributeAsync("href");

        var shortName = await overlayElement.GetAttributeAsync("data-id");

        return new ReleaseIdAndUrl(shortName, url);
    }

    private async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage scenePage, IPage galleryPage)
    {
        var successfulLoading = false;
        for (var i = 0; i < 3; i++)
        {
            try
            {
                await scenePage.GotoAsync(url);
                await scenePage.WaitForLoadStateAsync();
                await Task.Delay(1000);
                successfulLoading = true;
            }
            catch (Exception ex)
            {
                Log.Warning(ex, "Failed to load scene page {Url}, retrying", url);
            }
        }

        if (!successfulLoading)
        {
            throw new ExtractorException(ExtractorRetryMode.Skip, $"Failed to load scene page {url}");
        }

        var releaseDateElement = await scenePage.QuerySelectorAsync("p.update-info-line:nth-of-type(1) i.fa-calendar + b");
        string releaseDateRaw = await releaseDateElement.TextContentAsync();
        DateOnly releaseDate = DateOnly.ParseExact(releaseDateRaw, "dd.MM.yyyy", CultureInfo.InvariantCulture);

        var durationElement = await scenePage.QuerySelectorAsync("p.update-info-line:nth-of-type(1) i.fa-clock-o + b");
        var durationRaw = await durationElement.TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await scenePage.Locator("h1.update-info-title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        IElementHandle performerContainer = null;
        ILocator performerContainerLocator = scenePage.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Performer:" });
        ILocator performersContainerLocator = scenePage.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Performers:" });
        if (await performerContainerLocator.IsVisibleAsync())
        {
            performerContainer = await performerContainerLocator.ElementHandleAsync();
        }
        else if (await performersContainerLocator.IsVisibleAsync())
        {
            performerContainer = await performersContainerLocator.ElementHandleAsync();
        }

        var performers = new List<SitePerformer>();
        if (performerContainer != null)
        {
            var performersRaw = await performerContainer.QuerySelectorAllAsync("a");

            foreach (var performerElement in performersRaw)
            {
                var performerUrl = await performerElement.GetAttributeAsync("href");
                var nameRaw = await performerElement.TextContentAsync();
                var name = nameRaw.Trim();
                var shortName = name.Replace(" ", "+");
                performers.Add(new SitePerformer(shortName, name, performerUrl));
            }
        }

        var descriptionRaw = await scenePage.Locator("p.ap-limited-description-text").TextContentAsync();
        string description = descriptionRaw.Trim();

        var tagsContainer = await scenePage.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Niches:" }).ElementHandleAsync();
        var tagElements = await tagsContainer.QuerySelectorAllAsync("a");
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Replace("/studios/videos?niche=", "");
            var tagNameRaw = await tagElement.TextContentAsync();
            var tagName = tagNameRaw.Replace("\n", "").Trim();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        var availableVideoFiles = await ParseAvailableDownloadsAsync(scenePage);

        var previewElement = await scenePage.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");
        var availableImageFile = new AvailableImageFile("image", "scene", "preview", backgroundImageUrl, null, null, null);
        var availableImageFiles = new List<IAvailableFile> { availableImageFile };

        var availableGalleryFiles = new List<IAvailableFile>();
        var photosLink = scenePage.Locator("a.btn-pictures");
        if (await photosLink.IsVisibleAsync())
        {
            var photosUrl = await photosLink.GetAttributeAsync("href");
            await galleryPage.GotoAsync(photosUrl);
            var downloadIcon = await galleryPage.Locator("i.fa-download").ElementHandleAsync();
            var downloadContainer = await downloadIcon.EvaluateHandleAsync("element => element.parentNode");
            var downloadUrl = await downloadContainer.AsElement().GetAttributeAsync("href");
            availableGalleryFiles.Add(new AvailableGalleryZipFile("zip",
                "gallery",
                "",
                downloadUrl,
                null,
                null,
                null));
        }

        var release = new Release(
            releaseUuid,
            site,
            subSite,
            releaseDate,
            releaseShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            new List<IAvailableFile>()
                .Concat(availableVideoFiles)
                .Concat(availableImageFiles)
                .Concat(availableGalleryFiles).ToList(),
            "{}",
            DateTime.Now);

        return release;
    }

    private static async Task<IList<AvailableVideoFile>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadIcon = await page.Locator("i.fa-download").ElementHandleAsync();
        var downloadContainer = await downloadIcon.EvaluateHandleAsync("element => element.parentNode.parentNode");
        var downloadLinks = await downloadContainer.AsElement().QuerySelectorAllAsync("a");
        var availableDownloads = new List<AvailableVideoFile>();
        foreach (var downloadLink in downloadLinks)
        {
            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", " ").Trim();

            var resolutionHeight = HumanParser.ParseResolutionHeight(description);

            var url = await downloadLink.GetAttributeAsync("href");

            availableDownloads.Add(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        description,
                        url,
                        -1,
                        resolutionHeight,
                        -1,
                        -1,
                        string.Empty));
        }
        return availableDownloads.OrderByDescending(d => d.ResolutionHeight).ToList();
    }

    private async Task<IReadOnlyList<SubSite>> GetSubSitesAsync(Site site, IPage page)
    {
        await page.GotoAsync("/studios");
        await Task.Delay(5000);

        var existingSubSites = await _repository.GetSubSitesAsync(site.Uuid);

        var studioHandles = await page.Locator("div.studio-item-container").ElementHandlesAsync();
        List<SubSite> subSites = new List<SubSite>();
        foreach (var studioHandle in studioHandles)
        {
            // get the <a> element inside the current studio container
            var aElementHandle = await studioHandle.QuerySelectorAsync("a");
            if (aElementHandle == null)
            {
                continue;
            }

            var imgElementHandle = await studioHandle.QuerySelectorAsync(":scope > img");
            if (imgElementHandle != null)
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

            var siteName = subsiteUrl.Replace("/studios/studio/", "");

            var uuid = existingSubSites.FirstOrDefault(s => s.ShortName == siteName)?.Uuid ?? UuidGenerator.Generate();
            subSites.Add(new SubSite(uuid, siteName, siteName, "{}", site));
        }

        var uniqueSubSites = subSites
            .GroupBy(s => s.Name)
            .Select(g => g.First())
            .OrderBy(s => s.Name)
            .ToList();

        return uniqueSubSites.AsReadOnly();
    }
}
