using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

[PornNetwork("nubilesporn")]
[PornSite("nubilesporn")]
public class NubilesPornRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public NubilesPornRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var usernameInput = page.GetByPlaceholder("Email or Username");
        if (await usernameInput.IsVisibleAsync())
        {
            await page.GetByPlaceholder("Email or Username").ClickAsync();
            await page.GetByPlaceholder("Email or Username").FillAsync(site.Username);

            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            // TODO: let's see if we need to manually enable this at all
            // await page.GetByText("Remember me").ClickAsync();

            await page.GetByRole(AriaRole.Button, new() { NameString = "Sign In" }).ClickAsync();
            await page.WaitForLoadStateAsync();

            await Task.Delay(5000);

            if (await page.GetByRole(AriaRole.Button, new() { NameString = "Sign In" }).IsVisibleAsync())
            {
                await page.GetByRole(AriaRole.Button, new() { NameString = "Sign In" }).ClickAsync();
                await page.WaitForLoadStateAsync();
            }
        }

        await Task.Delay(5000);

        await page.GotoAsync(site.Url);
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator("ul.navbar-nav > li.nav-item > a.nav-link").Nth(0).ClickAsync();
        await page.WaitForLoadStateAsync();

        var lastPageElement = await page.QuerySelectorAsync("ul.pagination li.page-item div.dropdown div.dropdown-menu a:last-of-type");
        var lastPage = await lastPageElement.TextContentAsync();

        return int.Parse(lastPage);
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var previewElement = await scenePage.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");

        try
        {
            var candidate = backgroundImageUrl.Replace("1280", "1920");
            await _downloader.DownloadSceneImageAsync(scene, candidate, scene.Url);
        }
        catch (WebException ex)
        {
            if (ex.Status == WebExceptionStatus.ProtocolError && (ex.Response as HttpWebResponse)?.StatusCode == HttpStatusCode.NotFound)
            {
                try
                {
                    await _downloader.DownloadSceneImageAsync(scene, backgroundImageUrl, scene.Url);
                }
                catch (WebException ex2)
                {
                    if (ex2.Status == WebExceptionStatus.ProtocolError && (ex2.Response as HttpWebResponse)?.StatusCode == HttpStatusCode.NotFound)
                    {
                        Log.Warning($"Unable to download preview image for {scene.Id} {scene.Name} from URL {backgroundImageUrl}.", ex2);
                    }
                    else
                    {
                        throw;
                    }
                }
            }
            else
            {
                throw;
            }
        }
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var sceneHandles = await page.Locator("div.Videoset div.content-grid-item").ElementHandlesAsync();

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
        var linkElement = await currentScene.QuerySelectorAsync("figcaption > div.caption-header > span.title > a");
        var url = await linkElement.GetAttributeAsync("href");

        string pattern = @"/video/watch/(?<id>\d+)/";
        Match match = Regex.Match(url, pattern);
        if (match.Success)
        {
            var id = match.Groups["id"].Value;
            return new SceneIdAndUrl(id, url);
        }

        string altPattern = @"%2Fvideo%2Fwatch%2F(?<id>\d+)%2F";
        Match altMatch = Regex.Match(url, altPattern);
        if (altMatch.Success)
        {
            var id = altMatch.Groups["id"].Value;
            return new SceneIdAndUrl(id, url);
        }

        throw new Exception($"Unable to parse ID from {url}");
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.Locator("ul.pagination > li.page-item").Nth(-2).ClickAsync();
    }

    public async Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response)
    {
        if (response.Url == "https://site-api.project1service.com/v2/releases/" + sceneShortName)
        {
            var bodyBuffer = await response.BodyAsync();
            var body = System.Text.Encoding.UTF8.GetString(bodyBuffer);
            return new CapturedResponse(Enum.GetName(AdultTimeRequestType.SceneMetadata)!, response);
        }

        return null;
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
    {
        var releaseDateRaw = await page.Locator("div.content-pane-title span.date").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw);

        var durationRaw = await page.Locator("span.vjs-remaining-time-display").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("div.content-pane-title h2").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performersRaw = await page.Locator("div.content-pane-performers > a.model").ElementHandlesAsync();

        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersRaw)
        {
            var performerUrl = await performerElement.GetAttributeAsync("href");
            var shortName = performerUrl.Replace("/model/profile/", "");
            var name = await performerElement.TextContentAsync();
            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        var elementHandles = await page.Locator("div.content-pane-description p").ElementHandlesAsync();
        var descriptionParagraphs = new List<string>();
        foreach (var elementHandle in elementHandles)
        {
            var descriptionParagraph = await elementHandle.TextContentAsync();
            if (!string.IsNullOrWhiteSpace(descriptionParagraph))
            {
                descriptionParagraphs.Add(descriptionParagraph);
            }
        }
        string description = string.Join("\r\n\r\n", descriptionParagraphs).Trim();

        var tagElements = await page.Locator("div.categories > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Replace("/video/category/", "");
            var tagNameRaw = await tagElement.TextContentAsync();
            var tagName = tagNameRaw.Replace("\n", "").Trim();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
            null,
            site,
            subSite,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            new List<SiteTag>(),
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            "{}"
        );
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IList<CapturedResponse> responses)
    {
        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        return await _downloader.DownloadSceneAsync(scene, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            await page.GetByRole(AriaRole.Button).Filter(new LocatorFilterOptions() { HasText = "Downloads" }).ClickAsync();
            await selectedDownload.ElementHandle.ClickAsync();
        });
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadLinks = await page.Locator("div.dropdown-downloads").First.Locator("a.dropdown-downloads-link").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", " ").Trim();

            var resolutionWidth = HumanParser.ParseResolutionWidth(description);
            var resolutionHeight = HumanParser.ParseResolutionHeight(description);

            var url = await downloadLink.GetAttributeAsync("href");

            string pattern = @"\((\d+[\.\d]*)\s*(GB|MB|KB)\)";
            Match match = Regex.Match(description, pattern);
            if (!match.Success)
            {
                throw new Exception($"Unable to parse ID from {url}");
            }

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        HumanParser.ParseFileSize(match.Groups[1].Value + " " + match.Groups[2].Value),
                        -1,
                        string.Empty,
                        url),
                    downloadLink));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.FileSize).ToList();
    }

    public Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        throw new NotImplementedException();
    }
}
