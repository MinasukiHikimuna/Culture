using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

[PornNetwork("sensuallove")]
[PornSite("sensuallove")]
public class SensualLoveRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public SensualLoveRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = "Members" }).First.ClickAsync();

        var emailInputLocator = page.GetByPlaceholder("E-Mail");

        if (await emailInputLocator.IsVisibleAsync())
        {
            await page.GetByPlaceholder("E-Mail").ClickAsync();
            await page.GetByPlaceholder("E-Mail").FillAsync(site.Username);
            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            await page.GetByText("Get Inside").ClickAsync();
        }

        await page.Locator("div.welcome").WaitForAsync(new LocatorWaitForOptions() { State = WaitForSelectorState.Visible });
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator(".slider-watchall").First.ClickAsync();

        // There doesn't seem to be any kind of pagination or loading for more scenes at the moment.
        return 1;
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var scenesLocator = page.Locator("div.content-view-lg > div.content-view-grid > div.content-grid-item-wrapper");
        await scenesLocator.First.WaitForAsync(new() { State = WaitForSelectorState.Visible });
        var sceneHandles = await scenesLocator.ElementHandlesAsync();

        var indexScenes = new List<IndexScene>();
        foreach (var sceneHandle in sceneHandles.Reverse())
        {
            var sceneIdAndUrl = await GetSceneIdAsync(site, sceneHandle);
            indexScenes.Add(new IndexScene(null, sceneIdAndUrl.Id, sceneIdAndUrl.Url, sceneHandle));
        }

        return indexScenes.AsReadOnly();
    }

    public async Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var linkElement = await currentScene.QuerySelectorAsync("a");
        var url = await linkElement.GetAttributeAsync("href");
        var id = url.Replace("/members/content/item/", "");
        return new SceneIdAndUrl(id, url);
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var releaseDateRaw = await page.Locator("div.release-date > div.date").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw!);

        var durationRaw = await page.Locator("div.video-duration > div.count").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var title = await page.Locator("div.metadata div.title").GetAttributeAsync("title");
        var description = string.Empty;

        var performerElements = await page.Locator("div.metadata div.models > span").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var performerElement in performerElements)
        {
            var castUrl = await performerElement.GetAttributeAsync("data-href");
            var castId = await performerElement.GetAttributeAsync("data-value");
            var castName = await performerElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl));
        }

        var tagElements = await page.Locator("div.metadata div.tags > span").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("data-href");
            var tagId = await tagElement.GetAttributeAsync("data-value");
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
            null,
            site,
            null,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            "{}",
            DateTime.Now);
    }

    public async Task DownloadAdditionalFilesAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene, IReadOnlyList<IRequest> requests)
    {
        var previewElement = await scenePage.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "").Replace(" background-size: cover;", "");
        await _downloader.DownloadSceneImageAsync(scene, backgroundImageUrl, scene.Site.Url);
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
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

        return await _downloader.DownloadSceneAsync(scene, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
            await selectedDownload.ElementHandle.ClickAsync()
);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.download-center > div.download-buttons > div.download-button-wrapper").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadButtonElement = await downloadItem.QuerySelectorAsync("div.clickable");
            var downloadUrl = await downloadButtonElement.GetAttributeAsync("data-href");
            var resolutionWidth = HumanParser.ParseResolutionWidth(downloadUrl);
            var resolutionHeight = HumanParser.ParseResolutionHeight(downloadUrl);
            var codecElement = await downloadItem.QuerySelectorAsync("div.format-name");
            var codecRaw = await codecElement.InnerTextAsync();
            var codec = HumanParser.ParseCodec(codecRaw);
            if (codec == string.Empty)
            {
                codec = HumanParser.ParseCodec("H.264");
            }
            var sizeElement = await downloadItem.QuerySelectorAsync("div.info");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var descriptionRaw = await downloadItem.TextContentAsync();
            var description = Regex.Replace(descriptionRaw, @"\s+", " ");

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        size,
                        -1,
                        codec,
                        downloadUrl),
                    downloadButtonElement));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.ResolutionWidth).ThenByDescending(d => d.DownloadOption.Fps).ToList();
    }

    public Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        throw new NotImplementedException();
    }
}
