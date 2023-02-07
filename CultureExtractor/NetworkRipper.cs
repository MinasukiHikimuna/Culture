using CultureExtractor.Exceptions;
using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor;

public class NetworkRipper : INetworkRipper
{
    private readonly IRepository _repository;
    private readonly IServiceProvider _serviceProvider;
    private readonly IDownloader _downloader;

    public NetworkRipper(IRepository repository, IServiceProvider serviceProvider, IDownloader downloader)
    {
        _repository = repository;
        _serviceProvider = serviceProvider;
        _downloader = downloader;
    }

    public async Task ScrapeScenesAsync(Site site, BrowserSettings browserSettings, bool fullScrape)
    {
        ISceneScraper sceneScraper = (ISceneScraper) _serviceProvider.GetService(typeof(ISceneScraper));
        Log.Information($"Culture Extractor, using {sceneScraper.GetType()}");

        IPage page = await CreatePageAndLoginAsync(sceneScraper, site, browserSettings);
        var totalPages = await sceneScraper.NavigateToScenesAndReturnPageCountAsync(site, page);

        for (int currentPage = 1; currentPage <= totalPages; currentPage++)
        {
            await Task.Delay(5000);
            var currentScenes = await sceneScraper.GetCurrentScenesAsync(site, page);

            Log.Information(totalPages == int.MaxValue
                ? $"Batch {currentPage} of infinite page contains {currentScenes.Count} scenes"
                : $"Page {currentPage}/{totalPages} contains {currentScenes.Count} scenes");

            foreach (var currentScene in currentScenes)
            {
                for (int retries = 0; retries < 3; retries++)
                {
                    try
                    {
                        (string url, string sceneShortName) = await sceneScraper.GetSceneIdAsync(site, currentScene);

                        if (retries > 0)
                        {
                            Log.Information($"Retrying {retries + 1} attempt for {url}");
                        }

                        var existingScene = await _repository.GetSceneAsync(site.ShortName, sceneShortName);
                        if (existingScene == null || fullScrape)
                        {
                            var scenePage = await page.Context.NewPageAsync();

                            var responses = new List<CapturedResponse>();
                            EventHandler<IResponse> responseCapturer = async (_, response) =>
                            {
                                var capturedResponse = await sceneScraper.FilterResponsesAsync(sceneShortName, response);
                                if (capturedResponse != null)
                                {
                                    responses.Add(capturedResponse);
                                }
                            };
                            scenePage.Response += responseCapturer;

                            await scenePage.GotoAsync(url);
                            await scenePage.WaitForLoadStateAsync();

                            await Task.Delay(1000);

                            scenePage.Response -= responseCapturer;

                            var scene = await sceneScraper.ScrapeSceneAsync(site, url, sceneShortName, scenePage, responses);
                            if (existingScene != null)
                            {
                                scene = scene with { Id = existingScene.Id };
                            }

                            var savedScene = await _repository.UpsertScene(scene);
                            await sceneScraper.DownloadPreviewImageAsync(savedScene, scenePage, page, currentScene);

                            await scenePage.CloseAsync();

                            var sceneDescription = new { Site = scene.Site.Name, ReleaseDate = scene.ReleaseDate, Name = scene.Name, Url = site.Url + url };
                            Log.Information("Scraped scene: {@Scene}", sceneDescription);
                            await Task.Delay(3000);
                        }
                        // TODO: need to figure out how we can do initial scraping, this is used for new sensations and its 323 pages
                        /*else
                        {
                            Log.Information($"An existing scene {existingScene.ReleaseDate} {existingScene.Name} found. Assuming older scenes have already been scraped.");
                            return;
                        }*/
                        break;
                    }
                    catch (Exception ex)
                    {
                        Log.Error(ex.ToString(), ex);
                        await Task.Delay(3000);
                    }
                }
            }

            if (currentPage != totalPages)
            {
                await sceneScraper.GoToNextFilmsPageAsync(page);
            }
        }
    }

    public async Task DownloadScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        var matchingScenes = await _repository.QueryScenesAsync(site, downloadConditions.PreferredDownloadQuality);

        var furtherFilteredScenes = matchingScenes
            .Where(s =>
                downloadConditions.DateRange.Start <= s.ReleaseDate &&
                s.ReleaseDate <= downloadConditions.DateRange.End)
            .Where(s =>
                !downloadConditions.PerformerNames.Any() ||
                s.Performers.Any(p => downloadConditions.PerformerNames.Contains(p.Name)))
            .Where(s =>
                !downloadConditions.SceneIds.Any() ||
                downloadConditions.SceneIds.Contains(s.ShortName))
            .ToList();

        await DownloadGivenScenesAsync(
            site,
            browserSettings,
            downloadConditions,
            furtherFilteredScenes.ToList());
    }

    private async Task DownloadGivenScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, IList<Scene> matchingScenes)
    {
        var matchingScenesStr = string.Join($"{Environment.NewLine}    ", matchingScenes.Select(s => $"{s.Site.Name} - {s.ReleaseDate.ToString("yyyy-MM-dd")} - {s.Name}"));

        ISceneDownloader sceneDownloader = (ISceneDownloader)_serviceProvider.GetService(typeof(ISceneDownloader));
        Log.Information($"Culture Extractor, using {sceneDownloader.GetType()}");

        Log.Information($"Found {matchingScenes.Count} scenes:{Environment.NewLine}    {matchingScenesStr}");

        if (!matchingScenes.Any())
        {
            Log.Information("Nothing to download.");
            return;
        }

        IPage page = await CreatePageAndLoginAsync(sceneDownloader, site, browserSettings);

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

            for (int retries = 0; retries < 3; retries++)
            {
                try
                {
                    if (retries > 0)
                    {
                        Log.Information($"Retrying {retries + 1} attempt for {matchingScene.Url}");
                    }

                    var existingScene = await _repository.GetSceneAsync(site.ShortName, matchingScene.ShortName);

                    var scenePage = await page.Context.NewPageAsync();

                    ISceneScraper sceneScraper = null;
                    if (sceneDownloader is ISceneScraper scraper)
                    {
                        sceneScraper = scraper;
                    }

                    var responses = new List<CapturedResponse>();
                    EventHandler<IResponse> responseCapturer = null;
                    if (sceneScraper != null) {
                        responseCapturer = async (_, response) =>
                        {
                            var capturedResponse = await sceneScraper.FilterResponsesAsync(matchingScene.ShortName, response);
                            if (capturedResponse != null)
                            {
                                responses.Add(capturedResponse);
                            }
                        };
                        scenePage.Response += responseCapturer;
                    }

                    await scenePage.GotoAsync(matchingScene.Url);
                    await scenePage.WaitForLoadStateAsync();

                    await Task.Delay(1000);

                    if (sceneScraper != null)
                    {
                        scenePage.Response -= responseCapturer;
                    }

                    if (sceneScraper != null)
                    {
                        var scene = await sceneScraper.ScrapeSceneAsync(site, matchingScene.Url, matchingScene.ShortName, scenePage, responses);
                        if (existingScene != null)
                        {
                            scene = scene with { Id = existingScene.Id };
                        }

                        existingScene = await _repository.UpsertScene(scene);
                    }

                    var sceneDescription = new {
                        Site = existingScene.Site.Name,
                        ReleaseDate = existingScene.ReleaseDate,
                        Name = existingScene.Name,
                        Url = site.Url + existingScene.Url,
                        Quality = downloadConditions.PreferredDownloadQuality };
                    Log.Verbose("Downloading: {@Scene}", sceneDescription);

                    var download = await sceneDownloader.DownloadSceneAsync(existingScene, scenePage, downloadConditions, responses);
                    await _repository.SaveDownloadAsync(download, downloadConditions.PreferredDownloadQuality);

                    rippedScenes++;

                    await scenePage.CloseAsync();

                    Log.Information("Downloaded:  {@Scene}", sceneDescription);
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
                catch (DownloadException ex)
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
            }
        }
    }

    private async Task<IPage> CreatePageAndLoginAsync(ISiteScraper siteScraper, Site site, BrowserSettings browserSettings)
    {
        IPage page = await PlaywrightFactory.CreatePageAsync(site, browserSettings);
        await siteScraper.LoginAsync(site, page);

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
        return page;
    }
}
