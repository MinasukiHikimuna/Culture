using Microsoft.Playwright;
using CultureExtractor.Interfaces;
using CultureExtractor.Exceptions;

namespace CultureExtractor.Sites;

[PornNetwork("metart")]
[PornSite("metart")]
[PornSite("metartx")]
[PornSite("sexart")]
[PornSite("vivthomas")]
[PornSite("thelifeerotic")]
[PornSite("eternaldesire")]
[PornSite("straplez")]
[PornSite("hustler")]
public class MetArtNetworkRipper : ISceneScraper, ISceneDownloader
{
    private readonly IDownloader _downloader;

    public MetArtNetworkRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        if (await page.IsVisibleAsync(".sign-in"))
        {
            if (await page.Locator("#onetrust-accept-btn-handler").IsVisibleAsync())
            {
                await page.Locator("#onetrust-accept-btn-handler").ClickAsync();
            }

            await page.ClickAsync(".sign-in");
            await page.WaitForLoadStateAsync();

            await page.Locator("[name='email']").TypeAsync(site.Username);
            await page.Locator("[name='password']").TypeAsync(site.Password);
            await page.Locator("button[type='submit']").ClickAsync();
            await page.WaitForLoadStateAsync();
        }

        // Close the modal dialog if one is shown.
        try
        {
            await page.WaitForLoadStateAsync();
            if (await page.Locator(".close-btn").IsVisibleAsync())
            {
                await page.Locator(".close-btn").ClickAsync();
            }
            if (await page.Locator(".fa-times-circle").IsVisibleAsync())
            {
                await page.Locator(".fa-times-circle").ClickAsync();
            }
        }
        catch (Exception ex)
        {
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        // Close the modal dialog if one is shown.
        try
        {
            await page.WaitForLoadStateAsync();
            if (await page.Locator(".close-btn").IsVisibleAsync())
            {
                await page.Locator(".close-btn").ClickAsync();
            }
            if (await page.Locator(".fa-times-circle").IsVisibleAsync())
            {
                await page.Locator(".fa-times-circle").ClickAsync();
            }
        }
        catch (Exception ex)
        {
        }

        await page.Locator("nav a[href='/movies']").ClickAsync();
        await page.WaitForLoadStateAsync();

        // Close the modal dialog if one is shown.
        try
        {
            await page.WaitForLoadStateAsync();
            if (await page.Locator(".close-btn").IsVisibleAsync())
            {
                await page.Locator(".close-btn").ClickAsync();
            }
            if (await page.Locator(".fa-times-circle").IsVisibleAsync())
            {
                await page.Locator(".fa-times-circle").ClickAsync();
            }
        }
        catch (Exception ex)
        {
        }

        var totalPagesStr = await page.Locator("nav.pagination > a:nth-child(5)").TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);

        return totalPages;
    }

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var currentPage = await page.Locator("nav.pagination > a.active").TextContentAsync();
        var skipAdScene = currentPage == "1" && site.ShortName != "hustler";

        var currentScenes = await page.Locator("div.card-media a").ElementHandlesAsync();

        return skipAdScene
            ? currentScenes.Skip(1).ToList().AsReadOnly()
            : currentScenes;
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var url = await currentScene.GetAttributeAsync("href");
        var sceneShortName = url.Substring(url.LastIndexOf("/movie/") + "/movie/".Length + 1);
        return (url, sceneShortName);
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
    {
        var releaseDate = await ScrapeReleaseDateAsync(page);
        var duration = await ScrapeDurationAsync(page);
        var description = await ScrapeDescriptionAsync(page);
        var name = await ScrapeTitleAsync(page);
        var performers = await ScrapePerformersAsync(page, site.Url);

        var tagElements = await page.Locator("div.tags-wrapper > div > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagShortName = tagUrl.Replace("/tags/", "");
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagShortName, tagName, tagUrl));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        var scene = new Scene(
            null,
            site,
            releaseDate,
            sceneShortName,
            name,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList()
        );

        return scene;
    }

    private async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var releaseDateRaw = await page.Locator("div.movie-details > div > div > div > ul > li:nth-child(3) > span:nth-child(2)").TextContentAsync();
        return DateOnly.Parse(releaseDateRaw);
    }

    private async Task<string> ScrapeTitleAsync(IPage page)
    {
        var title = await page.Locator("div.movie-details h3.headline").TextContentAsync();
        title = title.Substring(0, title.LastIndexOf("(") - 1);
        return title;
    }

    private async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page, string baseUrl)
    {
        var castElements = await page.Locator("div.movie-details > div > div > div > ul > li:nth-child(1) > span:nth-child(2) > a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");
            var castId = castUrl.Substring(castUrl.LastIndexOf("/") + 1);
            var castName = await castElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl));
        }
        return performers.AsReadOnly();
    }

    private async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var duration = await page.Locator("div.movie-details > div > div > div > ul > li:nth-child(4) > span:nth-child(2)").TextContentAsync();
        if (TimeSpan.TryParse(duration, out TimeSpan timespan))
        {
            return timespan;
        }

        return TimeSpan.FromSeconds(0);
    }

    private async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        if (!await page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).IsVisibleAsync())
        {
            return string.Empty;
        }

        await page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).ClickAsync();
        var elementHandles = await page.Locator("div.movie-details div.info-container div p").ElementHandlesAsync();
        var descriptionParagraphs = new List<string>();
        foreach (var elementHandle in elementHandles)
        {
            var descriptionParagraph = await elementHandle.TextContentAsync();
            if (!string.IsNullOrWhiteSpace(descriptionParagraph))
            {
                descriptionParagraphs.Add(descriptionParagraph);
            }
        }
        return string.Join("\r\n\r\n", descriptionParagraphs);
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var previewElement = await scenePage.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");
        await _downloader.DownloadSceneImageAsync(scene, backgroundImageUrl);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = ">" }).ClickAsync();
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var downloadMenuLocator = page.Locator("div svg.fa-film");
        if (!await downloadMenuLocator.IsVisibleAsync())
        {
            throw new DownloadException(false, $"Could not find download menu for {scene.Url}. Skipping...");
        }

        await downloadMenuLocator.ClickAsync();

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.FirstOrDefault(f => f.DownloadOption.ResolutionHeight == 360) ?? availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        return await _downloader.DownloadSceneAsync(scene, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            await selectedDownload.ElementHandle.ClickAsync();
        });
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadMenuLocator = page.Locator("div svg.fa-film");
        if (!await downloadMenuLocator.IsVisibleAsync())
        {
            throw new DownloadException(false, $"Could not find download menu for {page.Url}. Skipping...");
        }

        await downloadMenuLocator.ClickAsync();

        var downloadLinks = await page.Locator("div.dropdown-menu a").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var description = await downloadLink.InnerTextAsync();
            var sizeElement = await downloadLink.QuerySelectorAsync("span.pull-right");
            var size = await sizeElement.TextContentAsync();
            var resolution = description.Replace(size, "");
            var url = await downloadLink.GetAttributeAsync("href");
            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        -1,
                        HumanParser.ParseResolutionHeight(resolution),
                        HumanParser.ParseFileSize(size),
                        -1,
                        string.Empty,
                        url),
                    downloadLink));
        }
        return availableDownloads;
    }
}
