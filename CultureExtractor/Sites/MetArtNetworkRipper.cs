using Microsoft.Playwright;
using CultureExtractor.Interfaces;
using CultureExtractor.Exceptions;
using System.Text.Json;
using System.Net.Http.Json;
using CultureExtractor.Sites.MetArt;

namespace CultureExtractor.Sites;

public class MetArtSceneData
{
    public Model[] models { get; set; }
    public Photographer[] photographers { get; set; }
    public string[] tags { get; set; }
    public string[] relatedGalleries { get; set; }
    public MetArtCategory[] categories { get; set; }
    public Crew[] crew { get; set; }
    public string UUID { get; set; }
    public string name { get; set; }
    public string description { get; set; }
    public string path { get; set; }
    public string coverImagePath { get; set; }
    public string thumbnailCoverPath { get; set; }
    public string type { get; set; }
    public string siteUUID { get; set; }
    public bool isPublic { get; set; }
    public DateTime createdAt { get; set; }
    public DateTime publishedAt { get; set; }
    public float ratingAverage { get; set; }
    public int favoriteCount { get; set; }
    public int ratingCount { get; set; }
    public int views { get; set; }
    public Ranks ranks { get; set; }
    public Leaderboardviews leaderboardViews { get; set; }
    public string coverCleanImagePath { get; set; }
    public string zipFile { get; set; }
    public string splashImagePath { get; set; }
    public bool isStaffSelection { get; set; }
    public int imageCount { get; set; }
    public int runtime { get; set; }
    public string permalink { get; set; }
    public string metaDescription { get; set; }
    public string metaTitle { get; set; }
    public bool hasCleanCover { get; set; }
    public bool hasCover { get; set; }
    public bool isPrivate { get; set; }
    public bool downloadsDisabled { get; set; }
    public bool hasPermissions { get; set; }
    public bool isIntimateSelection { get; set; }
    public Comments comments { get; set; }
    public Files files { get; set; }
    public object[] globalContent { get; set; }
    public Media media { get; set; }
    public Photos photos { get; set; }
    public Relatedgallery relatedGallery { get; set; }
    public object[] relatedMovies { get; set; }
}

public class Ranks
{
    public int day { get; set; }
    public int week { get; set; }
    public int month { get; set; }
    public int year { get; set; }
    public string siteUUID { get; set; }
}

public class Leaderboardviews
{
    public int day { get; set; }
    public int week { get; set; }
    public int month { get; set; }
    public int year { get; set; }
    public string siteUUID { get; set; }
}

public class Comments
{
    public int total { get; set; }
    public object[] comments { get; set; }
}

public class Files
{
    public object[] teasers { get; set; }
    public Sizes sizes { get; set; }
}

public class Sizes
{
    public Relatedphoto[] relatedPhotos { get; set; }
    public Video[] videos { get; set; }
    public Zip[] zips { get; set; }
}

public class Relatedphoto
{
    public string id { get; set; }
    public string size { get; set; }
}

public class Video
{
    public string id { get; set; }
    public string size { get; set; }
}

public class Zip
{
    public string fileName { get; set; }
    public string quality { get; set; }
    public string size { get; set; }
}

public class Media
{
    public string[] relatedGalleries { get; set; }
    public string UUID { get; set; }
    public string siteUUID { get; set; }
    public string galleryUUID { get; set; }
    public string rating { get; set; }
    public int ratingCount { get; set; }
    public int views { get; set; }
    public int displayOrder { get; set; }
    public string resolution { get; set; }
    public int runtime { get; set; }
}

public class Photos
{
    public Medium[] media { get; set; }
    public int total { get; set; }
}

public class Medium
{
    public string[] relatedGalleries { get; set; }
    public string UUID { get; set; }
    public string siteUUID { get; set; }
    public string galleryUUID { get; set; }
    public string rating { get; set; }
    public int ratingCount { get; set; }
    public int views { get; set; }
    public int displayOrder { get; set; }
    public string resolution { get; set; }
    public int runtime { get; set; }
}

public class Relatedgallery
{
    public Medium1[] media { get; set; }
    public int total { get; set; }
}

public class Medium1
{
    public string[] relatedGalleries { get; set; }
    public string UUID { get; set; }
    public string siteUUID { get; set; }
    public string galleryUUID { get; set; }
    public string rating { get; set; }
    public int ratingCount { get; set; }
    public int views { get; set; }
    public int displayOrder { get; set; }
    public string resolution { get; set; }
    public int runtime { get; set; }
}

public class Model
{
    public int age { get; set; }
    public string breasts { get; set; }
    public Comments1 comments { get; set; }
    public Country country { get; set; }
    public string ethnicity { get; set; }
    public string eyes { get; set; }
    public int publishAge { get; set; }
    public int galleriesCount { get; set; }
    public string gender { get; set; }
    public string hair { get; set; }
    public string headshotImagePath { get; set; }
    public int height { get; set; }
    public int moviesCount { get; set; }
    public string name { get; set; }
    public string path { get; set; }
    public string pubicHair { get; set; }
    public Ranks1 ranks { get; set; }
    public string siteUUID { get; set; }
    public string size { get; set; }
    public object[] tags { get; set; }
    public string UUID { get; set; }
    public int weight { get; set; }
    public int ratingCount { get; set; }
    public int favoriteCount { get; set; }
    public float ratingAverage { get; set; }
    public int views { get; set; }
    public bool downloadsDisabled { get; set; }
}

public class Comments1
{
    public int total { get; set; }
    public object[] comments { get; set; }
}

public class Country
{
    public string UUID { get; set; }
    public string name { get; set; }
    public string isoCode3 { get; set; }
}

public class Ranks1
{
    public int day { get; set; }
    public int week { get; set; }
    public int month { get; set; }
    public int year { get; set; }
    public string siteUUID { get; set; }
}

public class Photographer
{
    public Comments2 comments { get; set; }
    public string coverImagePath { get; set; }
    public string coverSiteUUID { get; set; }
    public string coverCleanImagePath { get; set; }
    public int galleriesCount { get; set; }
    public int moviesCount { get; set; }
    public string name { get; set; }
    public string path { get; set; }
    public string siteUUID { get; set; }
    public string[] tags { get; set; }
    public string thumbnailCoverPath { get; set; }
    public string UUID { get; set; }
    public bool isPublic { get; set; }
    public int favoriteCount { get; set; }
    public int ratingCount { get; set; }
    public int views { get; set; }
    public object[] ranks { get; set; }
    public object[] leaderboardViews { get; set; }
    public float ratingAverage { get; set; }
}

public class Comments2
{
    public int total { get; set; }
    public object[] comments { get; set; }
}

public class MetArtCategory
{
    public string name { get; set; }
    public string UUID { get; set; }
    public bool isRelated { get; set; }
}

public class Crew
{
    public string[] names { get; set; }
    public string role { get; set; }
}


[PornNetwork("metart")]
[PornSite("metart")]
[PornSite("metartx")]
[PornSite("sexart")]
[PornSite("vivthomas")]
[PornSite("thelifeerotic")]
[PornSite("eternaldesire")]
[PornSite("straplez")]
[PornSite("hustler")]
public class MetArtNetworkRipper : ISiteScraper
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

            var modalClose = page.Locator("div.modal-content a.alt-close");
            if (await modalClose.IsVisibleAsync())
            {
                await modalClose.ClickAsync();
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

    public string IndexRequestFilterPath => "**/api/movies*";
    public Func<IRequest, bool> IndexRequestFilterPredicate => (IRequest request) => true;

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var response = await requests[0].ResponseAsync();
        var content = await response.TextAsync();
        var data = JsonSerializer.Deserialize<MetArtMovies>(content);

        var currentPage = page.Url.Substring(page.Url.LastIndexOf("/") + 1);
        var skipAdScene = currentPage == "1" && site.ShortName != "hustler";

        return data.galleries.Skip(skipAdScene ? 1 : 0)
            .Select(g => new IndexScene(null, g.path.Substring(g.path.LastIndexOf("/movie/") + "/movie/".Length + 1), g.path, null))
            .Reverse()
            .ToList()
            .AsReadOnly();
    }

    public async Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var url = await currentScene.GetAttributeAsync("href");
        var sceneShortName = url.Substring(url.LastIndexOf("/movie/") + "/movie/".Length + 1);
        return new SceneIdAndUrl(sceneShortName, url);
    }

    public async Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response)
    {
        if (response.Url.Contains("/api/movie?name="))
        {
            return new CapturedResponse(Enum.GetName(AdultTimeRequestType.SceneMetadata)!, response);
        }

        return null;
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
    {
        if (!responses.Any())
        {
            throw new Exception("Could not read API response.");
        }

        var sceneMetadataResponse = responses[0];
        var body = await sceneMetadataResponse.Response.BodyAsync();
        var jsonContent = System.Text.Encoding.UTF8.GetString(body);
        var data = JsonSerializer.Deserialize<MetArtSceneData>(jsonContent)!;

        var releaseDate = data.publishedAt;
        var duration = TimeSpan.FromSeconds(data.runtime);
        var description = data.description;
        var name = data.name;

        
        var performers = data.models.Where(a => a.gender == "female").ToList()
            .Concat(data.models.Where(a => a.gender != "female").ToList())
            .Select(m => new SitePerformer(m.path.Substring(m.path.LastIndexOf("/") + 1), m.name, m.path))
            .ToList();

        var tags = data.tags
            .Select(t => new SiteTag(t.Replace(" ", "+"), t, "/tags/" + t.Replace(" ", "+")))
            .ToList();

        var downloads = data.files.sizes.videos
            .Select(d => new DownloadOption(d.id, -1, HumanParser.ParseResolutionHeight(d.id), HumanParser.ParseFileSize(d.size), -1, string.Empty, $"/api/download-media/{data.siteUUID}/film/{d.id}"))
            .OrderByDescending(d => d.ResolutionHeight)
            .ToList();

        // var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
            null,
            site,
            null,
            DateOnly.FromDateTime(releaseDate),
            sceneShortName,
            name,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloads,
            jsonContent
        );
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var data = JsonSerializer.Deserialize<MetArtSceneData>(scene.JsonDocument)!;
        await _downloader.DownloadSceneImageAsync(scene, scene.Site.Url + data.splashImagePath);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = ">" }).ClickAsync();
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IList<CapturedResponse> responses)
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

    public async Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/movies/{pageNumber}");
    }
}
