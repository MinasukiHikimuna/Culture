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

    public async Task ScrapeScenesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        ISiteScraper siteScraper = (ISiteScraper)_serviceProvider.GetService(typeof(ISiteScraper));
        Log.Information($"Culture Extractor, using {siteScraper.GetType()}");

        if (siteScraper is ISubSiteScraper subSiteScraper)
        {
            await ScrapeSubSiteScenesAsync(site, browserSettings, scrapeOptions, subSiteScraper);
        }
        else
        {
            IPage page = await CreatePageAndLoginAsync(siteScraper, site, browserSettings, scrapeOptions.GuestMode);
            var totalPages = await siteScraper.NavigateToScenesAndReturnPageCountAsync(site, page);

            await ScrapeScenesInternalAsync(site, null, scrapeOptions, siteScraper, page, totalPages);
        }
    }

    private async Task ScrapeSubSiteScenesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions, ISubSiteScraper subSiteScraper)
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
            await ScrapeScenesInternalAsync(site, subSite, scrapeOptions, subSiteScraper, page, totalPages);
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

    private async Task ScrapeScenesInternalAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, int totalPages)
    {
        foreach (var currentPage in PageEnumeration(scrapeOptions, totalPages))
        {
            await ScrapeScenePageAsync(site, subSite, scrapeOptions, siteScraper, page, totalPages, currentPage);
        }
    }

    private async Task ScrapeScenePageAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, int totalPages, int currentPage)
    {
        var scrapedScenes = 0;

        IReadOnlyList<IndexScene> indexScenes = await ScrapePageIndexScenesAsync(site, subSite, siteScraper, page, currentPage);

        Log.Information(totalPages == int.MaxValue
            ? $"Batch {currentPage} of infinite page contains {indexScenes.Count} scenes"
            : $"Page {currentPage}/{totalPages} contains {indexScenes.Count} scenes");

        var existingScenes = await _repository.GetReleasesAsync(site.ShortName, indexScenes.Select(s => s.ShortName).ToList());
        var checkedIndexScenes = indexScenes.Select(indexScene => indexScene with
            {
                Scene = existingScenes.FirstOrDefault(s => s.ShortName == indexScene.ShortName)
            }
        ).ToList();
        var unscrapedIndexScenes = scrapeOptions.FullScrape
            ? checkedIndexScenes.Where(s => s.Scene == null || s.Scene.LastUpdated < scrapeOptions.FullScrapeLastUpdated)
            : checkedIndexScenes.Where(s => s.Scene == null).ToList();
        if (scrapeOptions.ReverseOrder)
        {
            unscrapedIndexScenes = unscrapedIndexScenes.Reverse();
        }

        foreach (var currentScene in unscrapedIndexScenes)
        {
            if (scrapedScenes >= scrapeOptions.MaxScenes)
            {
                Log.Information($"Scraped {scrapedScenes} scenes, exiting");
                return;
            }

            Release? scene = await ScrapeSceneWithRetryAsync(site, subSite, scrapeOptions, siteScraper, page, currentScene);
            if (scene != null)
            {
                LogScrapedSceneDescription(scene);
                await Task.Delay(3000);
            }

            scrapedScenes++;
        }
    }

    private async Task<Release?> ScrapeSceneWithRetryAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, IndexScene? currentScene)
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
                    Log.Error($"Caught following exception while scraping {currentScene.Url}: " + args.Exception?.ToString(),
                        args.Exception);
                    return default;
                }
            })
            .Build();

        var scene = await strategy.ExecuteAsync(async token =>
            await ScrapeSceneAsync(currentScene, siteScraper, site, subSite, page, scrapeOptions)
        );
        return scene;
    }

    private static async Task<IReadOnlyList<IndexScene>> ScrapePageIndexScenesAsync(Site site, SubSite subSite, ISiteScraper siteScraper, IPage page, int currentPage)
    {
        var indexRetryStrategy = new ResilienceStrategyBuilder<IReadOnlyList<IndexScene>>()
            .AddRetry(new RetryStrategyOptions<IReadOnlyList<IndexScene>>()
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

        var indexScenes = await indexRetryStrategy.ExecuteAsync(async token =>
        {
            var requests = new List<IRequest>();
            await page.RouteAsync("**/*", async route =>
            {
                requests.Add(route.Request);
                await route.ContinueAsync();
            });

            var indexScenes = await siteScraper.GetCurrentScenesAsync(site, subSite, page, requests, currentPage);
            return indexScenes;
        });
        return indexScenes;
    }

    private static void LogScrapedSceneDescription(Release release)
    {
        var sceneDescription = new {
            Site = release.Site.Name,
            SubSite = release.SubSite?.Name,
            ShortName = release.ShortName,
            ReleaseDate = release.ReleaseDate,
            Name = release.Name,
            Url = release.Url.StartsWith("https://")
                ? release.Url
                : release.Site.Url + release.Url };
        Log.Information("Scraped scene: {@Scene}", sceneDescription);
    }

    private async Task<Release?> ScrapeSceneAsync(IndexScene currentScene, ISiteScraper siteScraper, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions)
    {
        var scenePage = await page.Context.NewPageAsync();

        try
        {
            var requests = new List<IRequest>();
            await scenePage.RouteAsync("**/*", async route =>
            {
                requests.Add(route.Request);
                await route.ContinueAsync();
            });

            await scenePage.GotoAsync(currentScene.Url);
            await scenePage.WaitForLoadStateAsync();

            await Task.Delay(1000);

            var sceneUuid = currentScene.Scene?.Uuid ?? UuidGenerator.Generate();
            var scene = await siteScraper.ScrapeSceneAsync(sceneUuid, site, subSite, currentScene.Url, currentScene.ShortName, scenePage, requests);
            if (scene == null)
            {
                return null;
            }

            return await _repository.UpsertScene(scene);
        }
        finally
        {
            await scenePage.CloseAsync();
        }
    }

    public async Task DownloadScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions)
    {
        var matchingScenes = await _repository.QueryReleasesAsync(site, downloadConditions);

        var furtherFilteredScenes = matchingScenes
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
            furtherFilteredScenes = furtherFilteredScenes
                .Where(s => s.SubSite != null && s.SubSite.ShortName == downloadOptions.SubSite)
                .ToList();
        }
        if (downloadOptions.MaxScenes != int.MaxValue)
        {
            furtherFilteredScenes = furtherFilteredScenes
                .Take(downloadOptions.MaxScenes)
                .ToList();
        }

        if (downloadOptions.ReverseOrder)
        {
            furtherFilteredScenes = furtherFilteredScenes.OrderByDescending(s => s.ReleaseDate).ToList();
        }
        else
        {
            furtherFilteredScenes = furtherFilteredScenes.OrderBy(s => s.ReleaseDate).ToList();
        }

        await DownloadGivenScenesAsync(
            site,
            browserSettings,
            downloadConditions,
            furtherFilteredScenes.ToList());
    }

    private async Task DownloadGivenScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, IList<Release> matchingScenes)
    {
        var matchingScenesStr = string.Join($"{Environment.NewLine}    ", matchingScenes.Select(s => $"{s.Site.Name} - {s.ReleaseDate.ToString("yyyy-MM-dd")} - {s.Name}"));

        ISiteScraper siteScraper = (ISiteScraper)_serviceProvider.GetService(typeof(ISiteScraper));
        Log.Information($"Culture Extractor, using {siteScraper.GetType()}");

        Log.Information($"Found {matchingScenes.Count} scenes:{Environment.NewLine}    {matchingScenesStr}");

        if (!matchingScenes.Any())
        {
            Log.Information("Nothing to download.");
            return;
        }

        IPage page = await CreatePageAndLoginAsync(siteScraper, site, browserSettings, false);

        var rippedScenes = 0;

        foreach (var matchingScene in matchingScenes)
        {
            if (rippedScenes >= downloadConditions.MaxDownloads)
            {
                Log.Information($"Maximum scene rip limit of {downloadConditions.MaxDownloads} reached. Stopping...");
                break;
            }
            if ((matchingScenes.Count - rippedScenes) % 10 == 0)
            {
                Log.Information($"Remaining downloads {matchingScenes.Count - rippedScenes}/{matchingScenes.Count} scenes.");
            }

            // Ungh, throws exception
            _downloader.CheckFreeSpace();

            IPage scenePage = null;
            const int maxRetries = 3;
            for (int retries = 0; retries < maxRetries; retries++)
            {
                try
                {
                    if (retries > 0)
                    {
                        Log.Information($"Retrying {retries + 1} attempt for {matchingScene.Url}");
                        await page.ReloadAsync();
                    }

                    var existingScene = await _repository.GetSceneAsync(site.ShortName, matchingScene.ShortName);

                    scenePage = await page.Context.NewPageAsync();

                    var requests = new List<IRequest>();
                    await scenePage.RouteAsync("**/*", async route =>
                    {
                        requests.Add(route.Request);
                        await route.ContinueAsync();
                    });

                    await scenePage.GotoAsync(matchingScene.Url);
                    await scenePage.WaitForLoadStateAsync();

                    var sceneUuid = existingScene?.Uuid ?? UuidGenerator.Generate();
                    var scene = await siteScraper.ScrapeSceneAsync(sceneUuid, site, null, matchingScene.Url, matchingScene.ShortName, scenePage, requests);
                    existingScene = await _repository.UpsertScene(scene);

                    var sceneDescription = new {
                        Site = existingScene.Site.Name,
                        ReleaseDate = existingScene.ReleaseDate,
                        Name = existingScene.Name,
                        Url = existingScene.Url.StartsWith("https://")
                            ? existingScene.Url
                            : existingScene.Site.Url + existingScene.Url,
                        Quality = downloadConditions.PreferredDownloadQuality
                    };
                    Log.Verbose("Downloading: {@Scene}", sceneDescription);

                    var download = await siteScraper.DownloadSceneAsync(existingScene, scenePage, downloadConditions, requests);
                    await _repository.SaveDownloadAsync(download, downloadConditions.PreferredDownloadQuality);

                    rippedScenes++;

                    var sceneDescription2 = new
                    {
                        Site = existingScene.Site.Name,
                        ReleaseDate = existingScene.ReleaseDate,
                        Name = existingScene.Name,
                        Url = existingScene.Url.StartsWith("https://")
                            ? existingScene.Url
                            : existingScene.Site.Url + existingScene.Url,
                        Quality = downloadConditions.PreferredDownloadQuality,
                        Phash = download.VideoHashes?.PHash
                    };
                    Log.Information("Downloaded:  {@Scene}", sceneDescription2);
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
                    if (scenePage != null)
                    {
                        await scenePage.CloseAsync();
                    }
                }

                if (retries == maxRetries)
                {
                    Log.Warning($"Failed to scrape {matchingScene.Url}");
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
