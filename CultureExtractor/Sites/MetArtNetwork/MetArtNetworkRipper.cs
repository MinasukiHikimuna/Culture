using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Serilog;
using CultureExtractor.Interfaces;

namespace CultureExtractor.Sites.MetArtNetwork;

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
    private readonly SqliteContext _sqliteContext;
    private readonly Repository _repository;

    public MetArtNetworkRipper()
    {
        _sqliteContext = new SqliteContext();
        _repository = new Repository(_sqliteContext);
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

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(IPage page)
    {
        var currentPage = await page.Locator("nav.pagination > a.active").TextContentAsync();
        var isFirstPage = currentPage == "1";

        var currentScenes = await page.Locator("div.card-media a").ElementHandlesAsync();

        return isFirstPage
            ? currentScenes.Skip(1).ToList().AsReadOnly()
            : currentScenes;
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var url = await currentScene.GetAttributeAsync("href");
        var sceneShortName = url.Substring(url.LastIndexOf("/movie/") + "/movie/".Length + 1);
        return (url, sceneShortName);
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page)
    {
        var metArtScenePage = new MetArtScenePage(page);
        var releaseDate = await metArtScenePage.ScrapeReleaseDateAsync();
        var duration = await metArtScenePage.ScrapeDurationAsync();
        var description = await metArtScenePage.ScrapeDescriptionAsync();
        var name = await metArtScenePage.ScrapeTitleAsync();
        var performers = await metArtScenePage.ScrapePerformersAsync(site.Url);

        var wholeDetails = await page.Locator("div.movie-details > div > div > div > ul").TextContentAsync();


        var tagElements = await page.Locator("div.tags-wrapper > div > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagShortName = tagUrl.Replace("/tags/", "");
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagShortName, tagName, tagUrl));
        }

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
            tags
        );

        return scene;
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage page, IElementHandle currentScene)
    {
        var previewElement = await page.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");
        await new Downloader().DownloadSceneImageAsync(scene, backgroundImageUrl);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = ">" }).ClickAsync();
    }

    public async Task DownloadSceneAsync(SceneEntity scene, IPage page, string rippingPath)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        var performerNames = scene.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        await page.Locator("div svg.fa-film").ClickAsync();

        var downloadUrl = await page.Locator("div.dropdown-menu a").Filter(new() { HasTextString = "360p SD" }).GetAttributeAsync("href");

        var waitForDownloadTask = page.WaitForDownloadAsync();
        await page.Locator("div.dropdown-menu a").Filter(new() { HasTextString = "360p SD" }).ClickAsync();
        var download = await waitForDownloadTask;
        var suggestedFilename = download.SuggestedFilename;

        var suffix = Path.GetExtension(suggestedFilename);
        var name = $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}{suffix}";
        name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));

        var path = Path.Join(rippingPath, name);

        Log.Verbose($"Downloading\r\n    URL:  {downloadUrl}\r\n    Path: {path}");

        await download.SaveAsAsync(path);
    }
}
