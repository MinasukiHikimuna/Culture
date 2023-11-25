using System.Text.Json.Serialization;

namespace CultureExtractor.Sites;

public class VixenFindVideosOnSitesResponse
{
    public class RootObject
    {
        public Data data { get; set; }
    }

    public class Data
    {
        public FindVideosOnSites findVideosOnSites { get; set; }
    }

    public class FindVideosOnSites
    {
        public Edges[] edges { get; set; }
        public PageInfo pageInfo { get; set; }
        public int totalCount { get; set; }
        public string __typename { get; set; }
    }

    public class Edges
    {
        public Node node { get; set; }
        public string cursor { get; set; }
        public string __typename { get; set; }
    }

    public class Node
    {
        public string id { get; set; }
        public string videoId { get; set; }
        public string title { get; set; }
        public string slug { get; set; }
        public string site { get; set; }
        public double rating { get; set; }
        public ExpertReview expertReview { get; set; }
        public string releaseDate { get; set; }
        public object isExclusive { get; set; }
        public object freeVideo { get; set; }
        public object isFreeLimitedTrial { get; set; }
        public ModelsSlugged[] modelsSlugged { get; set; }
        public Previews previews { get; set; }
        public Images images { get; set; }
        public string __typename { get; set; }
    }

    public class ExpertReview
    {
        public double global { get; set; }
        public string __typename { get; set; }
    }

    public class ModelsSlugged
    {
        public string name { get; set; }
        public string slugged { get; set; }
        public string __typename { get; set; }
    }

    public class Previews
    {
        public Listing[] listing { get; set; }
        public string __typename { get; set; }
    }

    public class Listing
    {
        public string src { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string type { get; set; }
        public string __typename { get; set; }
    }

    public class Images
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
        public Highdpi highdpi { get; set; }
        public string __typename { get; set; }
    }

    public class Highdpi
    {
        [JsonPropertyName("double")]
        public string doubleDpi { get; set; }
        [JsonPropertyName("triple")]
        public string tripleDpi { get; set; }
        public string __typename { get; set; }
    }

    public class PageInfo
    {
        public bool hasNextPage { get; set; }
        public bool hasPreviousPage { get; set; }
        public string __typename { get; set; }
    }
}

public class VixenFindOneVideoResponse
{
    public class RootObject
    {
        public Data data { get; set; }
    }

    public class Data
    {
        public FindOneVideo findOneVideo { get; set; }
    }

    public class FindOneVideo
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
        public string releaseDate { get; set; }
        public string runLength { get; set; }
        public Directors[] directors { get; set; }
        public Categories[] categories { get; set; }
        public object channel { get; set; }
        public Chapters chapters { get; set; }
        public object showcase { get; set; }
        public Tour tour { get; set; }
        public ModelsSlugged[] modelsSlugged { get; set; }
        public double rating { get; set; }
        public ExpertReview expertReview { get; set; }
        public string runLengthFormatted { get; set; }
        public string videoUrl1080P { get; set; }
        public object trailerTokenId { get; set; }
        public int picturesInSet { get; set; }
        public Carousel[] carousel { get; set; }
        public Images images { get; set; }
        public object[] tags { get; set; }
        public DownloadResolutions[] downloadResolutions { get; set; }
        public Related[] related { get; set; }
        public object freeVideo { get; set; }
        public bool isFreeLimitedTrial { get; set; }
        public object[] userVideoReview { get; set; }
        public string __typename { get; set; }
    }

    public class Directors
    {
        public string name { get; set; }
        public string __typename { get; set; }
    }

    public class Categories
    {
        public string slug { get; set; }
        public string name { get; set; }
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

    public class ModelsSlugged
    {
        public string name { get; set; }
        public string slugged { get; set; }
        public string __typename { get; set; }
    }

    public class ExpertReview
    {
        public double global { get; set; }
        public Properties[] properties { get; set; }
        public Models[] models { get; set; }
        public string __typename { get; set; }
    }

    public class Properties
    {
        public string name { get; set; }
        public string slug { get; set; }
        public double rating { get; set; }
        public string __typename { get; set; }
    }

    public class Models
    {
        public string slug { get; set; }
        public double rating { get; set; }
        public string name { get; set; }
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
        [JsonPropertyName("double")]
        public string doubleDpi { get; set; }
        [JsonPropertyName("triple")]
        public string tripleDpi { get; set; }
        public string __typename { get; set; }
    }

    public class DownloadResolutions
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
        public bool isFreeLimitedTrial { get; set; }
        public Models1[] models { get; set; }
        public string releaseDate { get; set; }
        public double rating { get; set; }
        public ExpertReview1 expertReview { get; set; }
        public object channel { get; set; }
        public Images1 images { get; set; }
        public Previews previews { get; set; }
        public string __typename { get; set; }
    }

    public class Models1
    {
        public object absoluteUrl { get; set; }
        public string name { get; set; }
        public string slug { get; set; }
        public string __typename { get; set; }
    }

    public class ExpertReview1
    {
        public double global { get; set; }
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
        [JsonPropertyName("double")]
        public string doubleDpi { get; set; }
        [JsonPropertyName("triple")]
        public string tripleDpi { get; set; }
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
}

public class VixenGetTokenResponse
{
    public class RootObject
    {
        public Data data { get; set; }
    }

    public class Data
    {
        public GenerateVideoToken generateVideoToken { get; set; }
    }

    public class GenerateVideoToken
    {
        public VideoToken p270 { get; set; }
        public VideoToken p360 { get; set; }
        public VideoToken p480 { get; set; }
        public VideoToken p480l { get; set; }
        public VideoToken p720 { get; set; }
        public VideoToken p1080 { get; set; }
        public VideoToken p2160 { get; set; }
        public object hls { get; set; } // Set as object because it's null in the JSON example
        public string __typename { get; set; }
    }

    public class VideoToken
    {
        public string token { get; set; }
        public string cdn { get; set; }
        public string __typename { get; set; }
    }
}

public class VixenGetPictureSetResponse
{
    public class RootObject
    {
        public Data data { get; set; }
    }

    public class Data
    {
        public FindOnePictureSet findOnePictureSet { get; set; }
    }

    public class FindOnePictureSet
    {
        public string pictureSetId { get; set; }
        public string zip { get; set; }
        public Video video { get; set; }
        public Images[] images { get; set; }
        public string __typename { get; set; }
    }

    public class Video
    {
        public string id { get; set; }
        public string videoId { get; set; }
        public object freeVideo { get; set; }
        public bool isFreeLimitedTrial { get; set; }
        public string site { get; set; }
        public Categories[] categories { get; set; }
        public string __typename { get; set; }
    }

    public class Categories
    {
        public string slug { get; set; }
        public string name { get; set; }
        public string __typename { get; set; }
    }

    public class Images
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
        public string __typename { get; set; }
    }

    public class Main
    {
        public string src { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string __typename { get; set; }
    }
}