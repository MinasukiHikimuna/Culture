using System.Net;
using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Web;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Xabe.FFmpeg;

namespace CultureExtractor.Sites;

[Site("brazzers")]
[Site("digitalplayground")]
public class AyloRipper : ISiteScraper, IYieldingScraper
{
    private readonly IDownloader _downloader;
    private readonly ICaptchaSolver _captchaSolver;
    private IPlaywrightFactory _playwrightFactory;

    public AyloRipper(IDownloader downloader, ICaptchaSolver captchaSolver, IPlaywrightFactory playwrightFactory, IRepository repository, ICultureExtractorContext context)
    {
        _downloader = downloader;
        _captchaSolver = captchaSolver;
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _context = context;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var usernameInput = page.GetByPlaceholder("Username or Email");
        if (await usernameInput.IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username or Email").ClickAsync();
            await page.GetByPlaceholder("Username or Email").FillAsync(site.Username);

            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            // TODO: let's see if we need to manually enable this at all
            // await page.GetByText("Remember me").ClickAsync();

            await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
            await page.WaitForLoadStateAsync();

            await Task.Delay(5000);

            await _captchaSolver.SolveCaptchaIfNeededAsync(page);

            if (await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).IsVisibleAsync())
            {
                await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
                await page.WaitForLoadStateAsync();
            }
        }

        await Task.Delay(5000);

        await page.GotoAsync(site.Url);

        Log.Information($"Logged into {site.Name}.");
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GotoAsync(site.Url + "/scenes");

        await page.WaitForLoadStateAsync();
        
        var lastPageUrl = await page.Locator("a[href^='/scenes?page=']").Last.GetAttributeAsync("href");
        var lastPage = lastPageUrl.Replace("/scenes?page=", "");

        return int.Parse(lastPage);
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(site, page, pageNumber);
        
        // Aylo occasionally forces re-login.
        if (page.Url.Contains("/login"))
        {
            await LoginAsync(site, page);
            await GoToPageAsync(site, page, pageNumber);
        }

        var releaseHandleLocators = page.Locator("span a[href^='/scene/']");

        try
        {
            await releaseHandleLocators.First.WaitForAsync(new LocatorWaitForOptions { State = WaitForSelectorState.Visible });
        }
        catch (TimeoutException)
        {
            // For unknown reason some pages don't have scenes at all. Especially page 154. Verified manually in
            // non-Playwright browser.
        }
        
        
        var releaseHandles = await releaseHandleLocators.ElementHandlesAsync();

        var listedReleases = new List<ListedRelease>();
        foreach (var releaseHandle in releaseHandles.Reverse())
        {
            var releaseIdAndUrl = await GetReleaseIdAsync(releaseHandle);
            listedReleases.Add(new ListedRelease(null, releaseIdAndUrl.Id, releaseIdAndUrl.Url, releaseHandle));
        }

        return listedReleases.AsReadOnly();
    }

    private static async Task GoToPageAsync(Site site, IPage page, int pageNumber)
    {
        await page.GotoAsync(site.Url + "/scenes?page=" + pageNumber);
    }

    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle currentRelease)
    {
        var url = await currentRelease.GetAttributeAsync("href");

        var pattern = @"/scene/(?<id>\d+)/";
        Match match = Regex.Match(url, pattern);
        if (!match.Success)
        {
            throw new Exception($"Unable to parse ID from {url}");
        }

        var id = match.Groups["id"].Value;

        return new ReleaseIdAndUrl(id, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        // Aylo occasionally forces re-login.
        if (page.Url.Contains("/login"))
        {
            await LoginAsync(site, page);
            await page.GotoAsync(url);
        }
        
        var request = requests.FirstOrDefault(r => r.Url == "https://site-api.project1service.com/v2/releases/" + releaseShortName);
        var response = await request.ResponseAsync();
        var jsonContent = await response.BodyAsync();
        var data = JsonSerializer.Deserialize<AyloRootObject>(jsonContent)!;


        var sceneData = data.result;

        var releaseDate = DateOnly.FromDateTime(sceneData.dateReleased.ToUniversalTime());
        var duration = TimeSpan.FromSeconds(sceneData.videos.full.length);
        var title = sceneData.title;

        var performers = new List<SitePerformer>();
        var genderSorted = sceneData.actors.Where(a => a.gender == "female").ToList().Concat(sceneData.actors.Where(a => a.gender != "female").ToList()).ToList();
        foreach (var performer in genderSorted)
        {
            var shortName = performer.id.ToString();
            var performerUrl = string.Empty;
            var name = performer.name;
            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        var tags = new List<SiteTag>();
        foreach (var tag in sceneData.tags)
        {
            var shortName = tag.id.ToString();
            var name = tag.name;
            tags.Add(new SiteTag(shortName.ToString(), name, string.Empty));
        }


        string description = sceneData.description ?? string.Empty;

        sceneData.videos.full.files.Remove("hls");
        sceneData.videos.full.files.Remove("dash");

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(sceneData);

        Release release = new Release(
            releaseUuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.AvailableVideoFile).ToList(),
            JsonSerializer.Serialize(sceneData),
            DateTime.Now);

        var previewElement = await page.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");

        await _downloader.DownloadSceneImageAsync(release, backgroundImageUrl, release.Url);
        
        return release;
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        // Aylo occasionally forces re-login.
        if (page.Url.Contains("/login"))
        {
            await LoginAsync(release.Site, page);
            await page.GotoAsync(release.Url);
        }
        
        var request = requests.FirstOrDefault(r => r.Url == "https://site-api.project1service.com/v2/releases/" + release.ShortName);
        var response = await request.ResponseAsync();
        var jsonContent = await response.TextAsync();
        var data = JsonSerializer.Deserialize<AyloRootObject>(jsonContent)!;
        var sceneData = data.result;

        sceneData.videos.full.files.Remove("hls");
        sceneData.videos.full.files.Remove("dash");

        var availableDownloads = await ParseAvailableDownloadsAsync(sceneData);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        var cookieString = await page.EvaluateAsync<string>("() => document.cookie");

        var headers = new WebHeaderCollection()
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };

        var suggestedFilename = selectedDownload.AvailableVideoFile.Url[(selectedDownload.AvailableVideoFile.Url.LastIndexOf("/", StringComparison.Ordinal) + 1)..];
        suggestedFilename = suggestedFilename[..suggestedFilename.IndexOf("?", StringComparison.Ordinal)];
        var suffix = Path.GetExtension(suggestedFilename);
        var name = ReleaseNamer.Name(release, suffix);

        return await _downloader.DownloadSceneDirectAsync(release, selectedDownload.AvailableVideoFile, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url, fileName: name);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(BrazzersResult sceneData)
    {
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();

        foreach (var downloadFileSize in sceneData.videos.full.files.Keys)
        {
            var description = downloadFileSize;
            var videoFile = sceneData.videos.full.files[downloadFileSize];

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                new AvailableVideoFile(
                    "video",
                    "scene",
                    description,
                    videoFile.urls.view,
                    -1,
                    HumanParser.ParseResolutionHeight(downloadFileSize),
                    videoFile.sizeBytes,
                    -1,
                    HumanParser.ParseCodec("H.264")
                ),
                null));
        }

        return availableDownloads.OrderByDescending(d => d.AvailableVideoFile.FileSize).ToList();
    }

    private class AyloRootObject
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

    private static string ScenesUrl(Site site, int pageNumber) =>
        $"{site.Url}/scenes?page={pageNumber}";
    
    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);

        var requests = await CaptureRequestsAsync(site, page);

        SetHeadersFromActualRequest(site, requests);
        await foreach (var scene in ScrapeScenesAsync(site, scrapeOptions))
        {
            yield return scene;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, ScrapeOptions scrapeOptions)
    {
        var moviesInitialPage = await GetMoviesPageAsync(site, 1);

        var pages = (int)Math.Ceiling((double)moviesInitialPage.meta.total / moviesInitialPage.meta.count);
        for (var pageNumber = 1; pageNumber <= pages; pageNumber++)
        {
            await Task.Delay(5000);

            var moviesPage = await GetMoviesPageAsync(site, pageNumber);

            Log.Information($"Page {pageNumber}/{pages} contains {moviesPage.result.Length} releases");

            var movies = moviesPage.result
                .ToDictionary(r => r.id.ToString(), r => r);

            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, movies.Keys.ToList());

            var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);
            
            var moviesToBeScraped = movies
                .Where(g => !existingReleasesDictionary.ContainsKey(g.Key) || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated)
                .Select(g => g.Value)
                .ToList();

            foreach (var movie in moviesToBeScraped)
            {
                await Task.Delay(1000);
                var shortName = movie.id.ToString();
                var scene = await ScrapeSceneAsync(site, shortName, existingReleasesDictionary);
                yield return scene;
            }
        }
    }

    private static async Task<Release> ScrapeSceneAsync(Site site, string shortName, Dictionary<string, Release> existingReleasesDictionary)
    {
        var movieUrl = MovieApiUrl(site, shortName);

        using var movieResponse = Client.GetAsync(movieUrl);
        var movieJson = await movieResponse.Result.Content.ReadAsStringAsync();
        var movieDetailsContainer = JsonSerializer.Deserialize<AyloMovieRequest.RootObject>(movieJson);
        if (movieDetailsContainer == null)
        {
            throw new InvalidOperationException("Could not read movie API response: " + movieJson);
        }

        var movieDetails = movieDetailsContainer.result;
        var sceneDownloads = movieDetails.videos.full.files
            .Where(keyValuePair => keyValuePair.Key != "dash" && keyValuePair.Key != "hls")
            .Select(keyValuePair => new AvailableVideoFile(
                "video",
                "scene",
                keyValuePair.Key,
                keyValuePair.Value.urls.view,
                -1,
                HumanParser.ParseResolutionHeight(keyValuePair.Key),
                keyValuePair.Value.sizeBytes,
                -1,
                string.Empty
            ))
            .OrderByDescending(availableFile => availableFile.ResolutionHeight)
            .ToList();

        var imageDownloads = new List<AyloMoviesRequest.PosterSizes>
            {
                movieDetails.images.poster._0,
                movieDetails.images.poster._1,
                movieDetails.images.poster._2,
                movieDetails.images.poster._3,
                movieDetails.images.poster._4,
                movieDetails.images.poster._5
            }
            .Select(posterSizes => posterSizes.xx)
            .Select((image, index) => new AvailableImageFile(
                "image",
                $"poster_xx_{index}",
                string.Empty,
                image.urls.default1,
                image.width,
                image.height,
                -1
            ))
            .ToList();

        var trailerDownloads = movieDetails.videos.mediabook.files
            .Select(keyValuePair =>
                new AvailableVideoFile("video", "trailer", keyValuePair.Key, keyValuePair.Value.urls.view, -1,
                    HumanParser.ParseResolutionHeight(keyValuePair.Value.format), keyValuePair.Value.sizeBytes, -1,
                    string.Empty)
            );

        var performers = movieDetails.actors.Where(a => a.gender == "female").ToList()
            .Concat(movieDetails.actors.Where(a => a.gender != "female").ToList())
            .Select(m => new SitePerformer(m.id.ToString(), m.name, string.Empty))
            .ToList();

        var tags = movieDetails.tags
            .Select(t => new SiteTag(t.id.ToString(), t.name, string.Empty))
            .ToList();

        var scene = new Release(
            existingReleasesDictionary.TryGetValue(shortName, out var existingRelease)
                ? existingRelease.Uuid
                : UuidGenerator.Generate(),
            site,
            null,
            DateOnly.FromDateTime(DateTime.Parse(movieDetails.dateReleased)),
            shortName,
            movieDetails.title,
            $"{site.Url}/scene/{movieDetails.id}",
            movieDetails.description ?? string.Empty,
            -1,
            performers,
            tags,
            new List<IAvailableFile>()
                .Concat(sceneDownloads)
                .Concat(imageDownloads)
                .Concat(trailerDownloads),
            movieJson,
            DateTime.Now);
        return scene;
    }

    private static string MoviesApiUrl(Site site, int pageNumber) =>
        $"https://site-api.project1service.com/v2/releases?blockId=4126598482&blockName=SceneListBlock&pageType=EXPLORE_SCENES&dateReleased=%3C2023-11-16&orderBy=-dateReleased&type=scene&limit=20&offset={(pageNumber - 1) * 20}";
    private static string MovieApiUrl(Site site, string shortName) =>
        $"https://site-api.project1service.com/v2/releases/{shortName}?pageType=PLAYER";
    
    private static async Task<AyloMoviesRequest.RootObject> GetMoviesPageAsync(Site site, int pageNumber)
    {
        var moviesApiUrl = MoviesApiUrl(site, pageNumber);

        using var response = await Client.GetAsync(moviesApiUrl);
        if (response.StatusCode != HttpStatusCode.OK)
        {
            throw new InvalidOperationException($"Could not read movies API response:{Environment.NewLine}Url={moviesApiUrl}{Environment.NewLine}StatusCode={response.StatusCode}{Environment.NewLine}ReasonPhrase={response.ReasonPhrase}");
        }
        
        var json = await response.Content.ReadAsStringAsync();
        var movies = JsonSerializer.Deserialize<AyloMoviesRequest.RootObject>(json);
        if (movies == null)
        {
            throw new InvalidOperationException("Could not read movies API response: " + json);
        }
        
        return movies;
    }
    
    private static Dictionary<string, string> SetHeadersFromActualRequest(Site site, IList<IRequest> requests)
    {
        var galleriesRequest = requests.SingleOrDefault(r => r.Url.StartsWith("https://site-api.project1service.com/v2/releases?"));
        if (galleriesRequest == null)
        {
            var requestUrls = requests.Select(r => r.Url + Environment.NewLine).ToList();
            throw new InvalidOperationException($"Could not read galleries API request from following requests:{Environment.NewLine}{string.Join("", requestUrls)}");
        }
        
        Client.DefaultRequestHeaders.Clear();
        foreach (var key in galleriesRequest.Headers.Keys)
        {
            Client.DefaultRequestHeaders.Add(key, galleriesRequest.Headers[key]);
        }
        
        return galleriesRequest.Headers;
    }

    private static readonly HttpClient Client = new();
    private readonly IRepository _repository;
    private ICultureExtractorContext _context;

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings,
        DownloadConditions downloadConditions, DownloadOptions downloadOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);
        var requests = await CaptureRequestsAsync(site, page);

        var headers = SetHeadersFromActualRequest(site, requests);
        var convertedHeaders = ConvertHeaders(headers);

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        
        foreach (var release in releases)
        {
            Log.Information("Downloading {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);

            var updatedScrape = await ScrapeSceneAsync(site, release.ShortName,
                new Dictionary<string, Release> { { release.ShortName, release } });
            
            var existingDownloadEntities = await _context.Downloads.Where(d => d.ReleaseUuid == release.Uuid).ToListAsync();
            await foreach (var videoDownload in DownloadsVideosAsync(downloadOptions, updatedScrape, existingDownloadEntities, headers, convertedHeaders))
            {
                yield return videoDownload;
            }
            await foreach (var trailerDownload in DownloadTrailersAsync(downloadOptions, updatedScrape, existingDownloadEntities))
            {
                yield return trailerDownload;
            }
            await foreach (var imageDownload in DownloadImagesAsync(updatedScrape, existingDownloadEntities, convertedHeaders))
            {
                yield return imageDownload;
            }
        }
    }
    
    private async IAsyncEnumerable<Download> DownloadsVideosAsync(DownloadOptions downloadOptions, Release release,
        List<DownloadEntity> existingDownloadEntities, IReadOnlyDictionary<string, string> headers, WebHeaderCollection convertedHeaders)
    {
        var availableVideos = release.AvailableFiles.OfType<AvailableVideoFile>().Where(d => d is { FileType: "video", ContentType: "scene" });
        var selectedVideo = downloadOptions.BestQuality
            ? availableVideos.FirstOrDefault()
            : availableVideos.LastOrDefault();
        if (selectedVideo == null || !NotDownloadedYet(existingDownloadEntities, selectedVideo))
        {
            yield break;
        }

        var uri = new Uri(selectedVideo.Url);
        var suggestedFileName = Path.GetFileName(uri.LocalPath);
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.Variant);

        var fileInfo = await TryDownloadAsync(release, selectedVideo, selectedVideo.Url, fileName, convertedHeaders);
        if (fileInfo == null)
        {
            yield break;
        }

        var videoHashes = Hasher.Phash(@"""" + fileInfo.FullName + @"""");
        yield return new Download(release, suggestedFileName, fileInfo.Name, selectedVideo, videoHashes);
    }
    
    private async IAsyncEnumerable<Download> DownloadTrailersAsync(DownloadOptions downloadOptions, Release release, List<DownloadEntity> existingDownloadEntities)
    {
        var availableTrailers = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "trailer" });
        var selectedTrailer = downloadOptions.BestQuality
            ? availableTrailers.FirstOrDefault()
            : availableTrailers.LastOrDefault();
        if (selectedTrailer == null  || !NotDownloadedYet(existingDownloadEntities, selectedTrailer))
        {
            yield break;
        }

        var trailerPlaylistFileName = $"trailer_{selectedTrailer.Variant}.m3u8";
        var trailerVideoFileName = $"trailer_{selectedTrailer.Variant}.mp4";

        // Note: we need to download the trailer without cookies because logged in users get the full scene
        // from the same URL.
        var fileInfo = await TryDownloadAsync(release, selectedTrailer, selectedTrailer.Url, trailerPlaylistFileName, new WebHeaderCollection());
        if (fileInfo == null)
        {
            yield break;
        }
        
        var trailerVideoFullPath = Path.Combine(fileInfo.DirectoryName, trailerVideoFileName);

        var snippet = await FFmpeg.Conversions.New()
            .Start(
                $"-protocol_whitelist \"file,http,https,tcp,tls\" -i \"{fileInfo.FullName}\" -y -c copy \"{trailerVideoFullPath}\"");

        var videoHashes = Hasher.Phash(@"""" + trailerVideoFullPath + @"""");
        yield return new Download(release,
            trailerPlaylistFileName,
            trailerVideoFileName,
            selectedTrailer,
            videoHashes);
    }
    
    private async IAsyncEnumerable<Download> DownloadImagesAsync(Release release, List<DownloadEntity> existingDownloadEntities, WebHeaderCollection convertedHeaders)
    {
        var imageFiles = release.AvailableFiles.OfType<AvailableImageFile>();
        foreach (var imageFile in imageFiles)
        {
            if (!NotDownloadedYet(existingDownloadEntities, imageFile))
            {
                continue;
            }
            
            var fileName = $"{imageFile.ContentType}.jpg";
            var fileInfo = await TryDownloadAsync(release, imageFile, imageFile.Url, fileName, convertedHeaders);
            if (fileInfo == null)
            {
                yield break;
            }
            
            var sha256Sum = Downloader.CalculateSHA256(fileInfo.FullName);
            var metadata = new ImageFileMetadata(sha256Sum);
            yield return new Download(release, $"{imageFile.ContentType}.jpg", fileInfo.Name, imageFile, metadata);
        }
    }
    
    private async Task<FileInfo?> TryDownloadAsync(Release release, IAvailableFile availableFile, string url, string fileName, WebHeaderCollection convertedHeaders)
    {
        const int maxRetryCount = 3; // Set the maximum number of retries
        int retryCount = 0;

        while (retryCount < maxRetryCount)
        {
            retryCount++;
            try
            {
                return await _downloader.DownloadFileAsync(
                    release,
                    url,
                    fileName,
                    release.Url,
                    convertedHeaders);
            }
            catch (WebException ex) when ((ex.Response as HttpWebResponse)?.StatusCode == HttpStatusCode.NotFound)
            {
                Log.Warning("Could not find {FileType} {ContentType} for {Release} from URL {Url}",
                    availableFile.FileType, availableFile.ContentType, release.Uuid, url);
                return null;
            }
            catch (WebException ex) when (ex.InnerException is IOException &&
                                          ex.InnerException.Message.Contains("The response ended prematurely"))
            {
                if (retryCount >= maxRetryCount)
                {
                    Log.Error("Max retry attempts reached for {FileType} {ContentType} for {Release} from URL {Url}.",
                        availableFile.FileType, availableFile.ContentType, release.Uuid, url);
                    return null;
                }

                Log.Warning(
                    "Download ended prematurely for {FileType} {ContentType} for {Release} from URL {Url}. Retrying...",
                    availableFile.FileType, availableFile.ContentType, release.Uuid, url);
            }
            catch (WebException ex)
            {
                Log.Error(ex, "Error downloading {FileType} {ContentType} for {Release} from URL {Url}",
                    availableFile.FileType, availableFile.ContentType, release.Uuid, url);
                return null;
            }
        }

        return null; // Return null if all retries fail
    }
    
    private static bool NotDownloadedYet(List<DownloadEntity> existingDownloadEntities, IAvailableFile bestVideo)
    {
        return !existingDownloadEntities.Exists(d => d.FileType == bestVideo.FileType && d.ContentType == bestVideo.ContentType && d.Variant == bestVideo.Variant);
    }
    
    private static async Task<List<IRequest>> CaptureRequestsAsync(Site site, IPage page)
    {
        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });

        await page.GotoAsync(ScenesUrl(site, 1));
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        await page.UnrouteAsync("**/*");
        return requests;
    }
    
    private static WebHeaderCollection ConvertHeaders(Dictionary<string, string> headers)
    {
        var convertedHeaders = new WebHeaderCollection();
        foreach (var header in headers)
        {
            convertedHeaders.Add(header.Key, header.Value);
        }
        return convertedHeaders;
    }
}
