using System.Text.Json.Serialization;

// ReSharper disable InconsistentNaming
// ReSharper disable ClassNeverInstantiated.Global

namespace CultureExtractor.Sites;

public class VixenFindVideosOnSitesResponse
{
    public class RootObject
    {
        public Data data { get; init; }
    }

    public class Data
    {
        public FindVideosOnSites findVideosOnSites { get; init; }
    }

    public class FindVideosOnSites
    {
        public Edges[] edges { get; init; }
        public PageInfo pageInfo { get; init; }
        public int totalCount { get; init; }
        public string __typename { get; init; }
    }

    public class Edges
    {
        public Node node { get; init; }
        public string cursor { get; init; }
        public string __typename { get; init; }
    }

    public class Node
    {
        public string id { get; init; }
        public string videoId { get; init; }
        public string title { get; init; }
        public string slug { get; init; }
        public string site { get; init; }
        public double? rating { get; init; }
        public ExpertReview expertReview { get; init; }
        public string releaseDate { get; init; }
        public object isExclusive { get; init; }
        public object freeVideo { get; init; }
        public object isFreeLimitedTrial { get; init; }
        public ModelsSlugged[] modelsSlugged { get; init; }
        public Previews previews { get; init; }
        public Images images { get; init; }
        public string __typename { get; init; }
    }

    public class ExpertReview
    {
        public double global { get; init; }
        public string __typename { get; init; }
    }

    public class ModelsSlugged
    {
        public string name { get; init; }
        public string slugged { get; init; }
        public string __typename { get; init; }
    }

    public class Previews
    {
        public Listing[] listing { get; init; }
        public string __typename { get; init; }
    }

    public class Listing
    {
        public string src { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public string type { get; init; }
        public string __typename { get; init; }
    }

    public class Images
    {
        public Listing1[] listing { get; init; }
        public string __typename { get; init; }
    }

    public class Listing1
    {
        public string src { get; init; }
        public string placeholder { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public Highdpi highdpi { get; init; }
        public string __typename { get; init; }
    }

    public class Highdpi
    {
        [JsonPropertyName("double")]
        public string doubleDpi { get; init; }
        [JsonPropertyName("triple")]
        public string tripleDpi { get; init; }
        public string __typename { get; init; }
    }

    public class PageInfo
    {
        public bool hasNextPage { get; init; }
        public bool hasPreviousPage { get; init; }
        public string __typename { get; init; }
    }
}

public class VixenFindOneVideoResponse
{
    public class RootObject
    {
        public Data data { get; init; }
    }

    public class Data
    {
        public FindOneVideo findOneVideo { get; init; }
    }

    public class FindOneVideo
    {
        public string id { get; init; }
        public string videoId { get; init; }
        public string newId { get; init; }
        public string uuid { get; init; }
        public string slug { get; init; }
        public string site { get; init; }
        public string title { get; init; }
        public string description { get; init; }
        public string descriptionHtml { get; init; }
        public object absoluteUrl { get; init; }
        public bool denied { get; init; }
        public bool isUpcoming { get; init; }
        public string releaseDate { get; init; }
        public string runLength { get; init; }
        public Directors[] directors { get; init; }
        public Categories[] categories { get; init; }
        public object channel { get; init; }
        public Chapters chapters { get; init; }
        public object showcase { get; init; }
        public Tour tour { get; init; }
        public ModelsSlugged[] modelsSlugged { get; init; }
        public double? rating { get; init; }
        public ExpertReview expertReview { get; init; }
        public string runLengthFormatted { get; init; }
        public string videoUrl1080P { get; init; }
        public object trailerTokenId { get; init; }
        public int picturesInSet { get; init; }
        public Carousel[] carousel { get; init; }
        public Images images { get; init; }
        public object[] tags { get; init; }
        public DownloadResolutions[] downloadResolutions { get; init; }
        public Related[] related { get; init; }
        public object freeVideo { get; init; }
        public bool isFreeLimitedTrial { get; init; }
        public object[] userVideoReview { get; init; }
        public string __typename { get; init; }
    }

    public class Directors
    {
        public string name { get; init; }
        public string __typename { get; init; }
    }

    public class Categories
    {
        public string slug { get; init; }
        public string name { get; init; }
        public string __typename { get; init; }
    }

    public class Chapters
    {
        public string trailerThumbPattern { get; init; }
        public string videoThumbPattern { get; init; }
        public Video[] video { get; init; }
        public string __typename { get; init; }
    }

    public class Video
    {
        public string title { get; init; }
        public int seconds { get; init; }
        public string _id { get; init; }
        public string __typename { get; init; }
    }

    public class Tour
    {
        public int views { get; init; }
        public string __typename { get; init; }
    }

    public class ModelsSlugged
    {
        public string name { get; init; }
        public string slugged { get; init; }
        public string __typename { get; init; }
    }

    public class ExpertReview
    {
        public double global { get; init; }
        public Properties[] properties { get; init; }
        public Models[] models { get; init; }
        public string __typename { get; init; }
    }

    public class Properties
    {
        public string name { get; init; }
        public string slug { get; init; }
        public double? rating { get; init; }
        public string __typename { get; init; }
    }

    public class Models
    {
        public string slug { get; init; }
        public double? rating { get; init; }
        public string name { get; init; }
        public string __typename { get; init; }
    }

    public class Carousel
    {
        public Listing[] listing { get; init; }
        public Main[] main { get; init; }
        public string __typename { get; init; }
    }

    public class Listing
    {
        public string src { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public string name { get; init; }
        public string __typename { get; init; }
    }

    public class Main
    {
        public string src { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public string name { get; init; }
        public string __typename { get; init; }
    }

    public class Images
    {
        public Poster[] poster { get; init; }
        public string __typename { get; init; }
    }

    public class Poster
    {
        public string src { get; init; }
        public string placeholder { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public Highdpi highdpi { get; init; }
        public string __typename { get; init; }
    }

    public class Highdpi
    {
        [JsonPropertyName("double")]
        public string doubleDpi { get; init; }
        [JsonPropertyName("triple")]
        public string tripleDpi { get; init; }
        public string __typename { get; init; }
    }

    public class DownloadResolutions
    {
        public string label { get; init; }
        public string size { get; init; }
        public string width { get; init; }
        public string res { get; init; }
        public string __typename { get; init; }
    }

    public class Related
    {
        public string title { get; init; }
        public string uuid { get; init; }
        public string id { get; init; }
        public string slug { get; init; }
        public object absoluteUrl { get; init; }
        public string site { get; init; }
        public object freeVideo { get; init; }
        public bool isFreeLimitedTrial { get; init; }
        public Models1[] models { get; init; }
        public string releaseDate { get; init; }
        public double? rating { get; init; }
        public ExpertReview1 expertReview { get; init; }
        public object channel { get; init; }
        public Images1 images { get; init; }
        public Previews previews { get; init; }
        public string __typename { get; init; }
    }

    public class Models1
    {
        public object absoluteUrl { get; init; }
        public string name { get; init; }
        public string slug { get; init; }
        public string __typename { get; init; }
    }

    public class ExpertReview1
    {
        public double global { get; init; }
        public string __typename { get; init; }
    }

    public class Images1
    {
        public Listing1[] listing { get; init; }
        public string __typename { get; init; }
    }

    public class Listing1
    {
        public string src { get; init; }
        public string placeholder { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public Highdpi1 highdpi { get; init; }
        public string __typename { get; init; }
    }

    public class Highdpi1
    {
        [JsonPropertyName("double")]
        public string doubleDpi { get; init; }
        [JsonPropertyName("triple")]
        public string tripleDpi { get; init; }
        public string __typename { get; init; }
    }

    public class Previews
    {
        public Listing2[] listing { get; init; }
        public string __typename { get; init; }
    }

    public class Listing2
    {
        public string src { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public string type { get; init; }
        public string __typename { get; init; }
    }
}

public class VixenGetTokenResponse
{
    public class RootObject
    {
        public Data data { get; init; }
    }

    public class Data
    {
        public GenerateVideoToken generateVideoToken { get; init; }
    }

    public class GenerateVideoToken
    {
        public VideoToken? p270 { get; init; }
        public VideoToken? p360 { get; init; }
        public VideoToken? p480 { get; init; }
        public VideoToken? p480l { get; init; }
        public VideoToken? p720 { get; init; }
        public VideoToken? p1080 { get; init; }
        public VideoToken? p2160 { get; init; }
        public object hls { get; init; } // Set as object because it's null in the JSON example
        public string __typename { get; init; }
    }

    public class VideoToken
    {
        public string token { get; init; }
        public string cdn { get; init; }
        public string __typename { get; init; }
    }
}

public class VixenGetPictureSetResponse
{
    public class RootObject
    {
        public Data data { get; init; }
    }

    public class Data
    {
        public FindOnePictureSet findOnePictureSet { get; init; }
    }

    public class FindOnePictureSet
    {
        public string pictureSetId { get; init; }
        public string zip { get; init; }
        public Video video { get; init; }
        public Images[] images { get; init; }
        public string __typename { get; init; }
    }

    public class Video
    {
        public string id { get; init; }
        public string videoId { get; init; }
        public object freeVideo { get; init; }
        public bool isFreeLimitedTrial { get; init; }
        public string site { get; init; }
        public Categories[] categories { get; init; }
        public string __typename { get; init; }
    }

    public class Categories
    {
        public string slug { get; init; }
        public string name { get; init; }
        public string __typename { get; init; }
    }

    public class Images
    {
        public Listing[] listing { get; init; }
        public Main[] main { get; init; }
        public string __typename { get; init; }
    }

    public class Listing
    {
        public string src { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public string __typename { get; init; }
    }

    public class Main
    {
        public string src { get; init; }
        public int width { get; init; }
        public int height { get; init; }
        public string __typename { get; init; }
    }
}

public class VixenGetSearchResultsResponse
{
    public class RootObject
    {
        public Data data { get; set; }
    }

    public class Data
    {
        public object[] searchCategories { get; set; }
        public object[] searchModels { get; set; }
        public Searchvideos searchVideos { get; set; }
    }

    public class Searchvideos
    {
        public int totalCount { get; set; }
        public Edge[] edges { get; set; }
        public string __typename { get; set; }
    }

    public class Edge
    {
        public Node node { get; set; }
        public string __typename { get; set; }
    }

    public class Node
    {
        public string id { get; set; }
        public string videoId { get; set; }
        public string title { get; set; }
        public string slug { get; set; }
        public Expertreview expertReview { get; set; }
        public DateTime releaseDate { get; set; }
        public object isExclusive { get; set; }
        public object freeVideo { get; set; }
        public string site { get; set; }
        public string description { get; set; }
        public bool isFreeLimitedTrial { get; set; }
        public Modelsslugged[] modelsSlugged { get; set; }
        public Images images { get; set; }
        public Previews previews { get; set; }
        public object channel { get; set; }
        public string __typename { get; set; }
    }

    public class Expertreview
    {
        public float global { get; set; }
        public string __typename { get; set; }
    }

    public class Images
    {
        public Listing[] listing { get; set; }
        public string __typename { get; set; }
    }

    public class Listing
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

    public class Previews
    {
        public Listing1[] listing { get; set; }
        public string __typename { get; set; }
    }

    public class Listing1
    {
        public string src { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string type { get; set; }
        public string __typename { get; set; }
    }

    public class Modelsslugged
    {
        public string name { get; set; }
        public string slugged { get; set; }
        public string __typename { get; set; }
    }
}