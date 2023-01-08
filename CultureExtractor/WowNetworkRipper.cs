using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using CultureExtractor.Sites.WowNetwork;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor;

[PornNetwork("wow")]
[PornSite("allfinegirls")]
[PornSite("wowgirls")]
[PornSite("wowporn")]
[PornSite("ultrafilms")]
public class WowNetworkRipper : ISiteRipper
{
    private readonly SqliteContext _sqliteContext;
    private readonly Repository _repository;

    public WowNetworkRipper()
    {
        _sqliteContext = new SqliteContext();
        _repository = new Repository(_sqliteContext);
    }

    public async Task ScrapeScenesAsync(string shortName, BrowserSettings browserSettings)
    {
        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, browserSettings);

        var loginPage = new WowLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

        var filmsPage = new WowFilmsPage(page);
        await filmsPage.OpenFilmsPageAsync(shortName);

        var totalPages = await filmsPage.GetFilmsPagesAsync(); 

        for (int currentPage = 1; currentPage <= totalPages; currentPage++)
        {
            Thread.Sleep(10000);
            var currentScenes = await filmsPage.GetCurrentScenesAsync();
            Log.Information($"Page {currentPage}/{totalPages} contains {currentScenes.Count} scenes");

            foreach (var currentScene in currentScenes)
            {
                for (int retries = 0; retries < 3; retries++)
                {
                    try
                    {
                        var relativeUrl = await currentScene.GetAttributeAsync("href");
                        var url = site.Url + relativeUrl;

                        string pattern = @"/film/(?<id>\w+)/.*";
                        Match match = Regex.Match(relativeUrl, pattern);
                        if (!match.Success)
                        {
                            Log.Information($@"Could not determine ID from ""{relativeUrl}"" using pattern {pattern}. Skipping...");
                            continue;
                        }

                        if (retries > 0)
                        {
                            Log.Information($"Retrying {retries + 1} attempt for {relativeUrl}");
                        }

                        var sceneShortName = match.Groups["id"].Value;
                        var existingScene = await _repository.GetSceneAsync(shortName, sceneShortName);
                        if (existingScene == null)
                        {
                            var newPage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });

                            await newPage.WaitForLoadStateAsync();

                            var wowScenePage = new WowScenePage(newPage);
                            var releaseDate = await wowScenePage.ScrapeReleaseDateAsync();
                            var duration = await wowScenePage.ScrapeDurationAsync();
                            var description = await wowScenePage.ScrapeDescriptionAsync();
                            var title = await wowScenePage.ScrapeTitleAsync();
                            var performers = await wowScenePage.ScrapePerformersAsync();
                            var tags = await wowScenePage.ScrapeTagsAsync();

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
                        }

                        if (existingScene.Id == null)
                        {
                            throw new Exception($"Scene ID was null for {existingScene.ShortName}");
                        }

                        await filmsPage.DownloadPreviewImageAsync(currentScene, existingScene);

                        Log.Information($"Scraped scene {existingScene.Id}: {url}");

                        Thread.Sleep(3000);

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
                await filmsPage.GoToNextFilmsPageAsync();
            }
        }
    }

    public async Task ScrapeGalleriesAsync(string shortName, BrowserSettings browserSettings)
    {
        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, browserSettings);

        var loginPage = new WowLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

        var galleriesPage = new WowGalleriesPage(page);
        await galleriesPage.OpenGalleriesPageAsync(shortName);

        var totalPages = await galleriesPage.GetGalleriesPagesAsync();

        for (int currentPage = 1; currentPage <= totalPages; currentPage++)
        {
            Thread.Sleep(10000);
            var currentGalleries = await galleriesPage.GetCurrentGalleriesAsync();
            Log.Information($"Page {currentPage}/{totalPages} contains {currentGalleries.Count} scenes");

            foreach (var currentGallery in currentGalleries)
            {
                for (int retries = 0; retries < 3; retries++)
                {
                    try
                    {
                        var relativeUrl = await currentGallery.GetAttributeAsync("href");
                        var url = site.Url + relativeUrl;

                        string pattern = @"/gallery/(?<id>\w+)/.*";
                        Match match = Regex.Match(relativeUrl, pattern);
                        if (!match.Success)
                        {
                            Log.Information($@"Could not determine ID from ""{relativeUrl}"" using pattern {pattern}. Skipping...");
                            continue;
                        }

                        if (retries > 0)
                        {
                            Log.Information($"Retrying {retries + 1} attempt for {relativeUrl}");
                        }

                        var galleryShortName = match.Groups["id"].Value;
                        var existingGallery = await _repository.GetGalleryAsync(shortName, galleryShortName);
                        if (existingGallery == null)
                        {
                            var newPage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentGallery.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });

                            await newPage.WaitForLoadStateAsync();

                            var galleryPage = new WowGalleryPage(newPage);
                            var releaseDate = await galleryPage.ScrapeReleaseDateAsync();
                            var title = await galleryPage.ScrapeTitleAsync();
                            var performers = await galleryPage.ScrapePerformersAsync();
                            var tags = await galleryPage.ScrapeTagsAsync();
                            var pictures = await galleryPage.ScrapePicturesAsync();

                            var gallery = new Gallery(
                                null,
                                site,
                                releaseDate,
                                galleryShortName,
                                title,
                                url,
                                string.Empty,
                                pictures,
                                performers,
                                tags
                            );
                            existingGallery = await _repository.SaveGalleryAsync(gallery);

                            await newPage.CloseAsync();
                        }

                        if (existingGallery.Id == null)
                        {
                            throw new Exception($"Gallery ID was null for {existingGallery.ShortName}");
                        }

                        await galleriesPage.DownloadPreviewImageAsync(currentGallery, existingGallery);

                        Log.Information($"Scraped gallery {existingGallery.Id}: {url}");

                        Thread.Sleep(3000);

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
                await galleriesPage.GoToNextPageAsync();
            }
        }
    }

    public async Task DownloadAsync(string shortName, DownloadConditions conditions, BrowserSettings browserSettings)
    {
        var matchingScenes = await _sqliteContext.Scenes
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Include(s => s.Site)
            .Where(s => conditions.DateRange.Start <= s.ReleaseDate && s.ReleaseDate <= conditions.DateRange.End)
        .ToListAsync();

        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, browserSettings);

        var loginPage = new WowLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);

        var rippingPath = $@"I:\Ripping\{site.Name}\";
        foreach (var scene in matchingScenes)
        {
            await page.GotoAsync(scene.Url);
            await page.WaitForLoadStateAsync();

            var performerNames = scene.Performers.Select(p => p.Name).ToList();
            var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

            // All scenes do not have 60 fps alternatives. In that case 30 fps button is not shown.
            /* var fps30Locator = newPage.Locator("span").Filter(new() { HasTextString = "30 fps" });
            if (await fps30Locator.IsVisibleAsync())
            {
                await newPage.Locator("span").Filter(new() { HasTextString = "30 fps" }).ClickAsync();
                await newPage.WaitForLoadStateAsync();
            }*/

            var downloadUrl = await page.GetByRole(AriaRole.Link, new() { NameString = "5568 x 3132" }).GetAttributeAsync("href");

            var waitForDownloadTask = page.WaitForDownloadAsync();
            await page.GetByRole(AriaRole.Link, new() { NameString = "5568 x 3132" }).ClickAsync();
            var download = await waitForDownloadTask;
            var suggestedFilename = download.SuggestedFilename;

            var suffix = Path.GetExtension(suggestedFilename);
            var name = $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}{suffix}";
            name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));

            var path = Path.Join(rippingPath, name);
            await download.SaveAsAsync(path);
        }
    }
}
