using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using RipperPlaywright.Pages.WowNetwork;
using System.Text.RegularExpressions;
using static System.Formats.Asn1.AsnWriter;

namespace RipperPlaywright;

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

    public async Task ScrapeScenesAsync(string shortName)
    {
        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, true);

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
            Console.WriteLine($"Page {currentPage}/{totalPages} contains {currentScenes.Count} scenes");

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
                            Console.WriteLine($@"Could not determine ID from ""{relativeUrl}"" using pattern {pattern}. Skipping...");
                            continue;
                        }

                        if (retries > 0)
                        {
                            Console.WriteLine($"Retrying {retries + 1} attempt for {relativeUrl}");
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

                        var previewElement = await currentScene.QuerySelectorAsync("span > img");
                        var imageUrl = await previewElement.GetAttributeAsync("src");
                        string pattern2 = "icon_\\d+x\\d+.jpg";
                        string replacement = "icon_3840x2160.jpg";
                        string output = Regex.Replace(imageUrl, pattern2, replacement);
                        await new Downloader().DownloadSceneImage(existingScene, output, (int) existingScene.Id);

                        Console.WriteLine($"{DateTime.Now} Scraped scene {existingScene.Id}: {url}");

                        Thread.Sleep(3000);

                        break;
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine(ex.ToString());
                    }
                }
            }

            if (currentPage != totalPages)
            {
                await filmsPage.GoToNextFilmsPageAsync();
            }
        }
    }

    public async Task ScrapeGalleriesAsync(string shortName)
    {
        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, false);

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
            Console.WriteLine($"Page {currentPage}/{totalPages} contains {currentGalleries.Count} scenes");

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
                            Console.WriteLine($@"Could not determine ID from ""{relativeUrl}"" using pattern {pattern}. Skipping...");
                            continue;
                        }

                        var galleryShortName = match.Groups["id"].Value;
                        var existingGalleryEntity = await _sqliteContext.Galleries.FirstOrDefaultAsync(s => s.ShortName == galleryShortName);
                        if (existingGalleryEntity != null)
                        {
                            continue;
                        }

                        if (retries > 0)
                        {
                            Console.WriteLine($"Retrying {retries + 1} attempt for {relativeUrl}");
                        }

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
                        var galleryId = await _repository.SaveGalleryAsync(gallery);

                        var previewElement = await currentGallery.QuerySelectorAsync("span > img");
                        var imageUrl = await previewElement.GetAttributeAsync("src");
                        string pattern2 = "icon_\\d+x\\d+.jpg";
                        string replacement = "icon_3840x2160.jpg";
                        string output = Regex.Replace(imageUrl, pattern2, replacement);
                        await new Downloader().DownloadGalleryImage(gallery, output, galleryId);

                        await newPage.CloseAsync();

                        Console.WriteLine($"{DateTime.Now} Scraped gallery {galleryId}: {url}");

                        Thread.Sleep(3000);

                        break;
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine(ex.ToString());
                    }
                }
            }

            if (currentPage != totalPages)
            {
                await galleriesPage.GoToNextPageAsync();
            }
        }
    }

    public async Task DownloadAsync(string shortName, DownloadConditions conditions)
    {
        var matchingScenes = await _sqliteContext.Scenes
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Include(s => s.Site)
            .Where(s => conditions.DateRange.Start <= s.ReleaseDate && s.ReleaseDate <= conditions.DateRange.End)
        .ToListAsync();

        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, true);

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
