using CultureExtractor.Exceptions;
using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Reflection;
using System.Runtime.CompilerServices;

namespace CultureExtractor;

public class NetworkRipper : INetworkRipper
{
    private readonly IRepository _repository;
    private readonly IServiceProvider _serviceProvider;

    public NetworkRipper(IRepository repository, IServiceProvider serviceProvider)
    {
        _repository = repository;
        _serviceProvider = serviceProvider;
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
                            var scenePage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });
                            await scenePage.WaitForLoadStateAsync();

                            var scene = await sceneScraper.ScrapeSceneAsync(site, url, sceneShortName, scenePage);
                            if (existingScene != null)
                            {
                                scene = scene with { Id = existingScene.Id };
                            }

                            var savedScene = await _repository.UpsertScene(scene);
                            await sceneScraper.DownloadPreviewImageAsync(savedScene, scenePage, page, currentScene);

                            await scenePage.CloseAsync();

                            Log.Information($"Scraped scene {savedScene.Id}: {url}");
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
                !downloadConditions.PerformerShortNames.Any() ||
                s.Performers.Any(p => downloadConditions.PerformerShortNames.Contains(p.ShortName)))
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
        ISceneScraper sceneScraper = (ISceneScraper) sceneDownloader;
        Log.Information($"Culture Extractor, using {sceneDownloader.GetType()}");

        Log.Information($"Found {matchingScenes.Count} scenes:{Environment.NewLine}    {matchingScenesStr}");

        if (!matchingScenes.Any())
        {
            Log.Information("Nothing to download.");
            return;
        }

        IPage page = await CreatePageAndLoginAsync(sceneDownloader, site, browserSettings);

        // TODO: investigate later how we could utilize these for example to download images
        // page.Request += (_, request) => Console.WriteLine(">> " + request.Method + " " + request.Url);
        // page.Response += (_, response) => Console.WriteLine("<< " + response.Status + " " + response.Url);

        var rippingPath = $@"B:\Ripping\{site.Name}\";
        const long minimumFreeDiskSpace = 5L * 1024 * 1024 * 1024;
        DirectoryInfo targetDirectory = new DirectoryInfo(rippingPath);

        var rippedScenes = 0;
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
                if (rippedScenes >= downloadConditions.MaxDownloads)
                {
                    Log.Information($"Maximum scene rip limit of {downloadConditions.MaxDownloads} reached. Stopping...");
                    break;
                }
                if ((matchingScenes.Count - rippedScenes) % 10 == 0)
                {
                    Log.Information($"Remaining downloads {matchingScenes.Count - rippedScenes}/{matchingScenes.Count} scenes.");
                }

                DriveInfo drive = new(targetDirectory.Root.FullName);
                if (drive.AvailableFreeSpace < minimumFreeDiskSpace)
                {
                    throw new InvalidOperationException($"Drive {drive.Name} has less than {minimumFreeDiskSpace} bytes free.");
                }

                for (int retries = 0; retries < 3; retries++)
                {
                    try
                    {
                        (string url, string sceneShortName) = await sceneScraper.GetSceneIdAsync(site, currentScene);

                        if (retries > 0)
                        {
                            Log.Information($"Retrying {retries + 1} attempt for {url}");
                        }

                        if (matchingScenes.Any(s => s.ShortName == sceneShortName))
                        {
                            var existingScene = await _repository.GetSceneAsync(site.ShortName, sceneShortName);
                            await currentScene.ScrollIntoViewIfNeededAsync();

                            var scenePage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });
                            await scenePage.WaitForLoadStateAsync();

                            var scene = await sceneScraper.ScrapeSceneAsync(site, url, sceneShortName, scenePage);
                            if (existingScene != null)
                            {
                                scene = scene with { Id = existingScene.Id };
                            }

                            var savedScene = await _repository.UpsertScene(scene);
                            await sceneScraper.DownloadPreviewImageAsync(savedScene, scenePage, page, currentScene);

                            var download = await sceneDownloader.DownloadSceneAsync(scene, scenePage, rippingPath, downloadConditions);
                            await _repository.SaveDownloadAsync(download, downloadConditions.PreferredDownloadQuality);

                            rippedScenes++;

                            await scenePage.CloseAsync();

                            Log.Information($"Downloaded scene {savedScene.Id}: {download.DownloadOption.Url}");
                            await Task.Delay(3000);
                        }
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

            if (currentPage != totalPages)
            {
                await sceneScraper.GoToNextFilmsPageAsync(page);
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
