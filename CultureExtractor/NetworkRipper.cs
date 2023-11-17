using CultureExtractor.Exceptions;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.Playwright;
using Polly;
using Polly.Fallback;
using Polly.Retry;
using Serilog;

namespace CultureExtractor;

public class NetworkRipper : INetworkRipper
{
    private readonly IRepository _repository;
    private readonly IServiceProvider _serviceProvider;
    private readonly IDownloader _downloader;
    private readonly IPlaywrightFactory _playwrightFactory;

    public NetworkRipper(IRepository repository, IServiceProvider serviceProvider, IDownloader downloader, IPlaywrightFactory playwrightFactory)
    {
        _repository = repository;
        _serviceProvider = serviceProvider;
        _downloader = downloader;
        _playwrightFactory = playwrightFactory;
    }

    public async Task ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IScraper scraper = (IScraper)_serviceProvider.GetService(typeof(IScraper));
        Log.Information($"Culture Extractor, using {scraper.GetType()}");

        if (scraper is IYieldingScraper yieldingScraper)
        {
            await foreach (var release in yieldingScraper.ScrapeReleasesAsync(site, browserSettings, scrapeOptions))
            {
                await _repository.UpsertRelease(release);
                
                var releaseDescription = new {
                    Uuid = release.Uuid,
                    Site = release.Site.Name,
                    SubSite = release.SubSite?.Name,
                    ShortName = release.ShortName,
                    ReleaseDate = release.ReleaseDate,
                    Name = release.Name,
                    Url = release.Url.StartsWith("https://")
                        ? release.Url
                        : release.Site.Url + release.Url };
                Log.Information("Scraped release: {@Release}", releaseDescription);
            }
        }
        else if (scraper is ISubSiteScraper subSiteScraper)
        {
            await ScrapeSubSiteReleasesAsync(site, browserSettings, scrapeOptions, subSiteScraper);
        }
        else if (scraper is ISiteScraper siteScraper)
        {
            IPage page = await CreatePageAndLoginAsync(siteScraper, site, browserSettings, scrapeOptions.GuestMode);
            var totalPages = await siteScraper.NavigateToReleasesAndReturnPageCountAsync(site, page);

            await ScrapeReleasesInternalAsync(site, null, scrapeOptions, siteScraper, page, totalPages);
        }
    }

    private async Task ScrapeSubSiteReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions, ISubSiteScraper subSiteScraper)
    {
        IPage page = await CreatePageAndLoginAsync(subSiteScraper, site, browserSettings, scrapeOptions.GuestMode);

        var subSites = await subSiteScraper.GetSubSitesAsync(site, page);
        subSites = !string.IsNullOrWhiteSpace(scrapeOptions.SubSite)
            ? subSites.Where(x => x.ShortName == scrapeOptions.SubSite).ToList()
            : subSites;

        var i = 1;
        foreach (var subSite in subSites)
        {
            Log.Information($"Subsite {i}/{subSites.Count}: {subSite.Name}");
            var totalPages = await subSiteScraper.NavigateToSubSiteAndReturnPageCountAsync(site, subSite, page);
            await ScrapeReleasesInternalAsync(site, subSite, scrapeOptions, subSiteScraper, page, totalPages);
            i++;
        }
    }

    private static IEnumerable<int> PageEnumeration(ScrapeOptions scrapeOptions, int totalPages)
    {
        for (int currentPage = scrapeOptions.ReverseOrder ? 1 : totalPages;
             scrapeOptions.ReverseOrder ? currentPage <= totalPages : currentPage >= 1;
             currentPage += scrapeOptions.ReverseOrder ? 1 : -1)
        {
            yield return currentPage;
        }
    }

    private async Task ScrapeReleasesInternalAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, int totalPages)
    {
        foreach (var currentPage in PageEnumeration(scrapeOptions, totalPages))
        {
            await ScrapeReleasePageAsync(site, subSite, scrapeOptions, siteScraper, page, totalPages, currentPage);
        }
    }

    private async Task ScrapeReleasePageAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, int totalPages, int currentPage)
    {
        var scrapedReleases = 0;

        IReadOnlyList<ListedRelease> listedReleases = await ScrapePageListedReleasesAsync(site, subSite, siteScraper, page, currentPage);

        Log.Information(totalPages == int.MaxValue
            ? $"Batch {currentPage} of infinite page contains {listedReleases.Count} releases"
            : $"Page {currentPage}/{totalPages} contains {listedReleases.Count} releases");

        var existingReleases = await _repository.GetReleasesAsync(site.ShortName, listedReleases.Select(s => s.ShortName).ToList());
        var checkedListedReleases = listedReleases.Select(listedRelease => listedRelease with
            {
                Release = existingReleases.FirstOrDefault(s => s.ShortName == listedRelease.ShortName)
            }
        ).ToList();
        var unscrapedListedReleases = scrapeOptions.FullScrape
            ? checkedListedReleases.Where(s => s.Release == null || s.Release.LastUpdated < scrapeOptions.FullScrapeLastUpdated)
            : checkedListedReleases.Where(s => s.Release == null).ToList();
        if (scrapeOptions.ReverseOrder)
        {
            unscrapedListedReleases = unscrapedListedReleases.Reverse();
        }

        foreach (var currentRelease in unscrapedListedReleases)
        {
            if (scrapedReleases >= scrapeOptions.MaxReleases)
            {
                Log.Information($"Scraped {scrapedReleases} releases, exiting");
                return;
            }

            Release? release = await ScrapeReleaseWithRetryAsync(site, subSite, scrapeOptions, siteScraper, page, currentRelease);
            if (release != null)
            {
                LogScrapedReleaseDescription(release);
                await Task.Delay(3000);
            }

            scrapedReleases++;
        }
    }

    private async Task<Release?> ScrapeReleaseWithRetryAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, ListedRelease? currentRelease)
    {
        var strategy = new ResilienceStrategyBuilder<Release?>()
            .AddFallback(new FallbackStrategyOptions<Release?>
            {
                FallbackAction = _ => Outcome.FromResultAsTask<Release?>(null)
            })
            .AddRetry(new RetryStrategyOptions<Release?>()
            {
                RetryCount = 3,
                BaseDelay = TimeSpan.FromSeconds(3),
                OnRetry = args =>
                {
                    Log.Error($"Caught following exception while scraping {currentRelease.Url}: " + args.Exception?.ToString(),
                        args.Exception);
                    return default;
                }
            })
            .Build();

        var release = await strategy.ExecuteAsync(async token =>
            await ScrapeReleaseAsync(currentRelease, siteScraper, site, subSite, page, scrapeOptions)
        );
        return release;
    }

    private static async Task<IReadOnlyList<ListedRelease>> ScrapePageListedReleasesAsync(Site site, SubSite subSite, ISiteScraper siteScraper, IPage page, int currentPage)
    {
        var indexRetryStrategy = new ResilienceStrategyBuilder<IReadOnlyList<ListedRelease>>()
            .AddRetry(new RetryStrategyOptions<IReadOnlyList<ListedRelease>>()
            {
                RetryCount = 3,
                BaseDelay = TimeSpan.FromSeconds(3),
                OnRetry = args =>
                {
                    Log.Error($"Caught following exception while scraping index page {currentPage}: " + args.Exception,
                        args.Exception);
                    return default;
                }
            })
            .Build();

        var listedReleases = await indexRetryStrategy.ExecuteAsync(async token =>
        {
            var requests = new List<IRequest>();
            await page.RouteAsync("**/*", async route =>
            {
                requests.Add(route.Request);
                await route.ContinueAsync();
            });

            var listedReleases = await siteScraper.GetCurrentReleasesAsync(site, subSite, page, requests, currentPage);
            return listedReleases;
        });
        return listedReleases;
    }

    private static void LogScrapedReleaseDescription(Release release)
    {
        var releaseDescription = new {
            Site = release.Site.Name,
            SubSite = release.SubSite?.Name,
            ShortName = release.ShortName,
            ReleaseDate = release.ReleaseDate,
            Name = release.Name,
            Url = release.Url.StartsWith("https://")
                ? release.Url
                : release.Site.Url + release.Url };
        Log.Information("Scraped release: {@Release}", releaseDescription);
    }

    private async Task<Release?> ScrapeReleaseAsync(ListedRelease currentRelease, ISiteScraper siteScraper, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions)
    {
        var releasePage = await page.Context.NewPageAsync();

        try
        {
            var requests = new List<IRequest>();
            await releasePage.RouteAsync("**/*", async route =>
            {
                requests.Add(route.Request);
                await route.ContinueAsync();
            });

            await releasePage.GotoAsync(currentRelease.Url);
            await releasePage.WaitForLoadStateAsync();

            await Task.Delay(1000);

            var releaseUuid = currentRelease.Release?.Uuid ?? UuidGenerator.Generate();
            var release = await siteScraper.ScrapeReleaseAsync(releaseUuid, site, subSite, currentRelease.Url, currentRelease.ShortName, releasePage, requests);
            if (release == null)
            {
                return null;
            }

            return await _repository.UpsertRelease(release);
        }
        finally
        {
            await releasePage.CloseAsync();
        }
    }

    public async Task DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions)
    {
        IScraper scraper = (IScraper)_serviceProvider.GetService(typeof(IScraper));
        Log.Information($"Culture Extractor, using {scraper.GetType()}");


        if (scraper is IYieldingScraper yieldingScraper)
        {
            await foreach (var download in yieldingScraper.DownloadReleasesAsync(site, browserSettings, downloadConditions, downloadOptions))
            {
                Log.Information($"Downloaded {download.AvailableFile.FileType} {download.AvailableFile.ContentType} {download.AvailableFile.Variant} of {download.Release.Name} from {download.Release.Site.Name}.");
                await _repository.SaveDownloadAsync(download, downloadConditions.PreferredDownloadQuality);
            }

            return;
        }

        var matchingReleases = await _repository.QueryReleasesAsync(site, downloadConditions, downloadOptions);
        var furtherFilteredReleases = matchingReleases
            .Where(s =>
                downloadConditions.DateRange.Start <= s.ReleaseDate &&
                s.ReleaseDate <= downloadConditions.DateRange.End)
            .Where(s =>
                !downloadConditions.PerformerNames.Any() ||
                s.Performers.Any(p => downloadConditions.PerformerNames.Contains(p.Name)))
            .Where(s =>
                !downloadConditions.ReleaseUuids.Any() ||
                downloadConditions.ReleaseUuids.Contains(s.ShortName))
            .ToList();

        if (!string.IsNullOrWhiteSpace(downloadOptions.SubSite))
        {
            furtherFilteredReleases = furtherFilteredReleases
                .Where(s => s.SubSite != null && s.SubSite.ShortName == downloadOptions.SubSite)
                .ToList();
        }
        if (downloadOptions.MaxReleases != int.MaxValue)
        {
            furtherFilteredReleases = furtherFilteredReleases
                .Take(downloadOptions.MaxReleases)
                .ToList();
        }

        if (downloadOptions.ReverseOrder)
        {
            furtherFilteredReleases = furtherFilteredReleases.OrderByDescending(s => s.ReleaseDate).ToList();
        }
        else
        {
            furtherFilteredReleases = furtherFilteredReleases.OrderBy(s => s.ReleaseDate).ToList();
        }

        
        var matchingReleasesStr = string.Join($"{Environment.NewLine}    ", matchingReleases.Select(s => $"{s.Site.Name} - {s.ReleaseDate.ToString("yyyy-MM-dd")} - {s.Name}"));
        
        var siteScraper = (ISiteScraper)scraper;
        Log.Information($"Found {matchingReleases.Count()} releases:{Environment.NewLine}    {matchingReleasesStr}");

        if (!matchingReleases.Any())
        {
            Log.Information("Nothing to download.");
            return;
        }
        
        IPage page = await CreatePageAndLoginAsync(siteScraper, site, browserSettings, false);

        var rippedReleases = 0;

        foreach (var matchingRelease in matchingReleases)
        {
            if (rippedReleases >= downloadConditions.MaxDownloads)
            {
                Log.Information($"Maximum release rip limit of {downloadConditions.MaxDownloads} reached. Stopping...");
                break;
            }
            if ((matchingReleases.Count() - rippedReleases) % 10 == 0)
            {
                Log.Information($"Remaining downloads {matchingReleases.Count() - rippedReleases}/{matchingReleases.Count()} releases.");
            }

            // Ungh, throws exception
            _downloader.CheckFreeSpace();

            IPage releasePage = null; 
            const int maxRetries = 3;
            for (int retries = 0; retries < maxRetries; retries++)
            {
                try
                {
                    if (retries > 0)
                    {
                        Log.Information($"Retrying {retries + 1} attempt for {matchingRelease.Url}");
                        await page.ReloadAsync();
                    }

                    var existingRelease = await _repository.GetReleaseAsync(site.ShortName, matchingRelease.ShortName);

                    releasePage = await page.Context.NewPageAsync();

                    var requests = new List<IRequest>();
                    await releasePage.RouteAsync("**/*", async route =>
                    {
                        requests.Add(route.Request);
                        await route.ContinueAsync();
                    });

                    await releasePage.GotoAsync(matchingRelease.Url);
                    await releasePage.WaitForLoadStateAsync();

                    var releaseUuid = existingRelease?.Uuid ?? UuidGenerator.Generate();
                    var release = await siteScraper.ScrapeReleaseAsync(releaseUuid, site, null, matchingRelease.Url, matchingRelease.ShortName, releasePage, requests);
                    existingRelease = await _repository.UpsertRelease(release);

                    var releaseDescription = new {
                        Site = existingRelease.Site.Name,
                        ReleaseDate = existingRelease.ReleaseDate,
                        Name = existingRelease.Name,
                        Url = existingRelease.Url.StartsWith("https://")
                            ? existingRelease.Url
                            : existingRelease.Site.Url + existingRelease.Url,
                        Quality = downloadConditions.PreferredDownloadQuality
                    };
                    Log.Verbose("Downloading: {@Release}", releaseDescription);

                    var download = await siteScraper.DownloadReleaseAsync(existingRelease, releasePage, downloadConditions, requests);
                    await _repository.SaveDownloadAsync(download, downloadConditions.PreferredDownloadQuality);

                    rippedReleases++;

                    var releaseDescription2 = new
                    {
                        Site = existingRelease.Site.Name,
                        ReleaseDate = existingRelease.ReleaseDate,
                        Name = existingRelease.Name,
                        Url = existingRelease.Url.StartsWith("https://")
                            ? existingRelease.Url
                            : existingRelease.Site.Url + existingRelease.Url,
                        Quality = downloadConditions.PreferredDownloadQuality,
                        Phash = (download.FileMetadata as VideoFileMetadata)?.Hashes.PHash
                    };
                    Log.Information("Downloaded:  {@Release}", releaseDescription2);
                    await Task.Delay(3000);
                    break;
                }
                catch (PlaywrightException ex)
                {
                    // Let's try again
                    Log.Error(ex.Message, ex);
                }
                catch (TimeoutException ex)
                {
                    // Let's try again
                    Log.Error(ex.Message, ex);
                }
                catch (ExtractorException ex)
                {
                    Log.Error(ex.Message, ex);
                    if (ex.ShouldRetry)
                    {
                        continue;
                    }
                    else
                    {
                        break;
                    }
                }
                catch (Exception ex)
                {
                    Log.Error(ex.ToString(), ex);
                    await Task.Delay(3000);
                }
                finally
                {
                    if (releasePage != null)
                    {
                        await releasePage.CloseAsync();
                    }
                }

                if (retries == maxRetries)
                {
                    Log.Warning($"Failed to scrape {matchingRelease.Url}");
                }
            }
        }
    }

    private async Task<IPage> CreatePageAndLoginAsync(ISiteScraper siteScraper, Site site, BrowserSettings browserSettings, bool guestMode)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        if (!guestMode)
        {
            await siteScraper.LoginAsync(site, page);
            await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        }

        return page;
    }
}
