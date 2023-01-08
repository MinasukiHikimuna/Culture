using CultureExtractor.Sites.WowNetwork;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites.CzechVRNetwork;

[PornNetwork("czechvr")]
[PornSite("czechvr")]
[PornSite("czechvrcasting")]
[PornSite("czechvrfetish")]
[PornSite("czechvrintimacy")]
public class CzechVRNetworkRipper : ISiteRipper
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

    public async Task DownloadAsync(string shortName, DownloadConditions conditions, BrowserSettings browserSettings)
    {
        throw new NotImplementedException();
    }
}
