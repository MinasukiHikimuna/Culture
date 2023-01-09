using CultureExtractor.Interfaces;
using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites.CzechVRNetwork;

[PornNetwork("czechvr")]
[PornSite("czechvr")]
[PornSite("czechvrcasting")]
[PornSite("czechvrfetish")]
[PornSite("czechvrintimacy")]
public class CzechVRNetworkRipper : ISiteRipper, ISceneDownloader
{
    private readonly SqliteContext _sqliteContext;
    private readonly Repository _repository;

    public CzechVRNetworkRipper()
    {
        _sqliteContext = new SqliteContext();
        _repository = new Repository(_sqliteContext);
    }

    public async Task ScrapeScenesAsync(string shortName, BrowserSettings browserSettings)
    {
        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, browserSettings);

        var loginPage = new CzechVRLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

        var videosPage = new CzechVRVideosPage(page);
        await videosPage.OpenVideosPageAsync(shortName);

        var totalPages = await videosPage.GetVideosPagesAsync();

        for (int currentPage = 1; currentPage <= totalPages; currentPage++)
        {
            Thread.Sleep(5000);
            var currentScenes = await videosPage.GetCurrentScenesAsync();
            Log.Information($"Page {currentPage}/{totalPages} contains {currentScenes.Count} scenes");

            foreach (var currentScene in currentScenes)
            {
                for (int retries = 0; retries < 3; retries++)
                {
                    try
                    {
                        var relativeUrl = await currentScene.GetAttributeAsync("href");
                        if (relativeUrl.StartsWith("./"))
                        {
                            relativeUrl = relativeUrl.Substring(2);
                        }
                        var url = site.Url + relativeUrl;

                        var imagehandle = await currentScene.QuerySelectorAsync("img");
                        var imageUrl = await imagehandle.GetAttributeAsync("src");

                        string pattern = @"(\d+)-\w+-big.jpg";
                        Match match = Regex.Match(imageUrl, pattern);
                        if (!match.Success)
                        {
                            Log.Information($@"Could not determine ID from ""{relativeUrl}"" using pattern {pattern}. Skipping...");
                            continue;
                        }

                        if (retries > 0)
                        {
                            Log.Information($"Retrying {retries + 1} attempt for {relativeUrl}");
                        }

                        var sceneShortName = match.Groups[1].Value;
                        var existingScene = await _repository.GetSceneAsync(shortName, sceneShortName);
                        if (existingScene == null)
                        {
                            var newPage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });

                            await newPage.WaitForLoadStateAsync();

                            var scenePage = new CzechVRScenePage(newPage);
                            var releaseDate = await scenePage.ScrapeReleaseDateAsync();
                            var duration = await scenePage.ScrapeDurationAsync();
                            var description = await scenePage.ScrapeDescriptionAsync();
                            var title = await scenePage.ScrapeTitleAsync();
                            var performers = await scenePage.ScrapePerformersAsync();
                            var tags = await scenePage.ScrapeTagsAsync();

                            var scene = new Scene(
                                null,
                                site,
                                releaseDate,
                                sceneShortName,
                                title,
                                url,
                                description,
                                duration.TotalSeconds,
                                performers,
                                tags
                            );
                            existingScene = await _repository.SaveSceneAsync(scene);

                            await newPage.CloseAsync();

                            await videosPage.DownloadPreviewImageAsync(currentScene, existingScene);

                            Log.Information($"Scraped scene {existingScene.Id}: {url}");

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
                await videosPage.GoToNextFilmsPageAsync();
            }
        }
    }

    public async Task ScrapeGalleriesAsync(string shortName, BrowserSettings browserSettings)
    {
        throw new NotImplementedException();
    }

    public async Task DownloadScenesAsync(string shortName, DownloadConditions conditions, BrowserSettings browserSettings)
    {
        var site = await _repository.GetSiteAsync(shortName);

        var matchingScenes = await _sqliteContext.Scenes
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

        var loginPage = new CzechVRLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);

        var rippingPath = $@"I:\Ripping\{site.Name}\";
        foreach (var scene in matchingScenes)
        {
            for (int retries = 0; retries < 3; retries++)
            {
                try
                {
                    await page.GotoAsync(scene.Url);
                    await page.WaitForLoadStateAsync();

                    if (retries > 0)
                    {
                        Log.Information($"Retrying {retries + 1} attempt for {scene.Url}");
                    }

                    var performerNames = scene.Performers.Select(p => p.Name).ToList();
                    var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

                    await page.Locator("li[id^=\"smartphone\"]:not(.download)").ClickAsync();

                    var downloadUrl = await page.Locator("a[data-filename$=\"SMARTPHONE LQ\"]").GetAttributeAsync("href");

                    var waitForDownloadTask = page.WaitForDownloadAsync();

                    await page.Locator("a[data-filename$=\"SMARTPHONE LQ\"]").ClickAsync();

                    var download = await waitForDownloadTask;
                    var suggestedFilename = download.SuggestedFilename;

                    var suffix = Path.GetExtension(suggestedFilename);
                    var name = $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}{suffix}";
                    name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));

                    var path = Path.Join(rippingPath, name);

                    Log.Verbose($"Downloading\r\n    URL:  {downloadUrl}\r\n    Path: {path}");

                    await download.SaveAsAsync(path);
                    break;
                }
                catch (PlaywrightException ex)
                {
                    Log.Error(ex.Message, ex);
                    // Let's try again
                }
            }
        }
    }
}
