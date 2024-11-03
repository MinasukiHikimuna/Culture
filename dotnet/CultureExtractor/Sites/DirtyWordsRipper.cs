using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Polly;
using Serilog;
using System.Collections.Immutable;
using System.Net;

namespace CultureExtractor.Sites;

/**
 * TODO:
 * - Performers are associated incorrectly!
 * - Some releases are added multiple times
 **/
[Site("dirtywords")]
public class DirtyWordsRipper : IYieldingScraper
{
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly IDownloader _downloader;

    public DirtyWordsRipper(IPlaywrightFactory playwrightFactory, IRepository repository, IDownloader downloader)
    {
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _downloader = downloader;
    }

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await foreach (var scene in ScrapeScenesAsync(site, page, scrapeOptions))
        {
            yield return scene;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        // Rip only specific model
        // var modelName = "mina-thorne"; // "xev-bellringer"; // "bratty-bunny-4"; // "ashley-alban"; // "ashley-fires;" // "brooke-marie"; // "ellie-idol"; // "goddess-vikki"; // 
        // var baseUrl = $"/category/models/{modelName}";
        // end
        // Rip all models
        var baseUrl = "";

        await RetryGotoAsync(page, $"{site.Url}{baseUrl}");

        var lastPageLink = await page.Locator("a.last").First.ElementHandleAsync();
        var lastPageUrl = await lastPageLink.GetAttributeAsync("href");
        var pages = int.Parse(lastPageUrl.Split('/').Last());

        for (var pageNumber = 2229; pageNumber <= pages; pageNumber++)
        {
            await RetryGotoAsync(page, $"{site.Url}{baseUrl}/page/{pageNumber}");

            var releaseHandles = await page.Locator("article.post").ElementHandlesAsync();
            Log.Information($"Page {pageNumber}/{pages} contains {releaseHandles.Count} releases");

            var listedReleases = new List<ListedRelease>();
            foreach (var releaseHandle in releaseHandles)
            {
                var releaseIdAndUrl = await GetReleaseIdAsync(releaseHandle);
                listedReleases.Add(new ListedRelease(null, releaseIdAndUrl.Id, releaseIdAndUrl.Url, releaseHandle));
            }

            var scenes = listedReleases
                .ToDictionary(r => r.ShortName, r => r);
            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, scenes.Keys.ToList());
            var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);
            var moviesToBeScraped = scenes
                .Where(g => !existingReleasesDictionary.ContainsKey(g.Key) || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated)
                .Select(g => g.Value)
                .ToList();

            foreach (var movie in moviesToBeScraped)
            {
                await Task.Delay(5000);

                var release = await ScrapeReleaseAsync(movie, site, null, page, scrapeOptions);
                if (release != null)
                {
                    yield return release;
                }
                else
                {
                    Log.Warning("Failed to scrape release {Release} from {Url}", movie.ShortName, movie.Url);
                }
            }
        }
    }

    private async Task<IResponse?> RetryGotoAsync(IPage page, string url)
    {
        var strategy = new ResiliencePipelineBuilder<IResponse?>()
            .AddRetry(new ()
            {
                MaxRetryAttempts = 3,
                Delay = TimeSpan.FromSeconds(10),
                OnRetry = args =>
                {
                    var ex = args.Outcome.Exception;
                    Log.Error($"Caught following exception while navigating to {url}: " + ex, ex);
                    return default;
                }
            })
            .Build();

        return await strategy.ExecuteAsync(async token =>
            await page.GotoAsync(url)
        );
    }

    private async Task<Release?> ScrapeReleaseAsync(ListedRelease currentRelease, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions)
    {
        var releasePage = await page.Context.NewPageAsync();

        await RetryGotoAsync(releasePage, currentRelease.Url);

        try
        {
            var releaseUuid = currentRelease.Release?.Uuid ?? UuidGenerator.Generate();

            var title = await releasePage.Locator("div.post-title").TextContentAsync();

            var articleContainer = await releasePage.Locator("article.post").First.ElementHandleAsync();
            var id = await articleContainer.GetAttributeAsync("id");

            var postContainer = await page.Locator("div.postdata").First.ElementHandleAsync();

            var performerContainer = await postContainer.QuerySelectorAsync("div.left > a");
            var performerRaw = await performerContainer.TextContentAsync();
            var performerName = performerRaw.Replace("\t", " ").Replace("\n", "").Trim();
            var performerUrl = await performerContainer.GetAttributeAsync("href");
            var performerShortName = performerUrl.Split('/').Last();
            var performers = new List<SitePerformer> { new SitePerformer(performerShortName, performerName, performerUrl) };


            var tagsContainer = await postContainer.QuerySelectorAsync("div.right");
            var tagElements = await tagsContainer.QuerySelectorAllAsync("a");

            var tags = new List<SiteTag>();
            foreach (var tagElement in tagElements)
            {
                var link = await tagElement.GetAttributeAsync("href");
                var tagId = link.Split('/').Last();
                var tag = await tagElement.TextContentAsync();
                tags.Add(new SiteTag(tagId, tag, link));
            }

            var descriptionContainer = await releasePage.Locator("div.single.entry-content p ").Nth(1).ElementHandleAsync();
            var description = await descriptionContainer.TextContentAsync();

            var dateContainer = await articleContainer.QuerySelectorAsync("div.date");
            var yearContainer = await dateContainer.QuerySelectorAsync("div.year");
            var year = await yearContainer.TextContentAsync();

            var monthContainer = await dateContainer.QuerySelectorAsync("div.month");
            var month = await monthContainer.TextContentAsync();

            var dayContainer = await dateContainer.QuerySelectorAsync("div.day");
            var day = await dayContainer.TextContentAsync();

            var date = DateTime.Parse($"{day} {month} {year}");

            var images = await articleContainer.QuerySelectorAllAsync("div.entry > p > a > img");
            var imageDownloads = new List<IAvailableFile>();

            var heroImage = images[0];
            var thumbnailImage = images[1];

            string? heroImageUrl = await heroImage.GetAttributeAsync("src");
            heroImageUrl = heroImageUrl.Replace("thumbs/small", "files");

            string? thumbnailImageUrl = await thumbnailImage.GetAttributeAsync("src");
            thumbnailImageUrl = thumbnailImageUrl.Replace("thumbs/small", "files");

            var heroImageFile = new AvailableImageFile("image", "hero", "", heroImageUrl, -1, -1, -1);
            var thumbnailImageFile = new AvailableImageFile("image", "thumbnail", "", thumbnailImageUrl, -1, -1, -1);

            imageDownloads.Add(heroImageFile);
            imageDownloads.Add(thumbnailImageFile);

            var scriptElement = await page.QuerySelectorAsync("script[type='application/ld+json']");
            var scriptRaw = await scriptElement.InnerTextAsync();

            var k2sDownload = await releasePage.Locator("a.free.button").GetAttributeAsync("href");
            var videoDownload = new AvailableVideoFile("video", "scene", "", k2sDownload, -1, -1, -1, -1, "");

            var scene = new Release(
                releaseUuid,
                site,
                subSite,
                DateOnly.FromDateTime(date),
                id,
                title,
                currentRelease.Url,
                description ?? string.Empty,
                -1,
                performers,
                tags,
                new List<IAvailableFile>()
                    .Concat(imageDownloads)
                    .Concat(new List<AvailableVideoFile> { videoDownload }),
                scriptRaw,
                DateTime.Now);

            return scene;
        }
        catch (Exception ex)
        {
            Log.Error($"Failed to scrape release {currentRelease.ShortName} from {currentRelease.Url}", ex);
            return null;
        }
        finally
        {
            await releasePage.CloseAsync();
        }
    }

    private async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle releaseHandle)
    {
        var id = await releaseHandle.GetAttributeAsync("id");

        var link = await releaseHandle.QuerySelectorAsync("a");
        var url = await link.GetAttributeAsync("href");

        return new ReleaseIdAndUrl(id, url);
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        yield return null;
        // throw new NotImplementedException();
        /*
        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        var downloadedReleases = 0;
        foreach (var release in releases)
        {
            var releaseDownloadPlan = PlanDownloads(release, downloadConditions);
            var releaseMissingDownloadsPlan = PlanMissingDownloads(releaseDownloadPlan);

            if (!releaseMissingDownloadsPlan.AvailableFiles.Any())
            {
                continue;
            }

            var cookie = Client.DefaultRequestHeaders.GetValues("cookie").FirstOrDefault();
            var accessToken = ExtractAccessTokenFromCookie(cookie);
            var expiryDate = DecodeTokenAndGetExpiry(accessToken);
            var convertedHeaders = new WebHeaderCollection();
            if (expiryDate != null && expiryDate.Value.AddMinutes(-5) < DateTime.Now.ToUniversalTime())
            {
                var requests = await CaptureRequestsAsync(site, page);

                SetHeadersFromActualRequest(site, requests);

                var newCookie = Client.DefaultRequestHeaders.GetValues("cookie").FirstOrDefault();
                var newAccessToken = ExtractAccessTokenFromCookie(newCookie);

                Log.Debug($"Refresh access token.{Environment.NewLine}Old: {accessToken}{Environment.NewLine}New: {newAccessToken}");

                var headers = SetHeadersFromActualRequest(site, requests);
                convertedHeaders = ConvertHeaders(headers);
            }

            // this is now done on every scene despite we might already have all files
            // the reason for updated scrape is that the links are timebombed and we need to refresh those
            Release? updatedScrape;
            try
            {
                updatedScrape = await ScrapeSceneAsync(site, release.ShortName, release.Uuid);
            }
            catch (Exception ex)
            {
                Log.Warning(ex, "Could not scrape {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                continue;
            }
            await Task.Delay(10000);

            var existingDownloadEntities = await _context.Downloads.Where(d => d.ReleaseUuid == release.Uuid).ToListAsync();
            Log.Information("Downloading: {Site} - {ReleaseDate} - {Release} [{Uuid}]", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name, release.Uuid);
            foreach (var videoDownload in await DownloadVideosAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
            {
                yield return videoDownload;
            }
            await foreach (var galleryDownload in DownloadGalleryAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
            {
                yield return galleryDownload;
            }
            foreach (var trailerDownload in await DownloadTrailersAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
            {
                yield return trailerDownload;
            }
            await foreach (var imageDownload in DownloadImagesAsync(updatedScrape, existingDownloadEntities, convertedHeaders))
            {
                yield return imageDownload;
            }

            downloadedReleases++;
            Log.Information($"{downloadedReleases} releases downloaded in this session.");
        }*/
    }

    private ReleaseDownloadPlan PlanMissingDownloads(ReleaseDownloadPlan releaseDownloadPlan)
    {
        /*var existingDownloads = _context.Downloads.Where(d => d.ReleaseUuid == releaseDownloadPlan.Release.Uuid).ToList();
        var notYetDownloaded = releaseDownloadPlan.AvailableFiles
            .Where(f => !existingDownloads.Exists(d =>
                d.FileType == f.FileType && d.ContentType == f.ContentType && d.Variant == f.Variant))
            .ToImmutableList();

        return releaseDownloadPlan with { AvailableFiles = notYetDownloaded };*/

        throw new NotImplementedException();
    }

    private static ReleaseDownloadPlan PlanDownloads(Release release, DownloadConditions downloadConditions)
    {
        var sceneFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "scene").ToList();
        var trailerFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "trailer").ToList();

        var selectedSceneFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? sceneFiles.Take(1)
            : sceneFiles.TakeLast(1);
        var selectedTrailerFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? trailerFiles.Take(1)
            : trailerFiles.TakeLast(1);
        var otherFiles = release.AvailableFiles
            .Except(trailerFiles)
            .Except(sceneFiles)
            .ToList();

        var availableFiles = new List<IAvailableFile>()
            .Concat(selectedSceneFiles)
            .Concat(selectedTrailerFiles)
            .Concat(otherFiles)
            .ToImmutableList();

        return new ReleaseDownloadPlan(release, availableFiles);
    }
}
