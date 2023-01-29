using CultureExtractor.Exceptions;
using CultureExtractor.Interfaces;
using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;
using static System.Net.Mime.MediaTypeNames;

namespace CultureExtractor.Sites.CzechVRNetwork;

[PornNetwork("czechvr")]
[PornSite("czechvr")]
[PornSite("czechvrcasting")]
[PornSite("czechvrfetish")]
[PornSite("czechvrintimacy")]
public class CzechVRNetworkRipper : ISceneScraper, ISceneDownloader
{
    public async Task LoginAsync(Site site, IPage page)
    {
        var memberLoginHeader = page.GetByRole(AriaRole.Heading, new() { NameString = "Member login" });

        // TODO: sometimes this requires captcha, how to handle reliably?
        if (await memberLoginHeader.IsVisibleAsync())
        {
            // Login requires CAPTCHA so we need to create a headful browser
            /*IPage loginPage = await PlaywrightFactory.CreatePageAsync(site, new BrowserSettings(false));
            await loginPage.WaitForLoadStateAsync();*/

            var loginPage = page;

            await loginPage.GetByPlaceholder("Username").TypeAsync(site.Username);
            await loginPage.GetByPlaceholder("Password").TypeAsync(site.Password);
            await loginPage.GetByRole(AriaRole.Button, new() { NameString = "CLICK HERE TO LOGIN" }).ClickAsync();
            await loginPage.GetByRole(AriaRole.Button, new() { NameString = "CLICK HERE TO LOGIN" }).WaitForAsync(new LocatorWaitForOptions()
            {
                State = WaitForSelectorState.Detached
            });
            await loginPage.WaitForLoadStateAsync();

            await Task.Delay(1000);

            Log.Information($"Logged in as {site.Username}.");
        }
        else
        {
            Log.Verbose("Login was not necessary.");
        }
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
        var linkElement = await currentScene.QuerySelectorAsync("div.nazev > h2 > a");
        var relativeUrl = await linkElement.GetAttributeAsync("href");
        if (relativeUrl.StartsWith("./"))
        {
            relativeUrl = relativeUrl.Substring(2);
        }

        var titleElement = await currentScene.QuerySelectorAsync("div.nazev > h2");
        var title = await titleElement.TextContentAsync();

        string pattern = @" (?<id>\d+) - ";
        Match match = Regex.Match(title, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($@"Could not determine ID from ""{title}"" using pattern {pattern}. Skipping...");
        }

        var sceneShortName = match.Groups["id"].Value;

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

            var resolutionWidth = HumanParser.ParseResolutionWidth(descriptionRaw);
            var resolutionHeight = HumanParser.ParseResolutionHeight(descriptionRaw);

            var url = await downloadOption.Link.GetAttributeAsync("href");
            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
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
