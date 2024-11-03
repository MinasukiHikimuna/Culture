using System.Text.Json.Serialization;

namespace CultureExtractor.Sites;

public class DigiGammaModels
{
    public class RootObject
    {
        public Results[] results { get; set; }
    }

    public class Results
    {
        public Hits[] hits { get; set; }
        public int nbHits { get; set; }
        public int page { get; set; }
        public int nbPages { get; set; }
        public int hitsPerPage { get; set; }
        public object facets { get; set; }
        public bool exhaustiveFacetsCount { get; set; }
        public bool exhaustiveNbHits { get; set; }
        public bool exhaustiveTypo { get; set; }
        public Exhaustive exhaustive { get; set; }
        public string query { get; set; }
        [JsonPropertyName("params")]
        public string parameters {
            get;
            set;
        }
        public string index { get; set; }
        public string queryID { get; set; }
        public int processingTimeMS { get; set; }
        public ProcessingTimingsMS processingTimingsMS { get; set; }
        public int serverTimeMS { get; set; }
        public bool exhaustiveFacetValues { get; set; }
    }

    public class Hits
    {
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
        public object vr_format { get; set; }
        public string category_ids { get; set; }
        public Directors[] directors { get; set; }
        public string network_name { get; set; }
        public string network_id { get; set; }
        public string original { get; set; }
        public string segment_site_id { get; set; }
        public int isVR { get; set; }
        public Video_formats[] video_formats { get; set; }
        public Scrubbers scrubbers { get; set; }
        public Dictionary<string, string> trailers { get; set; }
        public string url_title { get; set; }
        public string url_movie_title { get; set; }
        public string length_range_15min { get; set; }
        public string photoset_id { get; set; }
        public string photoset_name { get; set; }
        public string photoset_url_name { get; set; }
        public Network network { get; set; }
        public int date { get; set; }
        public Actors[] actors { get; set; }
        public Female_actors[] female_actors { get; set; }
        public Categories[] categories { get; set; }
        public string[] master_categories { get; set; }
        public object[] award_winning { get; set; }
        public int male { get; set; }
        public int female { get; set; }
        public int shemale { get; set; }
        public string[] pictures_qualifier { get; set; }
        public Pictures pictures { get; set; }
        public Dictionary<string, long> download_file_sizes { get; set; }
        public string[] download_sizes { get; set; }
        public string[] availableOnSite { get; set; }
        public string[] content_tags { get; set; }
        public int lesbian { get; set; }
        public int bisex { get; set; }
        public int trans { get; set; }
        public int hasSubtitle { get; set; }
        public int hasPpu { get; set; }
        public object rating_rank { get; set; }
        public int ratings_up { get; set; }
        public int ratings_down { get; set; }
        public int plays_365days { get; set; }
        public int plays_30days { get; set; }
        public int plays_7days { get; set; }
        public int plays_24hours { get; set; }
        public double engagement_score { get; set; }
        public int views { get; set; }
        public int single_site_views { get; set; }
        public string objectID { get; set; }
        public _highlightResult _highlightResult { get; set; }
        public string clip_4k_size { get; set; }
        public Channels[] channels { get; set; }
        public MainChannel mainChannel { get; set; }
        public string clip_1080p_size { get; set; }
    }

    public class Directors
    {
        public string name { get; set; }
        public string url_name { get; set; }
    }

    public class Video_formats
    {
        public string codec { get; set; }
        public string format { get; set; }
        public string size { get; set; }
        public string slug { get; set; }
        public string trailer_url { get; set; }
    }

    public class Scrubbers
    {
        public Full full { get; set; }
        public object trailer { get; set; }
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

    public class Actors
    {
        public string actor_id { get; set; }
        public string name { get; set; }
        public string gender { get; set; }
        public string url_name { get; set; }
    }

    public class Female_actors
    {
        public string actor_id { get; set; }
        public string name { get; set; }
        public string gender { get; set; }
        public string url_name { get; set; }
    }

    public class Categories
    {
        public string category_id { get; set; }
        public string name { get; set; }
        public string url_name { get; set; }
    }

    public class Pictures
    {
        public Nsfw nsfw { get; set; }
        public string _920x1080 { get; set; }
        public string resized { get; set; }
    }

    public class Nsfw
    {
        public Top top { get; set; }
    }

    public class Top
    {
        public string _920x1080 { get; set; }
    }

    public class _highlightResult
    {
        public Clip_id clip_id { get; set; }
        public Title title { get; set; }
        public Description description { get; set; }
        public Movie_id movie_id { get; set; }
        public Movie_title movie_title { get; set; }
        public Compilation compilation { get; set; }
        public Sitename sitename { get; set; }
        public Actors1[] actors { get; set; }
        public Categories1[] categories { get; set; }
        public Content_tags[] content_tags { get; set; }
        public Channels1[] channels { get; set; }
    }

    public class Clip_id
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

    public class Movie_id
    {
        public string value { get; set; }
        public string matchLevel { get; set; }
        public object[] matchedWords { get; set; }
    }

    public class Movie_title
    {
        public string value { get; set; }
        public string matchLevel { get; set; }
        public object[] matchedWords { get; set; }
    }

    public class Compilation
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

    public class Actors1
    {
        public Name name { get; set; }
    }

    public class Name
    {
        public string value { get; set; }
        public string matchLevel { get; set; }
        public object[] matchedWords { get; set; }
    }

    public class Categories1
    {
        public Name1 name { get; set; }
    }

    public class Name1
    {
        public string value { get; set; }
        public string matchLevel { get; set; }
        public object[] matchedWords { get; set; }
    }

    public class Content_tags
    {
        public string value { get; set; }
        public string matchLevel { get; set; }
        public object[] matchedWords { get; set; }
    }

    public class Channels1
    {
        public Id id { get; set; }
        public Name2 name { get; set; }
    }

    public class Id
    {
        public string value { get; set; }
        public string matchLevel { get; set; }
        public object[] matchedWords { get; set; }
    }

    public class Name2
    {
        public string value { get; set; }
        public string matchLevel { get; set; }
        public object[] matchedWords { get; set; }
    }

    public class Channels
    {
        public string id { get; set; }
        public string name { get; set; }
        public string type { get; set; }
    }

    public class MainChannel
    {
        public string id { get; set; }
        public string name { get; set; }
        public string type { get; set; }
    }

    public class Exhaustive
    {
        public bool facetsCount { get; set; }
        public bool nbHits { get; set; }
        public bool typo { get; set; }
        public bool facetValues { get; set; }
    }

    public class ProcessingTimingsMS
    {
        public _request _request { get; set; }
        public AfterFetch afterFetch { get; set; }
        public Fetch fetch { get; set; }
        public int total { get; set; }
    }

    public class _request
    {
        public int roundTrip { get; set; }
    }

    public class AfterFetch
    {
        public Format format { get; set; }
        public Merge merge { get; set; }
        public int total { get; set; }
    }

    public class Format
    {
        public int highlighting { get; set; }
        public int total { get; set; }
    }

    public class Merge
    {
        public int total { get; set; }
    }

    public class Fetch
    {
        public int facetingAfterDistinct { get; set; }
        public int scanning { get; set; }
        public int total { get; set; }
    }
}