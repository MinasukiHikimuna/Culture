using CultureExtractor.Exceptions;
using CultureExtractor.Interfaces;
using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Serilog;
using System.Reflection;
using System.Text.Json;

namespace CultureExtractor;

public class NetworkRipper
{
    private readonly Repository _repository;

    public NetworkRipper(Repository repository)
    {
        _repository = repository;
    }

    public async Task ScrapeScenesAsync(Site site, BrowserSettings browserSettings, bool fullScrape)
    {
        ISceneScraper? sceneScraper = GetRipper<ISceneScraper>(site.ShortName);
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
                        else
                        {
                            Log.Information($"An existing scene {existingScene.ReleaseDate} {existingScene.Name} found. Assuming older scenes have already been scraped.");
                            return;
                        }
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

        var furtherFilteredScenes = matchingScenes.Where(s =>
            downloadConditions.DateRange.Start <= s.ReleaseDate &&
            s.ReleaseDate <= downloadConditions.DateRange.End).ToList();

        await DownloadGivenScenesAsync(
            site,
            browserSettings,
            downloadConditions,
            furtherFilteredScenes.ToList());
    }

    public async Task UpsizeScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, IList<string> fileNames)
    {
        throw new NotImplementedException("Upsizing is not yet supported!");

        /*var preferredDownloadQuality = Enum.GetName(downloadConditions.PreferredDownloadQuality);

        var matchingScenes = await _repository.QueryScenesAsync(site, downloadConditions.PreferredDownloadQuality);
        var matchingScenes = await _repository._sqliteContext.Scenes
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Include(s => s.Site)
            .Include(s => s.Downloads)
            .OrderBy(s => s.ReleaseDate)
            .Where(s => s.Downloads.Any(d => fileNames.Contains(d.SavedFilename)))
            .Where(s => !s.Downloads.Any(d => d.DownloadQuality == preferredDownloadQuality))
        .ToListAsync();*/

        /*await DownloadGivenScenesAsync(
            site,
            browserSettings,
            downloadConditions,
            matchingScenes);*/
    }

    private async Task DownloadGivenScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, IList<Scene> matchingScenes)
    {
        var matchingScenesStr = string.Join($"{Environment.NewLine}    ", matchingScenes.Select(s => $"{s.Site.Name} - {s.ReleaseDate.ToString("yyyy-MM-dd")} - {s.Name}"));

        ISceneDownloader? sceneDownloader = GetRipper<ISceneDownloader>(site.ShortName);
        Log.Information($"Culture Extractor, using {sceneDownloader.GetType()}");

        Log.Information($"Found {matchingScenes.Count} scenes:{Environment.NewLine}    {matchingScenesStr}");

        if (!matchingScenes.Any())
        {
            Log.Information("Nothing to download.");
            return;
        }

        IPage page = await CreatePageAndLoginAsync(sceneDownloader, site, browserSettings);

        var rippingPath = $@"B:\Ripping\{site.Name}\";
        const long minimumFreeDiskSpace = 5L * 1024 * 1024 * 1024;
        DirectoryInfo targetDirectory = new DirectoryInfo(rippingPath);

        var rippedScenes = 0;
        foreach (var scene in matchingScenes)
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
                    if (retries > 0)
                    {
                        Log.Information($"Retrying {retries + 1} attempt for {scene.Url}");
                    }

                    var download = await sceneDownloader.DownloadSceneAsync(scene, page, rippingPath, downloadConditions);
                    await _repository.SaveDownloadAsync(download, downloadConditions.PreferredDownloadQuality);

                    await Task.Delay(3000);

                    rippedScenes++;
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

    private static T GetRipper<T>(string shortName) where T : class
    {
        Type attributeType = typeof(PornSiteAttribute);

        var siteRipperTypes = Assembly
            .GetExecutingAssembly()
            .GetTypes()
            .Where(type => typeof(T).IsAssignableFrom(type))
            .Where(type =>
            {
                object[] attributes = type.GetCustomAttributes(attributeType, true);
                return attributes.Length > 0 && attributes.Any(attribute => (attribute as PornSiteAttribute)?.ShortName == shortName);
            });

        if (!siteRipperTypes.Any())
        {
            throw new ArgumentException($"Could not find any class with short name {shortName} with type {typeof(T)}");
        }
        if (siteRipperTypes.Count() > 2)
        {
            throw new ArgumentException($"Found more than one classes with short name {shortName} with type {typeof(T)}");
        }

        var siteRipperType = siteRipperTypes.First();
        if (Activator.CreateInstance(siteRipperType) is not T siteRipper)
        {
            throw new ArgumentException($"Could not instantiate a class with type {siteRipperType}");
        }

        return siteRipper;
    }
}
