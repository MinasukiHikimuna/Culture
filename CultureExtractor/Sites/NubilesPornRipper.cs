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
    private readonly IRepository _repository;

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

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var currentScenes = await page.Locator("div.Videoset div.content-grid-item").ElementHandlesAsync();
        return currentScenes;
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var linkElement = await currentScene.QuerySelectorAsync("figcaption > div.caption-header > span.title > a");
        var url = await linkElement.GetAttributeAsync("href");

        string pattern = @"/video/watch/(?<id>\d+)/";
        Match match = Regex.Match(url, pattern);
        if (match.Success)
        {
            var id = match.Groups["id"].Value;
            return (url, id);
        }

        string altPattern = @"%2Fvideo%2Fwatch%2F(?<id>\d+)%2F";
        Match altMatch = Regex.Match(url, altPattern);
        if (altMatch.Success)
        {
            var id = altMatch.Groups["id"].Value;
            return (url, id);
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

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
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

        var subSiteElement = await page.QuerySelectorAsync("div.content-pane-title a.site-link");
        var subSiteShortNameRaw = await subSiteElement.GetAttributeAsync("href");
        var subSiteShortName = subSiteShortNameRaw.Replace("/video/website/", "");
        var subSiteNameRaw = await subSiteElement.TextContentAsync();
        var subSiteName = subSiteNameRaw.Replace("\n", "").Trim();

        var subSite = new SubSite(null, subSiteShortName, subSiteName, site);

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


    private class BrazzersRootobject
    {
        public Meta meta { get; set; }
        public BrazzersResult result { get; set; }
    }

    private class Meta
    {
        public int count { get; set; }
        public int total { get; set; }
    }

    private class BrazzersResult
    {
        public string brand { get; set; }
        public Brandmeta brandMeta { get; set; }
        public int id { get; set; }
        public int spartanId { get; set; }
        public string type { get; set; }
        public string title { get; set; }
        public DateTime dateReleased { get; set; }
        public string description { get; set; }
        public int position { get; set; }
        public bool isVR { get; set; }
        public string sexualOrientation { get; set; }
        public string privacy { get; set; }
        public bool isDownloadable { get; set; }
        public Stats stats { get; set; }
        public Actor[] actors { get; set; }
        public Gallery[] galleries { get; set; }
        public Images images { get; set; }
        public Tag[] tags { get; set; }
        public Timetag[] timeTags { get; set; }
        public Videos videos { get; set; }
        public Group[] groups { get; set; }
        public bool isMemberUnlocked { get; set; }
        public bool isFreeScene { get; set; }
        public Customlist[] customLists { get; set; }
        public object reaction { get; set; }
        public bool isUpcomingPlayable { get; set; }
        public bool isUpcoming { get; set; }
        public bool isMicrotransactable { get; set; }
        public object bundleId { get; set; }
    }

    private class Brandmeta
    {
        public string shortName { get; set; }
        public string displayName { get; set; }
    }

    private class Stats
    {
        public int likes { get; set; }
        public int dislikes { get; set; }
        public int rating { get; set; }
        public float score { get; set; }
        public int downloads { get; set; }
        public int plays { get; set; }
        public int views { get; set; }
    }

    private class Images
    {
        public Poster poster { get; set; }
        public Card_Main_Rect card_main_rect { get; set; }
    }

    private class Poster
    {
        public _0 _0 { get; set; }
        public _1 _1 { get; set; }
        public _2 _2 { get; set; }
        public _3 _3 { get; set; }
        public _4 _4 { get; set; }
        public _5 _5 { get; set; }
        public string alternateText { get; set; }
        public int imageVersion { get; set; }
    }

    private class _0
    {
        public Xs xs { get; set; }
        public Sm sm { get; set; }
        public Md md { get; set; }
        public Lg lg { get; set; }
        public Xl xl { get; set; }
        public Xx xx { get; set; }
    }

    private class Xs
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls urls { get; set; }
    }

    private class Urls
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls1 urls { get; set; }
    }

    private class Urls1
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls2 urls { get; set; }
    }

    private class Urls2
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls3 urls { get; set; }
    }

    private class Urls3
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls4 urls { get; set; }
    }

    private class Urls4
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xx
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls5 urls { get; set; }
    }

    private class Urls5
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _1
    {
        public Xs1 xs { get; set; }
        public Sm1 sm { get; set; }
        public Md1 md { get; set; }
        public Lg1 lg { get; set; }
        public Xl1 xl { get; set; }
        public Xx1 xx { get; set; }
    }

    private class Xs1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls6 urls { get; set; }
    }

    private class Urls6
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls7 urls { get; set; }
    }

    private class Urls7
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls8 urls { get; set; }
    }

    private class Urls8
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls9 urls { get; set; }
    }

    private class Urls9
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls10 urls { get; set; }
    }

    private class Urls10
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xx1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls11 urls { get; set; }
    }

    private class Urls11
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _2
    {
        public Xs2 xs { get; set; }
        public Sm2 sm { get; set; }
        public Md2 md { get; set; }
        public Lg2 lg { get; set; }
        public Xl2 xl { get; set; }
        public Xx2 xx { get; set; }
    }

    private class Xs2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls12 urls { get; set; }
    }

    private class Urls12
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls13 urls { get; set; }
    }

    private class Urls13
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls14 urls { get; set; }
    }

    private class Urls14
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls15 urls { get; set; }
    }

    private class Urls15
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls16 urls { get; set; }
    }

    private class Urls16
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xx2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls17 urls { get; set; }
    }

    private class Urls17
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _3
    {
        public Xs3 xs { get; set; }
        public Sm3 sm { get; set; }
        public Md3 md { get; set; }
        public Lg3 lg { get; set; }
        public Xl3 xl { get; set; }
        public Xx3 xx { get; set; }
    }

    private class Xs3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls18 urls { get; set; }
    }

    private class Urls18
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls19 urls { get; set; }
    }

    private class Urls19
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls20 urls { get; set; }
    }

    private class Urls20
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls21 urls { get; set; }
    }

    private class Urls21
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls22 urls { get; set; }
    }

    private class Urls22
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xx3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls23 urls { get; set; }
    }

    private class Urls23
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _4
    {
        public Xs4 xs { get; set; }
        public Sm4 sm { get; set; }
        public Md4 md { get; set; }
        public Lg4 lg { get; set; }
        public Xl4 xl { get; set; }
        public Xx4 xx { get; set; }
    }

    private class Xs4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls24 urls { get; set; }
    }

    private class Urls24
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls25 urls { get; set; }
    }

    private class Urls25
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls26 urls { get; set; }
    }

    private class Urls26
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls27 urls { get; set; }
    }

    private class Urls27
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls28 urls { get; set; }
    }

    private class Urls28
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xx4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls29 urls { get; set; }
    }

    private class Urls29
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _5
    {
        public Xs5 xs { get; set; }
        public Sm5 sm { get; set; }
        public Md5 md { get; set; }
        public Lg5 lg { get; set; }
        public Xl5 xl { get; set; }
        public Xx5 xx { get; set; }
    }

    private class Xs5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls30 urls { get; set; }
    }

    private class Urls30
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls31 urls { get; set; }
    }

    private class Urls31
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls32 urls { get; set; }
    }

    private class Urls32
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls33 urls { get; set; }
    }

    private class Urls33
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls34 urls { get; set; }
    }

    private class Urls34
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xx5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls35 urls { get; set; }
    }

    private class Urls35
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Card_Main_Rect
    {
        public _01 _0 { get; set; }
        public _11 _1 { get; set; }
        public _21 _2 { get; set; }
        public _31 _3 { get; set; }
        public _41 _4 { get; set; }
        public _51 _5 { get; set; }
        public string alternateText { get; set; }
        public int imageVersion { get; set; }
    }

    private class _01
    {
        public Xs6 xs { get; set; }
        public Sm6 sm { get; set; }
        public Md6 md { get; set; }
        public Lg6 lg { get; set; }
        public Xl6 xl { get; set; }
    }

    private class Xs6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls36 urls { get; set; }
    }

    private class Urls36
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls37 urls { get; set; }
    }

    private class Urls37
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls38 urls { get; set; }
    }

    private class Urls38
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls39 urls { get; set; }
    }

    private class Urls39
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls40 urls { get; set; }
    }

    private class Urls40
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _11
    {
        public Xs7 xs { get; set; }
        public Sm7 sm { get; set; }
        public Md7 md { get; set; }
        public Lg7 lg { get; set; }
        public Xl7 xl { get; set; }
    }

    private class Xs7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls41 urls { get; set; }
    }

    private class Urls41
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls42 urls { get; set; }
    }

    private class Urls42
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls43 urls { get; set; }
    }

    private class Urls43
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls44 urls { get; set; }
    }

    private class Urls44
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls45 urls { get; set; }
    }

    private class Urls45
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _21
    {
        public Xs8 xs { get; set; }
        public Sm8 sm { get; set; }
        public Md8 md { get; set; }
        public Lg8 lg { get; set; }
        public Xl8 xl { get; set; }
    }

    private class Xs8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls46 urls { get; set; }
    }

    private class Urls46
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls47 urls { get; set; }
    }

    private class Urls47
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls48 urls { get; set; }
    }

    private class Urls48
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls49 urls { get; set; }
    }

    private class Urls49
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls50 urls { get; set; }
    }

    private class Urls50
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _31
    {
        public Xs9 xs { get; set; }
        public Sm9 sm { get; set; }
        public Md9 md { get; set; }
        public Lg9 lg { get; set; }
        public Xl9 xl { get; set; }
    }

    private class Xs9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls51 urls { get; set; }
    }

    private class Urls51
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls52 urls { get; set; }
    }

    private class Urls52
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls53 urls { get; set; }
    }

    private class Urls53
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls54 urls { get; set; }
    }

    private class Urls54
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls55 urls { get; set; }
    }

    private class Urls55
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _41
    {
        public Xs10 xs { get; set; }
        public Sm10 sm { get; set; }
        public Md10 md { get; set; }
        public Lg10 lg { get; set; }
        public Xl10 xl { get; set; }
    }

    private class Xs10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls56 urls { get; set; }
    }

    private class Urls56
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls57 urls { get; set; }
    }

    private class Urls57
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls58 urls { get; set; }
    }

    private class Urls58
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls59 urls { get; set; }
    }

    private class Urls59
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls60 urls { get; set; }
    }

    private class Urls60
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class _51
    {
        public Xs11 xs { get; set; }
        public Sm11 sm { get; set; }
        public Md11 md { get; set; }
        public Lg11 lg { get; set; }
        public Xl11 xl { get; set; }
    }

    private class Xs11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls61 urls { get; set; }
    }

    private class Urls61
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Sm11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls62 urls { get; set; }
    }

    private class Urls62
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Md11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls63 urls { get; set; }
    }

    private class Urls63
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Lg11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls64 urls { get; set; }
    }

    private class Urls64
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Xl11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls65 urls { get; set; }
    }

    private class Urls65
    {
        public string _default { get; set; }
        public string webp { get; set; }
    }

    private class Videos
    {
        public Full full { get; set; }
        public Mediabook mediabook { get; set; }
    }

    private class Full
    {
        public int id { get; set; }
        public string type { get; set; }
        public int part { get; set; }
        public int length { get; set; }
        public Dictionary<string, VideoFile> files { get; set; }
        public string alternateText { get; set; }
    }

    private class VideoFile
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public VideoFileUrls urls { get; set; }
        public string label { get; set; }
    }

    private class VideoFileUrls
    {
        public string view { get; set; }
        public string download { get; set; }
    }
    
    private class Mediabook
    {
        public int id { get; set; }
        public string type { get; set; }
        public int part { get; set; }
        public int length { get; set; }
        public Files1 files { get; set; }
        public string alternateText { get; set; }
    }

    private class Files1
    {
        public _720P1 _720p { get; set; }
        public _320P1 _320p { get; set; }
    }

    private class _720P1
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public int sizeBytes { get; set; }
        public string type { get; set; }
        public Urls73 urls { get; set; }
        public string label { get; set; }
    }

    private class Urls73
    {
        public string view { get; set; }
        public string download { get; set; }
    }

    private class _320P1
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public int sizeBytes { get; set; }
        public string type { get; set; }
        public Urls74 urls { get; set; }
        public string label { get; set; }
    }

    private class Urls74
    {
        public string view { get; set; }
        public string download { get; set; }
    }

    private class Actor
    {
        public int id { get; set; }
        public string name { get; set; }
        public string gender { get; set; }
        public object[] imageMasters { get; set; }
        public object[] images { get; set; }
        public object[] tags { get; set; }
        public string customUrl { get; set; }
    }

    private class Child
    {
        public int id { get; set; }
        public int spartanId { get; set; }
        public string type { get; set; }
        public string title { get; set; }
        public int position { get; set; }
        public object[] imageMasters { get; set; }
        public object[] actors { get; set; }
        public object[] children { get; set; }
        public object[] collections { get; set; }
        public object[] galleries { get; set; }
        public object[] images { get; set; }
        public object[] tags { get; set; }
        public object[] timeTags { get; set; }
        public object videos { get; set; }
        public object[] groups { get; set; }
    }

    private class Collection
    {
        public int id { get; set; }
        public string name { get; set; }
        public string shortName { get; set; }
        public object[] site { get; set; }
        public object[] imageMasters { get; set; }
        public object[] images { get; set; }
        public string customUrl { get; set; }
    }

    private class Gallery
    {
        public int id { get; set; }
        public string type { get; set; }
        public string format { get; set; }
        public string directory { get; set; }
        public string filePattern { get; set; }
        public int filesCount { get; set; }
        public string multiCdnId { get; set; }
        public Urls75 urls { get; set; }
        public string url { get; set; }
    }

    private class Urls75
    {
        public string view { get; set; }
    }

    private class Tag
    {
        public int id { get; set; }
        public string name { get; set; }
        public bool isVisible { get; set; }
        public string category { get; set; }
        public int categoryOrder { get; set; }
        public bool showOnProfile { get; set; }
        public object[] imageMasters { get; set; }
        public object[] images { get; set; }
        public string customUrl { get; set; }
    }

    private class Timetag
    {
        public int id { get; set; }
        public string name { get; set; }
        public int startTime { get; set; }
        public int endTime { get; set; }
    }

    private class Group
    {
        public int id { get; set; }
        public string name { get; set; }
        public string displayName { get; set; }
        public string shortName { get; set; }
        public object[] images { get; set; }
        public bool blockedDownloads { get; set; }
        public bool isTest { get; set; }
        public object[] imageMasters { get; set; }
    }

    private class Customlist
    {
        public string brand { get; set; }
        public int memberId { get; set; }
        public string contentType { get; set; }
        public int contentId { get; set; }
        public string listSlug { get; set; }
        public string createdTime { get; set; }
    }
}
