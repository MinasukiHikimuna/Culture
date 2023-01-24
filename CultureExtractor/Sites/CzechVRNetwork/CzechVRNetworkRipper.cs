using CultureExtractor.Exceptions;
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
public class CzechVRNetworkRipper : ISceneScraper, ISceneDownloader
{
    private readonly SqliteContext _sqliteContext;
    private readonly Repository _repository;

    public CzechVRNetworkRipper()
    {
        _sqliteContext = new SqliteContext();
        _repository = new Repository(_sqliteContext);
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var loginPage = new CzechVRLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        var videosPage = new CzechVRVideosPage(page);
        await videosPage.OpenVideosPageAsync(site.ShortName);

        var totalPages = await videosPage.GetVideosPagesAsync();

        return totalPages;
    }

    public Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var videosPage = new CzechVRVideosPage(page);
        return videosPage.GetCurrentScenesAsync();
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var relativeUrl = await currentScene.GetAttributeAsync("href");
        if (relativeUrl.StartsWith("./"))
        {
            relativeUrl = relativeUrl.Substring(2);
        }

        var imagehandle = await currentScene.QuerySelectorAsync("img");
        var imageUrl = await imagehandle.GetAttributeAsync("src");

        string pattern = @"(\d+)-\w+-big.jpg";
        Match match = Regex.Match(imageUrl, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($@"Could not determine ID from ""{relativeUrl}"" using pattern {pattern}. Skipping...");
        }

        var sceneShortName = match.Groups[1].Value;

        return (relativeUrl, sceneShortName);
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page)
    {
        var scenePage = new CzechVRScenePage(page);
        var releaseDate = await scenePage.ScrapeReleaseDateAsync();
        var duration = await scenePage.ScrapeDurationAsync();
        var description = await scenePage.ScrapeDescriptionAsync();
        var title = await scenePage.ScrapeTitleAsync();
        var performers = await scenePage.ScrapePerformersAsync();
        var tags = await scenePage.ScrapeTagsAsync();
        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

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
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList()
        );
        return scene;
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var videosPage = new CzechVRVideosPage(scenesPage);
        await videosPage.DownloadPreviewImageAsync(currentScene, scene);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        var videosPage = new CzechVRVideosPage(page);
        await videosPage.GoToNextFilmsPageAsync();
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, string rippingPath, DownloadConditions downloadConditions)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        return await new Downloader().DownloadSceneAsync(page, selectedDownload.DownloadOption, scene, rippingPath, async () =>
        {
            await page.EvaluateAsync(
                $"document.querySelector('a[href=\"{selectedDownload.DownloadOption.Url}\"')" +
                $".parentElement" +
                $".parentElement" +
                $".parentElement" +
                $".previousElementSibling" +
                $".click()");
            await page.Locator($"a[href=\"{selectedDownload.DownloadOption.Url}\"]").ClickAsync();
        });
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadOptions = new List<DownloadOptionElements>();
        var deviceElements = await page.Locator("ul.zalozky > li:not(.download)").ElementHandlesAsync();
        var downloadElements = await page.Locator("ul.zalozky > li.download").ElementHandlesAsync();

        for (var i = 0; i < deviceElements.Count; i++)
        {
            var deviceElement = deviceElements[i];
            var downloadElement = downloadElements[i];

            var downloadDescriptionElements = await downloadElement.QuerySelectorAllAsync("div.nazevpopis");
            var downloadLinkElements = await downloadElement.QuerySelectorAllAsync("div.dlnew > div.dlp > a");

            for (var j = 0; j < downloadDescriptionElements.Count; j++)
            {
                downloadOptions.Add(new DownloadOptionElements(downloadElement, downloadDescriptionElements[j], downloadLinkElements[j]));
            }
        }

        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadOption in downloadOptions)
        {
            var descriptionRaw = await downloadOption.Details.TextContentAsync();
            var description = descriptionRaw.Replace("\t", "").Replace("\n", "").Trim();
            var url = await downloadOption.Link.GetAttributeAsync("href");
            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        HumanParser.ParseResolutionWidth(description),
                        HumanParser.ParseResolutionHeight(description),
                        HumanParser.ParseFileSize(description),
                        HumanParser.ParseFps(description),
                        HumanParser.ParseCodec(description),
                        url),
                    null));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.FileSize).ToList();
    }

    private record DownloadOptionElements(IElementHandle Device, IElementHandle Details, IElementHandle Link);
}
