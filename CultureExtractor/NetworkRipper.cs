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

    public async Task InitializeAsync(string shortName, JobType jobType, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        var site = await _repository.GetSiteAsync(shortName);

        switch (jobType)
        {
            case JobType.ScrapeScenes:
                ISceneScraper? siteRipper = GetRipper<ISceneScraper>(shortName);
                Log.Information($"Culture Extractor, using {siteRipper.GetType()}");
                await ScrapeScenesAsync(siteRipper, site, browserSettings);
                break;
            case JobType.DownloadScenes:
                ISceneDownloader? sceneDownloader = GetRipper<ISceneDownloader>(shortName);
                Log.Information($"Culture Extractor, using {sceneDownloader.GetType()}");

                var preferredDownloadQuality = Enum.GetName(downloadConditions.PreferredDownloadQuality);

                var matchingScenes = await _repository._sqliteContext.Scenes
                    .Include(s => s.Performers)
                    .Include(s => s.Tags)
                    .Include(s => s.Site)
                    .Include(s => s.Downloads)
                    .OrderBy(s => s.ReleaseDate)
                    .Where(s => s.SiteId == site.Id)
                    .Where(s => downloadConditions.DateRange == null || (downloadConditions.DateRange.Start <= s.ReleaseDate && s.ReleaseDate <= downloadConditions.DateRange.End))
                    .Where(s => downloadConditions.PerformerShortName == null || s.Performers.Any(p => p.ShortName == downloadConditions.PerformerShortName))
                    .Where(s => !s.Downloads.Any(d => d.DownloadQuality == preferredDownloadQuality))
                .ToListAsync();

                await DownloadScenesAsync(
                    sceneDownloader,
                    matchingScenes,
                    site,
                    downloadConditions,
                    browserSettings);
                break;
            case JobType.UpsizeDownloadedScenes:
                ISceneDownloader? sceneDownloader2 = GetRipper<ISceneDownloader>(shortName);
                Log.Information($"Culture Extractor, using {sceneDownloader2.GetType()}");

                var preferredDownloadQuality2 = Enum.GetName(downloadConditions.PreferredDownloadQuality);

                var fileNames = new List<string>
                {
                    @" - PurgatoryX - 2021-07-09 - My Wife’s Massage Vol 2 E1.mp4",
                    @"Aidra Fox & Donnie Rock - PurgatoryX - 2019-10-11 - The Last Straw Vol 1 E1.mp4",
                    @"Angela White & Donnie Rock - PurgatoryX - 2019-11-01 - The Dentist Vol 1 E3.mp4",
                    @"Anny Aurora & Donnie Rock - PurgatoryX - 2019-12-27 - The Dentist Vol 2 E1.mp4",
                    @"Autumn Falls & Lena Paul - PurgatoryX - 2019-03-29 - The Therapist Vol 1 E1.mp4",
                    @"Autumn Falls & Lena Paul - PurgatoryX - 2019-05-10 - The Therapist Vol 1 E2.mp4",
                    @"Autumn Falls, Lena Paul & Donnie Rock - PurgatoryX - 2019-06-07 - The Therapist Vol 1 E3.mp4",
                    @"Bella Rolland, Donnie Rock & La Sirena 69 - PurgatoryX - 2020-10-02 - Genie Wishes Vol 2 E2.mp4",
                    @"Charles Dera, Donnie Rock & April Snow - PurgatoryX - 2018-12-21 - Fantasy Couple E3.mp4",
                    @"Charles Dera, Donnie Rock & Cassie Cloutier - PurgatoryX - 2019-01-18 - My Wife’s Massage E2.mp4",
                    @"Charles Dera, Donnie Rock & Jaye Summers - PurgatoryX - 2019-04-19 - My Husband Convinced Me Vol 1 E1.mp4",
                    @"Charles Dera, Donnie Rock & Sherly Queen - PurgatoryX - 2018-10-26 - My Wife’s Massage E1.mp4",
                    @"Charles Dera, Donnie Rock, Jaye Summers & Vienna Black - PurgatoryX - 2019-06-14 - My Husband Convinced Me Vol 1 E2.mp4",
                    @"Charles Dera, Donnie Rock, Jaye Summers & Vienna Black - PurgatoryX - 2019-07-26 - My Husband Convinced Me Vol 1 E3.mp4",
                    @"Cherie DeVille, Charles Dera & Donnie Rock - PurgatoryX - 2019-03-01 - My Wife’s Massage E3.mp4",
                    @"Demi Sutra & Donnie Rock - PurgatoryX - 2019-09-20 - The Dentist Vol 1 E2.mp4",
                    @"Donnie Rock & April Snow - PurgatoryX - 2018-11-23 - Fantasy Couple E1.mp4",
                    @"Donnie Rock, April Snow & Nadya Nabakova - PurgatoryX - 2018-12-07 - Fantasy Couple E2.mp4",
                    @"Emily Willis & Aidra Fox - PurgatoryX - 2019-11-08 - The Last Straw Vol 1 E2.mp4",
                    @"Emily Willis, Aidra Fox & Donnie Rock - PurgatoryX - 2019-12-06 - The Last Straw Vol 1 E3.mp4",
                    @"Jennifer White & Donnie Rock - PurgatoryX - 2020-08-07 - Genie Wishes Vol 2 E1.mp4",
                    @"Kendra Spade & Donnie Rock - PurgatoryX - 2019-08-23 - The Dentist Vol 1 E1.mp4",
                    @"Khloe Kapri & Donnie Rock - PurgatoryX - 2020-02-07 - The Dentist Vol 2 E2.mp4",
                    @"Krissy Lynn, Donnie Rock, Ramon Nomar & La Sirena 69 - PurgatoryX - 2020-11-27 - Genie Wishes Vol 2 E3.mp4",
                    @"Lacy Lennon, Gianna Dior & Donnie Rock - PurgatoryX - 2020-03-27 - Let Me Watch Vol 2 E1.mp4",
                    @"Lacy Lennon, Gianna Dior & Seth Gamble - PurgatoryX - 2020-05-15 - Let Me Watch Vol 2 E2.mp4",
                    @"Lacy Lennon, Gianna Dior, Seth Gamble & Donnie Rock - PurgatoryX - 2020-07-10 - Let Me Watch Vol 2 E3.mp4",
                    @"Laney Grey, Codey Steele & Alex Mack - PurgatoryX - 2020-10-30 - My Fiancée's Wishes Vol 1 E2.mp4",
                    @"Laney Grey, Codey Steele & Stirling Cooper - PurgatoryX - 2020-09-04 - My Fiancée’s Wishes Vol 1 E1.mp4",
                    @"Laney Grey, Codey Steele, Stirling Cooper & Alex Mack - PurgatoryX - 2020-12-25 - My Fiancée's Wishes Vol 1 E3.mp4",
                    @"Markus Kage, Rowan Rails & Samantha Creams - PurgatoryX - 2021-09-03 - My Wife's Massage Vol 2 E2.mp4",
                    @"Maya Bijou, Charles Dera & Bambi Black - PurgatoryX - 2019-05-24 - Let Me Watch Vol 1 E2.mp4",
                    @"Maya Bijou, Charles Dera, Donnie Rock & Bambi Black - PurgatoryX - 2019-06-21 - Let Me Watch Vol 1 E3.mp4",
                    @"Maya Bijou, Donnie Rock & Bambi Black - PurgatoryX - 2019-04-26 - Let Me Watch Vol 1 E1.mp4",
                    @"Vanna Bardot & Donnie Rock - PurgatoryX - 2020-03-06 - The Dentist Vol 2 E3.mp4"
                };

                var matchingScenes2 = await _repository._sqliteContext.Scenes
                    .Include(s => s.Performers)
                    .Include(s => s.Tags)
                    .Include(s => s.Site)
                    .Include(s => s.Downloads)
                    .OrderBy(s => s.ReleaseDate)
                    .Where(s => s.Downloads.Any(d => fileNames.Contains(d.SavedFilename)))
                    .Where(s => !s.Downloads.Any(d => d.DownloadQuality == preferredDownloadQuality2))
                .ToListAsync();

                await DownloadScenesAsync(
                    sceneDownloader2,
                    matchingScenes2,
                    site,
                    downloadConditions,
                    browserSettings);
                break;
            default:
                throw new Exception($"Could not find a ripper for job {Enum.GetName(jobType)} with site short name {shortName}");
        }
    }

    private async Task ScrapeScenesAsync(ISceneScraper sceneScraper, Site site, BrowserSettings browserSettings)
    {
        IPage page = await CreatePageAndLoginAsync(sceneScraper, site, browserSettings);
        var totalPages = await sceneScraper.NavigateToScenesAndReturnPageCountAsync(site, page);

        for (int currentPage = 1; currentPage <= totalPages; currentPage++)
        {
            await Task.Delay(5000);
            var currentScenes = await sceneScraper.GetCurrentScenesAsync(page);

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
                        if (existingScene == null)
                        {
                            var scenePage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });
                            await scenePage.WaitForLoadStateAsync();

                            var scene = await sceneScraper.ScrapeSceneAsync(site, url, sceneShortName, scenePage);
                            var savedScene = await _repository.SaveSceneAsync(scene);
                            await sceneScraper.DownloadPreviewImageAsync(savedScene, scenePage, page, currentScene);

                            await scenePage.CloseAsync();

                            Log.Information($"Scraped scene {savedScene.Id}: {url}");
                            await Task.Delay(3000);
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

    public async Task DownloadScenesAsync(ISceneDownloader sceneDownloader, IList<SceneEntity> matchingScenes, Site site, DownloadConditions conditions, BrowserSettings browserSettings)
    {
        var matchingScenesStr = string.Join($"{Environment.NewLine}    ", matchingScenes.Select(s => $"{s.Site.Name} - {s.ReleaseDate.ToString("yyyy-MM-dd")} - {s.Name}"));

        Log.Information($"Found {matchingScenes.Count()} scenes:{Environment.NewLine}    {matchingScenesStr}");

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
            if (rippedScenes >= conditions.MaxDownloads)
            {
                Log.Information($"Maximum scene rip limit of {conditions.MaxDownloads} reached. Stopping...");
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

                    var download = await sceneDownloader.DownloadSceneAsync(scene, page, rippingPath, conditions);

                    _repository._sqliteContext.Downloads.Add(new DownloadEntity()
                    {
                        DownloadedAt = DateTime.Now,
                        DownloadDetails = JsonSerializer.Serialize(download.DownloadDetails),
                        DownloadQuality = Enum.GetName(conditions.PreferredDownloadQuality),
                        OriginalFilename = download.OriginalFilename,
                        SavedFilename = download.SavedFilename,

                        SceneId = scene.Id,
                        Scene = scene,
                    });
                    await _repository._sqliteContext.SaveChangesAsync();

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
