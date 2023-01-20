using CultureExtractor.Interfaces;
using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Serilog;
using System;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites.WowNetwork;

[PornNetwork("wow")]
[PornSite("allfinegirls")]
[PornSite("wowgirls")]
[PornSite("wowporn")]
[PornSite("ultrafilms")]
public class WowNetworkRipper : ISiteRipper, ISceneDownloader
{
    private readonly SqliteContext _sqliteContext;
    private readonly Repository _repository;

    public WowNetworkRipper()
    {
        _sqliteContext = new SqliteContext();
        _repository = new Repository(_sqliteContext);
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var loginPage = new WowLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);
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
            await Task.Delay(10000);
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

                            await filmsPage.DownloadPreviewImageAsync(currentScene, existingScene);
                            Log.Information($"Scraped scene {existingScene.Id}: {url}");

                            await newPage.CloseAsync();

                            await Task.Delay(3000);
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
            await Task.Delay(10000);
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

                        await Task.Delay(3000);

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

    public async Task<Download> DownloadSceneAsync(SceneEntity scene, IPage page, string rippingPath, DownloadConditions downloadConditions)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var performerNames = scene.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        var availableDownloads = await ParseAvailableDownloads(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        var waitForDownloadTask = page.WaitForDownloadAsync();
        await selectedDownload.ElementHandle.ClickAsync();
        var download = await waitForDownloadTask;
        var suggestedFilename = download.SuggestedFilename;

        var suffix = Path.GetExtension(suggestedFilename);
        var name = $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}{suffix}";
        name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));

        var path = Path.Join(rippingPath, name);

        Log.Verbose($"Downloading\r\n    URL:  {selectedDownload.DownloadDetails.Url}\r\n    Path: {path}");

        await download.SaveAsAsync(path);

        return new Download(suggestedFilename, name, selectedDownload.DownloadDetails);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloads(IPage page)
    {
        var downloadItems = await page.Locator("div.ct_dl_items > ul > li").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadLinkElement = await downloadItem.QuerySelectorAsync("a");
            var downloadUrl = await downloadLinkElement.GetAttributeAsync("href");
            var resolutionRaw = await downloadLinkElement.TextContentAsync();
            resolutionRaw = resolutionRaw.Replace("\n", "").Trim();
            var resolutionWidth = HumanParser.ParseResolutionWidth(resolutionRaw);
            var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionRaw);
            var codecElement = await downloadItem.QuerySelectorAsync("span.format");
            var codecRaw = await codecElement.InnerTextAsync();
            var fpsElement = await downloadItem.QuerySelectorAsync("span.fps");
            var fpsRaw = await fpsElement.InnerTextAsync();
            var sizeElement = await downloadItem.QuerySelectorAsync("span.size");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var descriptionElement = await downloadItem.QuerySelectorAsync("div.ct_dl_details");
            var description = await descriptionElement.TextContentAsync();

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadDetails(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        size,
                        double.Parse(fpsRaw.Replace("fps", "")),
                        downloadUrl,
                        codecRaw),
                    downloadLinkElement));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadDetails.ResolutionWidth).ThenByDescending(d => d.DownloadDetails.Fps).ToList();
    }
}
