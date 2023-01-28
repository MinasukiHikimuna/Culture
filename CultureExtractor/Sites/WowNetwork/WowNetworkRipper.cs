using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites.WowNetwork;

[PornNetwork("wow")]
[PornSite("allfinegirls")]
[PornSite("wowgirls")]
[PornSite("wowporn")]
[PornSite("ultrafilms")]
public class WowNetworkRipper : ISceneScraper, ISceneDownloader
{
    public async Task LoginAsync(Site site, IPage page)
    {
        var loginPage = new WowLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        var filmsPage = new WowFilmsPage(page);
        await filmsPage.OpenFilmsPageAsync(site.ShortName);

        return await filmsPage.GetFilmsPagesAsync();
    }

    public Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var filmsPage = new WowFilmsPage(page);
        return filmsPage.GetCurrentScenesAsync();
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var relativeUrl = await currentScene.GetAttributeAsync("href");
        var url = site.Url + relativeUrl;

        string pattern = @"/film/(?<id>\w+)/.*";
        Match match = Regex.Match(relativeUrl, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Could not parse ID from {url} using pattern {pattern}.");
        }

        return (url, match.Groups["id"].Value);
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page)
    {
        await page.WaitForLoadStateAsync();

        var wowScenePage = new WowScenePage(page);
        var releaseDate = await wowScenePage.ScrapeReleaseDateAsync();
        var duration = await wowScenePage.ScrapeDurationAsync();
        var description = await wowScenePage.ScrapeDescriptionAsync();
        var title = await wowScenePage.ScrapeTitleAsync();
        var performers = await wowScenePage.ScrapePerformersAsync();
        var tags = await wowScenePage.ScrapeTagsAsync();
        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
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
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var filmsPage = new WowFilmsPage(scenePage);
        await filmsPage.DownloadPreviewImageAsync(currentScene, scene);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        var filmsPage = new WowFilmsPage(page);
        await filmsPage.GoToNextFilmsPageAsync();
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, string rippingPath, DownloadConditions downloadConditions)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var performerNames = scene.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

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

        var path = Path.Join(@"F:\", name);

        Log.Verbose($"Downloading\r\n    URL:  {selectedDownload.DownloadOption.Url}\r\n    Path: {path}");

        await download.SaveAsAsync(path);

        return new Download(scene, suggestedFilename, name, selectedDownload.DownloadOption);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
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
            var codec = HumanParser.ParseCodec(codecRaw);
            var fpsElement = await downloadItem.QuerySelectorAsync("span.fps");
            var fpsRaw = await fpsElement.InnerTextAsync();
            var sizeElement = await downloadItem.QuerySelectorAsync("span.size");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var descriptionRaw = await downloadItem.TextContentAsync();
            var description = descriptionRaw.Replace("\n", "").Trim();

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        size,
                        double.Parse(fpsRaw.Replace("fps", "")),
                        codec,
                        downloadUrl),
                    downloadLinkElement));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.ResolutionWidth).ThenByDescending(d => d.DownloadOption.Fps).ToList();
    }
}
