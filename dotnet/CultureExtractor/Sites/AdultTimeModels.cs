using System.Text.Json.Serialization;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

public class AdultTimeModels
{
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
        IEnumerable<AvailableVideoFile> DownloadOptions,
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
        [JsonPropertyName("download_sizes")]
        public List<string> DownloadSizes { get; set; }
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
        [JsonConverter(typeof(StringOrNumberConverter))]
        public string Timecode { get; set; }
    }

    public enum AdultTimeRequestType
    {
        SceneMetadata
    }
}
