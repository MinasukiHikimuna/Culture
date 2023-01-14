using CultureExtractor.Interfaces;
using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Serilog;
using System.Reflection;

namespace CultureExtractor;

public class NetworkRipper
{
    private readonly Repository _repository;

    public NetworkRipper(Repository repository)
    {
        _repository = repository;
    }

    public async Task InitializeAsync(string shortName, JobType jobType, BrowserSettings browserSettings)
    {
        var site = await _repository.GetSiteAsync(shortName);

        switch (jobType)
        {
            case JobType.ScrapeScenes:
                ISceneScraper? siteRipper = GetRipper<ISceneScraper>(shortName);
                Log.Information($"Culture Extractor, using {siteRipper.GetType()}");
                await ScrapeScenesAsync(siteRipper, site, browserSettings);
                break;
            case JobType.ScrapeGalleries:
                ISiteRipper? siteRipper2 = GetRipper<ISiteRipper>(shortName);
                Log.Information($"Culture Extractor, using {siteRipper2.GetType()}");
                await siteRipper2.ScrapeGalleriesAsync(shortName, browserSettings);
                break;
            case JobType.DownloadScenes:
                ISceneDownloader? sceneDownloader = GetRipper<ISceneDownloader>(shortName);
                Log.Information($"Culture Extractor, using {sceneDownloader.GetType()}");
                await DownloadScenesAsync(
                    sceneDownloader,
                    site,
                    new DownloadConditions(new DateRange(new DateOnly(2015, 11, 29), new DateOnly(2024, 01, 01)), null),
                    browserSettings);
                break;
            default:
                throw new Exception($"Could not find a ripper for job {Enum.GetName(jobType)} with site short name {shortName}");
        }
    }

    private async Task ScrapeScenesAsync(ISceneScraper sceneScraper, Site site, BrowserSettings browserSettings)
    {
        IPage page = await PlaywrightFactory.CreatePageAsync(site, browserSettings);
        await sceneScraper.LoginAsync(site, page);

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

        var totalPages = await sceneScraper.NavigateToScenesAndReturnPageCountAsync(site, page);

        for (int currentPage = 1; currentPage <= totalPages; currentPage++)
        {
            Thread.Sleep(5000);
            var currentScenes = await sceneScraper.GetCurrentScenesAsync(page);

            if (totalPages == int.MaxValue)
            {
                Log.Information($"First batch of infinite page contains {currentScenes.Count} scenes");
            }
            else
            {
                Log.Information($"Page {currentPage}/{totalPages} contains {currentScenes.Count} scenes");
            }
            
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
                        if (existingScene == null)
                        {
                            var newPage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });
                            await newPage.WaitForLoadStateAsync();

                            var scene = await sceneScraper.ScrapeSceneAsync(site, url, sceneShortName, newPage);
                            var savedScene = await _repository.SaveSceneAsync(scene);
                            await sceneScraper.DownloadPreviewImageAsync(savedScene, newPage, currentScene);

                            await newPage.CloseAsync();

                            Log.Information($"Scraped scene {savedScene.Id}: {url}");

                            Thread.Sleep(3000);
                        }

                        break;
                    }
                    catch (Exception ex)
                    {
                        Log.Error(ex.ToString(), ex);
                    }
                }
            }

            if (currentPage != totalPages)
            {
                await sceneScraper.GoToNextFilmsPageAsync(page);
            }
        }
    }

    public async Task DownloadScenesAsync(ISceneDownloader sceneDownloader, Site site, DownloadConditions conditions, BrowserSettings browserSettings)
    {
        var matchingScenes = await _repository._sqliteContext.Scenes
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Include(s => s.Site)
            .OrderBy(s => s.ReleaseDate)
            .Where(s => s.SiteId == site.Id)
            .Where(s => conditions.DateRange == null || (conditions.DateRange.Start <= s.ReleaseDate && s.ReleaseDate <= conditions.DateRange.End))
            .Where(s => conditions.PerformerShortName == null || s.Performers.Any(p => p.ShortName == conditions.PerformerShortName))
        .ToListAsync();

        var matchingScenesStr = string.Join($"{Environment.NewLine}    ", matchingScenes.Select(s => $"{s.Site.Name} - {s.ReleaseDate.ToString("yyyy-MM-dd")} - {s.Name}"));

        Log.Information($"Found {matchingScenes.Count()} scenes:{Environment.NewLine}    {matchingScenesStr}");

        if (!matchingScenes.Any())
        {
            Log.Information("Nothing to download.");
            return;
        }

        IPage page = await PlaywrightFactory.CreatePageAsync(site, browserSettings);

        await sceneDownloader.LoginAsync(site, page);

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

        var rippingPath = $@"I:\Ripping\{site.Name}\";
        foreach (var scene in matchingScenes)
        {
            for (int retries = 0; retries < 3; retries++)
            {
                try
                {
                    if (retries > 0)
                    {
                        Log.Information($"Retrying {retries + 1} attempt for {scene.Url}");
                    }

                    await sceneDownloader.DownloadSceneAsync(scene, page, rippingPath);
                    break;
                }
                catch (PlaywrightException ex)
                {
                    // Let's try again
                    Log.Error(ex.Message, ex);
                }
            }
        }
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
