using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor.Sites;

[PornNetwork("purgatoryx")]
[PornSite("purgatoryx")]
public class PurgatoryXRipper : ISceneScraper, ISceneDownloader
{
    private readonly IDownloader _downloader;

    public PurgatoryXRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var enterButton = page.GetByRole(AriaRole.Link, new() { NameString = "Enter" });
        if (await enterButton.IsVisibleAsync())
        {
            await enterButton.ClickAsync();
        }

        var membersButton = page.Locator("#main-nav").GetByRole(AriaRole.Link, new() { NameString = "Members" });
        if (await membersButton.IsVisibleAsync())
        {
            await membersButton.ClickAsync();
        }

        if (await page.GetByPlaceholder("Username").IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username").ClickAsync();
            await page.GetByPlaceholder("Username").FillAsync(site.Username);
            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            await page.GetByRole(AriaRole.Button, new() { NameString = "Sign In" }).ClickAsync();
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator("#main-nav").GetByRole(AriaRole.Link, new() { NameString = "Episodes " }).ClickAsync();
        var lastPageText = await page.Locator("ul.pagination > li").Nth(-2).TextContentAsync();
        return int.Parse(lastPageText);
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var previewElement = await scenePage.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "").Replace(" background-size: cover;", "");
        await _downloader.DownloadSceneImageAsync(scene, backgroundImageUrl, "https://members.purgatoryx.com");
    }

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var currentScenes = await page.Locator("div.content-item").ElementHandlesAsync();
        return currentScenes;
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var linkElement = await currentScene.QuerySelectorAsync("div.container > div.row > a");
        var url = await linkElement.GetAttributeAsync("href");
        var idWithQueryStrings = url.Substring(url.LastIndexOf("/") + 1);
        var shortName = idWithQueryStrings.Contains("?")
            ? idWithQueryStrings.Substring(0, idWithQueryStrings.IndexOf("?"))
            : idWithQueryStrings;

        return (url, shortName);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = "Next »" }).ClickAsync();
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
    {
        Thread.Sleep(5000);

        var releaseDateRaw = await page.Locator("p.content-meta > span.date").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw);

        var durationRaw = await page.Locator("p.content-meta > span.total-time").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("h1.title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performersRaw = await page.Locator("div.model-wrap > ul > li").ElementHandlesAsync();

        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersRaw)
        {
            var performerLink = await performerElement.QuerySelectorAsync("a");
            var performerUrl = await performerLink.GetAttributeAsync("href");
            var shortName = performerUrl.Substring(performerUrl.LastIndexOf("/") + 1);
            var performerNameElement = await performerElement.QuerySelectorAsync("h5");
            var nameRaw = await performerNameElement.TextContentAsync();
            var name = nameRaw.Replace("\n", "").Trim();
            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        var description = await page.Locator("div.description > p").TextContentAsync();
        description = description.Replace("\n", "").Trim();

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
            new List<SiteTag>(),
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList()
        );
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        var performerNames = scene.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        await page.GetByRole(AriaRole.Button).Filter(new() { HasTextString = "Download video" }).ClickAsync();

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.FirstOrDefault(f => f.DownloadOption.ResolutionHeight == 360) ?? availableDownloads.Last(),
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
        var downloadListItems = await page.Locator("div.download-video > ul.dropdown-menu > li").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();

        var firstElementText = await downloadListItems.First().TextContentAsync();
        var expectedTitle = "Choose Download Quality";
        if (!firstElementText.Contains(expectedTitle))
        {
            throw new InvalidOperationException($"First element in download list is expected to contain title {expectedTitle}.");
        }

        foreach (var downloadListItem in downloadListItems.Skip(1))
        {
            var titleElement = await downloadListItem.QuerySelectorAsync("span.download-title");
            var titleRaw = await titleElement.TextContentAsync();
            var title = titleRaw.Replace("\n", "").Trim();

            var sizeElement = await downloadListItem.QuerySelectorAsync("span.download-size");
            var sizeRaw = await sizeElement.TextContentAsync();
            var size = HumanParser.ParseFileSize(sizeRaw.Replace("\n", "").Trim());

            var resolutionElement = await downloadListItem.QuerySelectorAsync("span.download-dimension");
            var resolutionRaw = await resolutionElement.TextContentAsync();
            var resolutionWidth = HumanParser.ParseResolutionWidth(resolutionRaw.Replace("\n", "").Trim());
            var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionRaw.Replace("\n", "").Trim());

            var codecElement = await downloadListItem.QuerySelectorAsync("span.download-codec");
            var codecRaw = await codecElement.TextContentAsync();
            var codec = HumanParser.ParseCodec(codecRaw.Replace("\n", "").Trim());

            var linkElement = await downloadListItem.QuerySelectorAsync("a");
            var url = await linkElement.GetAttributeAsync("href");

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        title,
                        resolutionWidth,
                        resolutionHeight,
                        size,
                        -1,
                        codec,
                        url),
                    downloadListItem));
        }
        return availableDownloads;
    }
}
