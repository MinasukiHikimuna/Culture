using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

public record AdultTimeSceneDocument(
    Guid Id,
    string Network,
    string Site,
    DateOnly ReleaseDate,
    string ShortName,
    string Name,
    string Url,
    string Description,
    TimeSpan Duration,
    IEnumerable<SitePerformer> Performers,
    IEnumerable<Director> Directors,
    IEnumerable<SiteTag> Tags,
    IEnumerable<DownloadOption> DownloadOptions,
    IEnumerable<ActionTag> Markers);

public class Rootobject
{
    public Result[] results { get; set; }
}

public class Result
{
    public AdultTimeScene[] hits { get; set; }
    public int nbHits { get; set; }
    public int page { get; set; }
    public int nbPages { get; set; }
    public int hitsPerPage { get; set; }
    public bool exhaustiveNbHits { get; set; }
    public bool exhaustiveTypo { get; set; }
    public Exhaustive exhaustive { get; set; }
    public string query { get; set; }
    public string _params { get; set; }
    public string index { get; set; }
    public string queryID { get; set; }
    public int processingTimeMS { get; set; }
    public Processingtimingsms processingTimingsMS { get; set; }
    public int serverTimeMS { get; set; }
    public Facets facets { get; set; }
    public Facets_Stats facets_stats { get; set; }
    public bool exhaustiveFacetsCount { get; set; }
    public bool exhaustiveFacetValues { get; set; }
}

public class Exhaustive
{
    public bool nbHits { get; set; }
    public bool typo { get; set; }
    public bool facetsCount { get; set; }
    public bool facetValues { get; set; }
}

public class Processingtimingsms
{
    public Request request { get; set; }
    public Afterfetch afterFetch { get; set; }
    public Fetch fetch { get; set; }
    public int total { get; set; }
}

public class Request
{
    public int roundTrip { get; set; }
}

public class Afterfetch
{
    public int dedupFacets { get; set; }
    public Merge merge { get; set; }
    public int total { get; set; }
}

public class Merge
{
    public int distinct { get; set; }
}

public class Fetch
{
    public int distinct { get; set; }
    public int faceting { get; set; }
    public int scanning { get; set; }
    public int total { get; set; }
}

public class Facets
{
    public Clip_Id clip_id { get; set; }
}

public class Clip_Id
{
    public int _120046 { get; set; }
    public int _120239 { get; set; }
    public int _120240 { get; set; }
    public int _120241 { get; set; }
    public int _12397 { get; set; }
    public int _125634 { get; set; }
    public int _12755 { get; set; }
    public int _132626 { get; set; }
    public int _134541 { get; set; }
    public int _134874 { get; set; }
    public int _144926 { get; set; }
    public int _15945 { get; set; }
    public int _169380 { get; set; }
    public int _197332 { get; set; }
    public int _20173 { get; set; }
    public int _20191 { get; set; }
    public int _31926 { get; set; }
    public int _32094 { get; set; }
    public int _40871 { get; set; }
    public int _41004 { get; set; }
    public int _41124 { get; set; }
    public int _41143 { get; set; }
    public int _41147 { get; set; }
    public int _42961 { get; set; }
    public int _42962 { get; set; }
    public int _42963 { get; set; }
    public int _42964 { get; set; }
    public int _48950 { get; set; }
    public int _49923 { get; set; }
    public int _60887 { get; set; }
    public int _67013 { get; set; }
    public int _67800 { get; set; }
    public int _67870 { get; set; }
    public int _67871 { get; set; }
    public int _71097 { get; set; }
    public int _71120 { get; set; }
    public int _71600 { get; set; }
    public int _71601 { get; set; }
    public int _71602 { get; set; }
    public int _73212 { get; set; }
    public int _10196 { get; set; }
    public int _1145 { get; set; }
    public int _1146 { get; set; }
    public int _1148 { get; set; }
    public int _11596 { get; set; }
    public int _11599 { get; set; }
    public int _1160 { get; set; }
    public int _11601 { get; set; }
    public int _11608 { get; set; }
    public int _1161 { get; set; }
    public int _11610 { get; set; }
    public int _1164 { get; set; }
    public int _1167 { get; set; }
    public int _1168 { get; set; }
    public int _11715 { get; set; }
    public int _11730 { get; set; }
    public int _11816 { get; set; }
    public int _118794 { get; set; }
    public int _118795 { get; set; }
    public int _118796 { get; set; }
    public int _118797 { get; set; }
    public int _11893 { get; set; }
    public int _1191 { get; set; }
    public int _119496 { get; set; }
    public int _119497 { get; set; }
    public int _119498 { get; set; }
    public int _119499 { get; set; }
    public int _1199 { get; set; }
    public int _120043 { get; set; }
    public int _120044 { get; set; }
    public int _120045 { get; set; }
    public int _1201 { get; set; }
    public int _120238 { get; set; }
    public int _1207 { get; set; }
    public int _1208 { get; set; }
    public int _120855 { get; set; }
    public int _120866 { get; set; }
    public int _120867 { get; set; }
    public int _120868 { get; set; }
    public int _120869 { get; set; }
    public int _121056 { get; set; }
    public int _121057 { get; set; }
    public int _121058 { get; set; }
    public int _121059 { get; set; }
    public int _1213 { get; set; }
    public int _1217 { get; set; }
    public int _1218 { get; set; }
    public int _1219 { get; set; }
    public int _1220 { get; set; }
    public int _1221 { get; set; }
    public int _122351 { get; set; }
    public int _123163 { get; set; }
    public int _123318 { get; set; }
    public int _123319 { get; set; }
    public int _123320 { get; set; }
    public int _123453 { get; set; }
    public int _12398 { get; set; }
    public int _12399 { get; set; }
    public int _12400 { get; set; }
    public int _124085 { get; set; }
}

public class Facets_Stats
{
    public Clip_Id1 clip_id { get; set; }
}

public class Clip_Id1
{
    public int min { get; set; }
    public int max { get; set; }
    public int avg { get; set; }
    public long sum { get; set; }
}

public class AdultTimeScene
{
    // Selected properties
    [JsonPropertyName("action_tags")]
    public ActionTag[] ActionTags { get; set; }
    [JsonPropertyName("directors")]
    public Director[] Directors { get; set; }
    [JsonPropertyName("trailers")]
    public Dictionary<string, string> Trailers { get; set; }
    [JsonPropertyName("download_file_sizes")]
    public Dictionary<string, long> DownloadFileSizes { get; set; }
    [JsonPropertyName("actors")]
    public Actor[] Actors { get; set; }

    // Generated properties
    public object subtitle_id { get; set; }
    public int clip_id { get; set; }
    public string title { get; set; }
    public string description { get; set; }
    public string clip_type { get; set; }
    public string clip_length { get; set; }
    public string clip_path { get; set; }
    public int source_clip_id { get; set; }
    public int length { get; set; }
    public string release_date { get; set; }
    public int upcoming { get; set; }
    public int movie_id { get; set; }
    public string movie_title { get; set; }
    public string movie_desc { get; set; }
    public string movie_date_created { get; set; }
    public string compilation { get; set; }
    public int site_id { get; set; }
    public string sitename { get; set; }
    public string sitename_pretty { get; set; }
    public string segment { get; set; }
    public int serie_id { get; set; }
    public string serie_name { get; set; }
    public int studio_id { get; set; }
    public string studio_name { get; set; }
    public string category_ids { get; set; }
    public string network_name { get; set; }
    public string network_id { get; set; }
    public string original { get; set; }
    public string segment_site_id { get; set; }
    public string url_title { get; set; }
    public string url_movie_title { get; set; }
    public string length_range_15min { get; set; }
    public string photoset_id { get; set; }
    public string photoset_name { get; set; }
    public string photoset_url_name { get; set; }
    public Network network { get; set; }
    public int date { get; set; }
    public Female_Actors[] female_actors { get; set; }
    public Category1[] categories { get; set; }
    public string[] master_categories { get; set; }
    public object[] award_winning { get; set; }
    public int male { get; set; }
    public int female { get; set; }
    public int shemale { get; set; }
    public string[] pictures_qualifier { get; set; }
    public Pictures pictures { get; set; }
    public string[] download_sizes { get; set; }
    public string[] availableOnSite { get; set; }
    public string[] content_tags { get; set; }
    public int lesbian { get; set; }
    public int bisex { get; set; }
    public int trans { get; set; }
    public int hasSubtitle { get; set; }
    public int hasPpu { get; set; }
    public Channel1[] channels { get; set; }
    public Mainchannel mainChannel { get; set; }
    public object rating_rank { get; set; }
    public int ratings_up { get; set; }
    public int ratings_down { get; set; }
    public int plays_365days { get; set; }
    public int plays_30days { get; set; }
    public int plays_7days { get; set; }
    public int plays_24hours { get; set; }
    public float engagement_score { get; set; }
    public int network_priority { get; set; }
    public Subtitles subtitles { get; set; }
    public int views { get; set; }
    public int single_site_views { get; set; }
    public string objectID { get; set; }
    public _Highlightresult _highlightResult { get; set; }
}

public class Scrubbers
{
    public Full full { get; set; }
    public object[] trailer { get; set; }
}

public class Full
{
    public string url { get; set; }
    public string thumbWidth { get; set; }
    public string thumbHeight { get; set; }
}

public class Network
{
    public string lvl0 { get; set; }
    public string lvl1 { get; set; }
}

public class Pictures
{
    public string _185x135 { get; set; }
    public Sfw sfw { get; set; }
    public Nsfw nsfw { get; set; }
    public string _1920x1080 { get; set; }
    public string _201x147 { get; set; }
    public string _307x224 { get; set; }
    public string _406x296 { get; set; }
    public string _638x360 { get; set; }
    public string _76x55 { get; set; }
    public string _960x544 { get; set; }
    public string resized { get; set; }
}

public class Sfw
{
    public Top top { get; set; }
}

public class Top
{
    public string _1920x1080 { get; set; }
}

public class Nsfw
{
    public Top1 top { get; set; }
}

public class Top1
{
    public string _1920x1080 { get; set; }
}

public class Download_File_Sizes
{
    [JsonPropertyName("160p")]
    public int _160p { get; set; }
    [JsonPropertyName("240p")]
    public int _240p { get; set; }
    public int _360p { get; set; }
    public int _480p { get; set; }
    public int _540p { get; set; }
    public int _720p { get; set; }
    public int _1080p { get; set; }
    public long _4k { get; set; }
}

public class Mainchannel
{
    public string id { get; set; }
    public string name { get; set; }
    public string type { get; set; }
}

public class Subtitles
{
    public Full1 full { get; set; }
    public Trailer trailer { get; set; }
    public string[] languages { get; set; }
}

public class Full1
{
    public string deauto { get; set; }
    public string en { get; set; }
    public string esauto { get; set; }
    public string frauto { get; set; }
    public string itauto { get; set; }
    public string nlauto { get; set; }
    public string ptauto { get; set; }
}

public class Trailer
{
    public string deauto { get; set; }
    public string en { get; set; }
    public string esauto { get; set; }
    public string frauto { get; set; }
    public string itauto { get; set; }
    public string nlauto { get; set; }
    public string ptauto { get; set; }
}

public class _Highlightresult
{
    public Clip_Id2 clip_id { get; set; }
    public Title title { get; set; }
    public Description description { get; set; }
    public Movie_Title movie_title { get; set; }
    public Sitename sitename { get; set; }
    public ActorHiglight[] actors { get; set; }
    public Category[] categories { get; set; }
    public Availableonsite[] availableOnSite { get; set; }
    public Content_Tags[] content_tags { get; set; }
    public Channel[] channels { get; set; }
}

public class Clip_Id2
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Title
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Description
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Movie_Title
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Sitename
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class ActorHiglight
{
    public Name name { get; set; }
}

public class Name
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Category
{
    public Name1 name { get; set; }
}

public class Name1
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Availableonsite
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Content_Tags
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Channel
{
    public Name2 name { get; set; }
}

public class Name2
{
    public string value { get; set; }
    public string matchLevel { get; set; }
    public object[] matchedWords { get; set; }
}

public class Director
{
    public string name { get; set; }
    public string url_name { get; set; }
}

public class Actor
{
    public string actor_id { get; set; }
    public string name { get; set; }
    public string gender { get; set; }
    public string url_name { get; set; }
}

public class Female_Actors
{
    public string actor_id { get; set; }
    public string name { get; set; }
    public string gender { get; set; }
    public string url_name { get; set; }
}

public class Category1
{
    public string category_id { get; set; }
    public string name { get; set; }
    public string url_name { get; set; }
}

public class Channel1
{
    public string id { get; set; }
    public string name { get; set; }
    public string type { get; set; }
}

public class ActionTag
{
    [JsonPropertyName("name")]
    public string Name { get; set; }
    [JsonPropertyName("timecode")]
    public string Timecode { get; set; }
}

public enum AdultTimeRequestType {
    SceneMetadata
}

[PornNetwork("adulttime")]
[PornSite("adulttime")]
public class AdultTimeRipper : ISceneScraper, ISceneDownloader
{
    private readonly IDownloader _downloader;

    public AdultTimeRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var usernameInput = page.GetByPlaceholder("Username or Email");
        if (await usernameInput.IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username or Email").ClickAsync();
            await page.GetByPlaceholder("Username or Email").FillAsync(site.Username);

            await page.GetByPlaceholder("password").ClickAsync();
            await page.GetByPlaceholder("password").FillAsync(site.Password);

            // TODO: let's see if we need to manually enable this at all
            // await page.GetByText("Remember me").ClickAsync();

            await page.GetByRole(AriaRole.Button, new() { NameString = "Click here to login" }).ClickAsync();

            await page.WaitForLoadStateAsync();
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = "Videos" }).ClickAsync();
        await page.WaitForLoadStateAsync();

        await page.Locator("div.FilterPanelItem-Categories a").Filter(new() { HasTextString = "Adult Time Original" }).ClickAsync();
        await page.WaitForLoadStateAsync();

        var totalCount = await page.Locator("span.SearchListing-ResultCount-Text").TextContentAsync();
        Log.Information(totalCount);

        var lastPage = await page.Locator("a.Pagination-Page-Link:not(.Pagination-RightControl-Link)").Last.TextContentAsync();
        return int.Parse(lastPage);
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var url = await scenePage.GetAttributeAsync("img.ScenePlayerHeaderPlus-PosterImage", "src");

        string pattern = @"(width=)\d+";
        string replacement = "${1}1920";
        string output = Regex.Replace(url, pattern, replacement);

        pattern = @"(format=)\w+";
        replacement = "${1}jpg";
        output = Regex.Replace(output, pattern, replacement);

        await _downloader.DownloadSceneImageAsync(scene, output, scene.Url);
    }

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var currentScenes = await page.Locator("div.ListingGrid-ListingGridItem").ElementHandlesAsync();
        return currentScenes;
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var thumbLinkElement = await currentScene.QuerySelectorAsync("a");
        var url = await thumbLinkElement.GetAttributeAsync("href");
        var id = url.Substring(url.LastIndexOf("/") + 1);
        return (url, id);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.Locator("a.Pagination-RightControl-Link").ClickAsync();
    }

    public async Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response)
    {
        if (response.Url.Contains("algolia.net"))
        {
            var bodyBuffer = await response.BodyAsync();
            var body = System.Text.Encoding.UTF8.GetString(bodyBuffer);

            if (body.Contains("facets=clip_id") && body.Contains("clip_id%3A" + sceneShortName))
            {
                return new CapturedResponse(Enum.GetName(AdultTimeRequestType.SceneMetadata)!, response);
            }
        }

        return null;
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
    {
        var sceneMetadataResponse = responses.First(r => r.Name == Enum.GetName(AdultTimeRequestType.SceneMetadata));

        var body = await sceneMetadataResponse.Response.BodyAsync();
        var foo = System.Text.Encoding.UTF8.GetString(body);

        var data = System.Text.Json.JsonSerializer.Deserialize<Rootobject>(foo)!;


        var sceneData = data.results[0].hits[0];


        var releaseDate = DateOnly.Parse(sceneData.release_date);
        var duration = TimeSpan.FromSeconds(sceneData.length);
        var title = sceneData.title;

        var performers = new List<SitePerformer>();
        foreach (var performer in sceneData.Actors)
        {
            var shortName = $"{performer.url_name}/{performer.actor_id}";
            var performerUrl = $"/en/pornstar/view/{shortName}";
            var name = performer.name;
            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        var tags = new List<SiteTag>();
        foreach (var tag in sceneData.categories)
        {
            var shortName = tag.category_id;
            var name = tag.name;
            tags.Add(new SiteTag(shortName, name, string.Empty));
        }

        string description = sceneData.description.Replace("</br>", Environment.NewLine);
        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(sceneData);

        var sceneDocument = new AdultTimeSceneDocument(
            Guid.NewGuid(),
            site.Name,
            sceneData.mainChannel.name,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration,
            performers,
            sceneData.Directors,
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            sceneData.ActionTags != null ? sceneData.ActionTags : new List<ActionTag>());

        Scene scene = new Scene(
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
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            JsonSerializer.Serialize(sceneDocument)
        );

        if (sceneData.subtitles != null)
        {
            var subtitleFilename = SceneNamer.Name(scene, ".vtt");
            await _downloader.DownloadSceneSubtitlesAsync(scene, subtitleFilename, "https://subtitles.gammacdn.com/" + sceneData.subtitles.full.en, page.Url);
        }

        return scene;
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IList<CapturedResponse> responses)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var sceneMetadataResponse = responses.First(r => r.Name == Enum.GetName(AdultTimeRequestType.SceneMetadata));

        var body = await sceneMetadataResponse.Response.BodyAsync();
        var foo = System.Text.Encoding.UTF8.GetString(body);

        var data = System.Text.Json.JsonSerializer.Deserialize<Rootobject>(foo)!;


        var sceneData = data.results[0].hits[0];

        var availableDownloads = await ParseAvailableDownloadsAsync(sceneData);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        IPage newPage = await page.Context.NewPageAsync();

        // TODO: does download but Playwright won't detect when it finishes
        var download = await _downloader.DownloadSceneAsync(scene, newPage, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            try
            {
                await newPage.GotoAsync(selectedDownload.DownloadOption.Url);
            }
            catch (PlaywrightException ex)
            {
                if (ex.Message.StartsWith("net::ERR_ABORTED"))
                {
                    // Ok. Thrown for some reason every time a file is downloaded using browser.
                }
                else
                {
                    throw;
                }
            }
        });

        await newPage.CloseAsync();

        return download;
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(AdultTimeScene sceneData)
    {
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();

        foreach (var downloadFileSize in sceneData.DownloadFileSizes.Keys)
        {
            var description = downloadFileSize;
            var resolutionHeight = HumanParser.ParseResolutionHeight(downloadFileSize);

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                new DownloadOption(
                    description,
                    -1,
                    HumanParser.ParseResolutionHeight(downloadFileSize),
                    sceneData.DownloadFileSizes[downloadFileSize],
                    -1,
                    HumanParser.ParseCodec("H.264"),
                    $"/movieaction/download/{sceneData.clip_id}/{downloadFileSize}/mp4"),
                null));
        }

        return availableDownloads.OrderByDescending(d => d.DownloadOption.FileSize).ToList();
    }
}
