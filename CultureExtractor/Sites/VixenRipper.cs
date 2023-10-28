using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

[PornNetwork("vixen")]
[PornSite("milfy")]
[PornSite("deeper")]
[PornSite("vixen")]
public class VixenRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public VixenRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var usernameInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Email" });
        if (await usernameInput.IsVisibleAsync())
        {
            await usernameInput.ClickAsync();
            await usernameInput.FillAsync(site.Username);

            var passwordInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Password" });
            await passwordInput.ClickAsync();
            await passwordInput.FillAsync(site.Password);

            await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
            await page.WaitForLoadStateAsync();

            await Task.Delay(5000);

            await page.WaitForLoadStateAsync();
            var continueButton = await page.QuerySelectorAsync("button[data-test-component='ContinueButton']");
            if (continueButton != null)
            {
                await continueButton.ClickAsync();
                await page.WaitForLoadStateAsync();
            }

            await page.WaitForLoadStateAsync();
            var hideForeverButton = await page.QuerySelectorAsync("p[data-test-component='HideForeverButton']");
            if (hideForeverButton != null)
            {
                await hideForeverButton.ClickAsync();
                await page.WaitForLoadStateAsync();
            }
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GotoAsync("/videos");
        await page.WaitForLoadStateAsync();

        var lastPageElement = await page.QuerySelectorAsync("div[data-test-component='Pagination'] a:has-text('Last')");
        var lastPageLink = await lastPageElement.GetAttributeAsync("href");
        if (string.IsNullOrEmpty(lastPageLink))
        {
            Log.Warning("Could not find 'Last' page link in pagination");
            return -1;
        }

        var lastPage = Regex.Match(lastPageLink, @"page=(\d+)").Groups[1].Value;
        if (string.IsNullOrEmpty(lastPage))
        {
            Log.Warning("Could not parse page number from url: {Url}", lastPageLink);
            return -1;
        }

        return int.Parse(lastPage);
    }

    public async Task DownloadAdditionalFilesAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene, IReadOnlyList<IRequest> requests)
    {
        var sceneMetadataRequest = requests
            .Where(r => r.Method == "POST")
            .Where(r => r.Url == $"{scene.Site.Url}/graphql")
            .FirstOrDefault();
        var response = await sceneMetadataRequest.ResponseAsync();
        var bodyBuffer = await response.BodyAsync();
        var jsonContent = System.Text.Encoding.UTF8.GetString(bodyBuffer);
        var data = JsonSerializer.Deserialize<VixenSceneRootObject>(jsonContent)!;

        var posterSource = data.data.findOneVideo.images.poster
            .OrderByDescending(i => i.width)
            .Select(i => i.src)
            .FirstOrDefault();

        await _downloader.DownloadSceneImageAsync(scene, posterSource, scene.Url);
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var sceneHandles = await page.Locator("div[data-test-component='VideoThumbnailContainer']").ElementHandlesAsync();

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
        var videoElement = await currentScene.QuerySelectorAsync("video");
        var videoSrc = await videoElement.GetAttributeAsync("src");

        var sceneId = Regex.Match(videoSrc, @"videos/(\d+)/").Groups[1].Value;

        var aElement = await currentScene.QuerySelectorAsync("a");
        var url = await aElement.GetAttributeAsync("href");

        return new SceneIdAndUrl(sceneId, url);
    }

    public async Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response)
    {
        if (response.Url == "https://members.milfy.com/graphql")
        {
            var bodyBuffer = await response.BodyAsync();
            var body = System.Text.Encoding.UTF8.GetString(bodyBuffer);
            return new CapturedResponse(Enum.GetName(AdultTimeRequestType.SceneMetadata)!, response);
        }

        return null;
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var sceneMetadataRequest = requests
            .Where(r => r.Method == "POST")
            .Where(r => r.Url == $"{site.Url}/graphql")
            .FirstOrDefault();
        var response = await sceneMetadataRequest.ResponseAsync();
        var bodyBuffer = await response.BodyAsync();
        var jsonContent = System.Text.Encoding.UTF8.GetString(bodyBuffer);
        var data = JsonSerializer.Deserialize<VixenSceneRootObject>(jsonContent)!;

        var releaseDate = DateOnly.FromDateTime(data.data.findOneVideo.releaseDate);
        var duration = HumanParser.ParseDuration(data.data.findOneVideo.runLength);
        var title = data.data.findOneVideo.title;

        var performers = new List<SitePerformer>();
        foreach (var modelSlug in data.data.findOneVideo.modelsSlugged)
        {
            var slug = modelSlug.slugged;
            var name = modelSlug.name;

            performers.Add(new SitePerformer(slug, name, $"/models/{slug}"));
        }

        string description = data.data.findOneVideo.description;

        var tags = new List<SiteTag>();
        foreach (var category in data.data.findOneVideo.categories)
        {
            var slug = category.slug;
            var tagName = category.name;
            tags.Add(new SiteTag(slug, tagName, $"/videos?search={category.name}"));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        var metadataJson = JsonSerializer.Serialize(data.data.findOneVideo);

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
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            metadataJson,
            DateTime.Now);
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        var cookieString = await page.EvaluateAsync<string>("() => document.cookie");

        var headers = new Dictionary<HttpRequestHeader, string>
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };

        var suggestedFilename = selectedDownload.DownloadOption.Url[(selectedDownload.DownloadOption.Url.LastIndexOf("/", StringComparison.Ordinal) + 1)..];
        suggestedFilename = suggestedFilename[..suggestedFilename.IndexOf("?", StringComparison.Ordinal)];
        var suffix = Path.GetExtension(suggestedFilename);
        var name = SceneNamer.Name(scene, suffix);

        return await _downloader.DownloadSceneDirectAsync(scene, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url, fileName: name);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        await page.ReloadAsync();

        var playButton = await page.QuerySelectorAsync("div[data-test-component='PlayButton']");
        
        await page.WaitForLoadStateAsync();
        await page.WaitForTimeoutAsync(10000);

        if (await playButton.IsVisibleAsync())
        {
            await playButton.ClickAsync();
        }

        var videoElement = await page.QuerySelectorAsync("video");
        await videoElement.HoverAsync();

        var resolutionButton = await page.QuerySelectorAsync(".vjs-resolution-button");
        await resolutionButton.ClickAsync();

        var resolutionMenuItems = await page.QuerySelectorAllAsync(".vjs-resolution .vjs-menu-item");
        var sources = new List<string>();

        await videoElement.HoverAsync();
        await resolutionButton.HoverAsync();
        await resolutionMenuItems[0].ClickAsync();

        var source = await videoElement.GetAttributeAsync("src");

        var availableDownloads = new List<DownloadDetailsAndElementHandle>();

        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        var cookieString = await page.EvaluateAsync<string>("() => document.cookie");

        HttpWebRequest request = WebRequest.Create(source) as HttpWebRequest;
        request.AllowAutoRedirect = false;
        request.Headers.Add(HttpRequestHeader.Referer, page.Url);
        request.Headers.Add(HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7");
        request.Headers.Add(HttpRequestHeader.UserAgent, userAgent);
        request.Headers.Add(HttpRequestHeader.Cookie, cookieString);
        HttpWebResponse response = request.GetResponse() as HttpWebResponse;
        if (response.StatusCode == HttpStatusCode.RedirectKeepVerb)
        {
            // Do something here...
            source = response.Headers["Location"];
        }

        var resolution = Regex.Match(source, @"(\d+)P.mp4").Groups[1].Value;

        availableDownloads.Add(
            new DownloadDetailsAndElementHandle(
                new DownloadOption(
                    resolution,
                    -1,
                    int.Parse(resolution),
                    -1,
                    -1,
                    string.Empty,
                    source),
                null));

        return availableDownloads.OrderByDescending(d => d.DownloadOption.ResolutionHeight).ToList();
    }

    public async Task<int> NavigateToSubSiteAndReturnPageCountAsync(Site site, SubSite subSite, IPage page)
    {
        await page.GotoAsync($"/channel/{subSite.ShortName}");
        await page.GetByRole(AriaRole.Heading, new() { NameString = "Recently Added\nview all" }).GetByRole(AriaRole.Link, new()
        {
            NameString = "view all"
        }).ClickAsync();

        var pageLinkHandles = await page.QuerySelectorAllAsync("nav.paginated-nav ul li:not(.disabled) a");
        if (pageLinkHandles.Count == 0)
        {
            throw new InvalidOperationException($"Could not find page links for subsite {subSite.Name}.");
        }

        // take second to last page link, because the last one is "next"
        var lastPageLinkHandle = pageLinkHandles[pageLinkHandles.Count - 2];
        var lastPageLinkText = await lastPageLinkHandle.TextContentAsync();
        return int.Parse(lastPageLinkText);
    }

    public async Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/videos?page={pageNumber}");
        await Task.Delay(1000);
    }


    public class VixenSceneRootObject
    {
        public Data data { get; set; }
    }

    public class Data
    {
        public Findonevideo findOneVideo { get; set; }
    }

    public class Findonevideo
    {
        public string id { get; set; }
        public string videoId { get; set; }
        public string newId { get; set; }
        public string uuid { get; set; }
        public string slug { get; set; }
        public string site { get; set; }
        public string title { get; set; }
        public string description { get; set; }
        public string descriptionHtml { get; set; }
        public object absoluteUrl { get; set; }
        public bool denied { get; set; }
        public bool isUpcoming { get; set; }
        public DateTime releaseDate { get; set; }
        public string runLength { get; set; }
        public Director[] directors { get; set; }
        public Category[] categories { get; set; }
        public object channel { get; set; }
        public Chapters chapters { get; set; }
        public object showcase { get; set; }
        public Tour tour { get; set; }
        public Modelsslugged[] modelsSlugged { get; set; }
        public double rating { get; set; }
        public Expertreview expertReview { get; set; }
        public string runLengthFormatted { get; set; }
        public string videoUrl1080P { get; set; }
        public object trailerTokenId { get; set; }
        public int picturesInSet { get; set; }
        public Carousel[] carousel { get; set; }
        public Images images { get; set; }
        public object[] tags { get; set; }
        public Downloadresolution[] downloadResolutions { get; set; }
        public Related[] related { get; set; }
        public object freeVideo { get; set; }
        public object[] userVideoReview { get; set; }
        public string __typename { get; set; }
    }

    public class Chapters
    {
        public string trailerThumbPattern { get; set; }
        public string videoThumbPattern { get; set; }
        public Video[] video { get; set; }
        public string __typename { get; set; }
    }

    public class Video
    {
        public string title { get; set; }
        public int seconds { get; set; }
        public string _id { get; set; }
        public string __typename { get; set; }
    }

    public class Tour
    {
        public int views { get; set; }
        public string __typename { get; set; }
    }

    public class Expertreview
    {
        public float global { get; set; }
        public Property1[] properties { get; set; }
        public Model[] models { get; set; }
        public string __typename { get; set; }
    }

    public class Property1
    {
        public string name { get; set; }
        public string slug { get; set; }
        public float rating { get; set; }
        public string __typename { get; set; }
    }

    public class Model
    {
        public string slug { get; set; }
        public float rating { get; set; }
        public string name { get; set; }
        public string __typename { get; set; }
    }

    public class Images
    {
        public Poster[] poster { get; set; }
        public string __typename { get; set; }
    }

    public class Poster
    {
        public string src { get; set; }
        public string placeholder { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public Highdpi highdpi { get; set; }
        public string __typename { get; set; }
    }

    public class Highdpi
    {
        public string _double { get; set; }
        public string triple { get; set; }
        public string __typename { get; set; }
    }

    public class Director
    {
        public string name { get; set; }
        public string __typename { get; set; }
    }

    public class Category
    {
        public string slug { get; set; }
        public string name { get; set; }
        public string __typename { get; set; }
    }

    public class Modelsslugged
    {
        public string name { get; set; }
        public string slugged { get; set; }
        public string __typename { get; set; }
    }

    public class Carousel
    {
        public Listing[] listing { get; set; }
        public Main[] main { get; set; }
        public string __typename { get; set; }
    }

    public class Listing
    {
        public string src { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string name { get; set; }
        public string __typename { get; set; }
    }

    public class Main
    {
        public string src { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string name { get; set; }
        public string __typename { get; set; }
    }

    public class Downloadresolution
    {
        public string label { get; set; }
        public string size { get; set; }
        public string width { get; set; }
        public string res { get; set; }
        public string __typename { get; set; }
    }

    public class Related
    {
        public string title { get; set; }
        public string uuid { get; set; }
        public string id { get; set; }
        public string slug { get; set; }
        public object absoluteUrl { get; set; }
        public string site { get; set; }
        public object freeVideo { get; set; }
        public Model1[] models { get; set; }
        public DateTime releaseDate { get; set; }
        public double rating { get; set; }
        public Expertreview1 expertReview { get; set; }
        public object channel { get; set; }
        public Images1 images { get; set; }
        public Previews previews { get; set; }
        public string __typename { get; set; }
    }

    public class Expertreview1
    {
        public float global { get; set; }
        public string __typename { get; set; }
    }

    public class Images1
    {
        public Listing1[] listing { get; set; }
        public string __typename { get; set; }
    }

    public class Listing1
    {
        public string src { get; set; }
        public string placeholder { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public Highdpi1 highdpi { get; set; }
        public string __typename { get; set; }
    }

    public class Highdpi1
    {
        public string _double { get; set; }
        public string triple { get; set; }
        public string __typename { get; set; }
    }

    public class Previews
    {
        public Listing2[] listing { get; set; }
        public string __typename { get; set; }
    }

    public class Listing2
    {
        public string src { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string type { get; set; }
        public string __typename { get; set; }
    }

    public class Model1
    {
        public object absoluteUrl { get; set; }
        public string name { get; set; }
        public string slug { get; set; }
        public string __typename { get; set; }
    }

}
