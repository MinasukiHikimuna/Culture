using System.Text.Json.Serialization;

namespace CultureExtractor.Sites;

public class AyloMovieRequest
{
    public class RootObject
    {
        public AyloMoviesRequest.Meta meta { get; set; }
        public AyloMoviesRequest.Result result { get; set; }
    }
}

public class AyloMoviesRequest
{
    public class RootObject
    {
        public Meta meta { get; set; }
        public Result[] result { get; set; }
    }

    public class Meta
    {
        public int count { get; set; }
        public int total { get; set; }
    }

    public class Result
    {
        public string brand { get; set; }
        public BrandMeta brandMeta { get; set; }
        public int id { get; set; }
        public int spartanId { get; set; }
        public string type { get; set; }
        public string title { get; set; }
        public string dateReleased { get; set; }
        public string? description { get; set; }
        public Parent parent { get; set; }
        public int position { get; set; }
        public bool isVR { get; set; }
        public string sexualOrientation { get; set; }
        public string privacy { get; set; }
        public bool isDownloadable { get; set; }
        public Stats stats { get; set; }
        public Actors[] actors { get; set; }
        public Children[] children { get; set; }
        public Collections[] collections { get; set; }
        public Galleries[] galleries { get; set; }
        public Images images { get; set; }
        public Tags[] tags { get; set; }
        public TimeTags[] timeTags { get; set; }
        public Videos videos { get; set; }
        public Groups[] groups { get; set; }
        public bool isMemberUnlocked { get; set; }
        public bool isFreeScene { get; set; }
        public object[] customLists { get; set; }
        public object reaction { get; set; }
        public bool isUpcomingPlayable { get; set; }
        public bool isUpcoming { get; set; }
        public bool canPlay { get; set; }
        public bool isMicrotransactable { get; set; }
        public bool isPrimary { get; set; }
        public object bundleId { get; set; }
    }

    public class BrandMeta
    {
        public string shortName { get; set; }
        public string displayName { get; set; }
    }

    public class Parent
    {
        public string brand { get; set; }
        public BrandMeta1 brandMeta { get; set; }
        public int id { get; set; }
        public int spartanId { get; set; }
        public string type { get; set; }
        public string title { get; set; }
        public string dateReleased { get; set; }
        public string description { get; set; }
        public int position { get; set; }
        public bool isVR { get; set; }
        public string sexualOrientation { get; set; }
        public string privacy { get; set; }
        public bool isDownloadable { get; set; }
        public Stats1 stats { get; set; }
        public Actors1[] actors { get; set; }
        public Children1[] children { get; set; }
        public Collections1[] collections { get; set; }
        public object[] galleries { get; set; }
        public Images1 images { get; set; }
        public Tags1[] tags { get; set; }
        public object[] timeTags { get; set; }
        // This seems to cause deserialization issues and we have no need for this.
        // public object[] videos { get; set; }
        public Groups1[] groups { get; set; }
    }

    public class BrandMeta1
    {
        public string shortName { get; set; }
        public string displayName { get; set; }
    }

    public class Stats1
    {
        public int likes { get; set; }
        public int dislikes { get; set; }
        public int rating { get; set; }
        public double score { get; set; }
        public int downloads { get; set; }
        public int plays { get; set; }
        public int views { get; set; }
    }

    public class Actors1
    {
        public int id { get; set; }
        public string name { get; set; }
        public string gender { get; set; }
        public object[] imageMasters { get; set; }
        public object[] images { get; set; }
        public object[] tags { get; set; }
        public string customUrl { get; set; }
    }

    public class Children1
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
        public bool canPlay { get; set; }
    }

    public class Mediabook
    {
        public string type { get; set; }
        public int part { get; set; }
        public int length { get; set; }
        public Dictionary<string, AyloFile> files { get; set; }
    }

    public class AyloFile
    {
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls urls { get; set; }
        public string label { get; set; }
    }

    public class Urls
    {
        public string view { get; set; }
        public string download { get; set; }
    }

    public class Full
    {
        public string type { get; set; }
        public int part { get; set; }
        public int length { get; set; }
        public Dictionary<string, AyloFile> files { get; set; }
    }

    public class Collections1
    {
        public int id { get; set; }
        public string name { get; set; }
        public string shortName { get; set; }
        public object[] site { get; set; }
        public object[] imageMasters { get; set; }
        public object[] images { get; set; }
        public string customUrl { get; set; }
    }

    public class Images1
    {
        public Poster poster { get; set; }
        public Card_main_rect card_main_rect { get; set; }
    }

    public class Poster
    {
        public _ _ { get; set; }
        public string alternateText { get; set; }
        public int imageVersion { get; set; }
    }

    public class _
    {
        public Xs xs { get; set; }
        public Sm sm { get; set; }
        public Md md { get; set; }
        public Lg lg { get; set; }
        public Xl xl { get; set; }
        public Xx xx { get; set; }
    }

    public class Xs
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls6 urls { get; set; }
    }

    public class Urls6
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls7 urls { get; set; }
    }

    public class Urls7
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls8 urls { get; set; }
    }

    public class Urls8
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls9 urls { get; set; }
    }

    public class Urls9
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls10 urls { get; set; }
    }

    public class Urls10
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xx
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls urls { get; set; }
    }

    public class Card_main_rect
    {
        public _1 _ { get; set; }
        public string alternateText { get; set; }
        public int imageVersion { get; set; }
    }

    public class _1
    {
        public Xs1 xs { get; set; }
        public Sm1 sm { get; set; }
        public Md1 md { get; set; }
        public Lg1 lg { get; set; }
        public Xl1 xl { get; set; }
    }

    public class Xs1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls12 urls { get; set; }
    }

    public class Urls12
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls13 urls { get; set; }
    }

    public class Urls13
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls14 urls { get; set; }
    }

    public class Urls14
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls15 urls { get; set; }
    }

    public class Urls15
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls16 urls { get; set; }
    }

    public class Urls16
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Tags1
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

    public class Groups1
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

    public class Stats
    {
        public int likes { get; set; }
        public int dislikes { get; set; }
        public int rating { get; set; }
        public double score { get; set; }
        public int downloads { get; set; }
        public int plays { get; set; }
        public int views { get; set; }
    }

    public class Actors
    {
        public int id { get; set; }
        public string name { get; set; }
        public string gender { get; set; }
        public object[] imageMasters { get; set; }
        public object[] images { get; set; }
        public object[] tags { get; set; }
        public string customUrl { get; set; }
    }

    public class Children
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
        public bool canPlay { get; set; }
    }

    public class Collections
    {
        public int id { get; set; }
        public string name { get; set; }
        public string shortName { get; set; }
        public object[] site { get; set; }
        public object[] imageMasters { get; set; }
        public object[] images { get; set; }
        public string customUrl { get; set; }
    }

    public class Galleries
    {
        public int id { get; set; }
        public string type { get; set; }
        public string format { get; set; }
        public string directory { get; set; }
        public string filePattern { get; set; }
        public int filesCount { get; set; }
        public string multiCdnId { get; set; }
        public Urls17 urls { get; set; }
        public string url { get; set; }
    }

    public class Urls17
    {
        public string view { get; set; }
    }

    public class Images
    {
        public Poster1 poster { get; set; }
        public Card_main_rect1 card_main_rect { get; set; }
    }

    public class Poster1
    {
        [JsonPropertyName("0")]
        public PosterSizes _0 { get; set; }
        [JsonPropertyName("1")]
        public PosterSizes _1 { get; set; }
        [JsonPropertyName("2")]
        public PosterSizes _2 { get; set; }
        [JsonPropertyName("3")]
        public PosterSizes _3 { get; set; }
        [JsonPropertyName("4")]
        public PosterSizes _4 { get; set; }
        [JsonPropertyName("5")]
        public PosterSizes _5 { get; set; }
        public string alternateText { get; set; }
        public int imageVersion { get; set; }
    }

    public class PosterSizes
    {
        public PosterSize xs { get; set; }
        public PosterSize sm { get; set; }
        public PosterSize md { get; set; }
        public PosterSize lg { get; set; }
        public PosterSize xl { get; set; }
        public PosterSize xx { get; set; }
    }

    public class PosterSize
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public PosterUrls urls { get; set; }
    }

    public class PosterUrls
    {
        [JsonPropertyName("default")]
        public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls19 urls { get; set; }
    }

    public class Urls19
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls20 urls { get; set; }
    }

    public class Urls20
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls21 urls { get; set; }
    }

    public class Urls21
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls22 urls { get; set; }
    }

    public class Urls22
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xx1
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls23 urls { get; set; }
    }

    public class Urls23
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _3
    {
        public Xs3 xs { get; set; }
        public Sm3 sm { get; set; }
        public Md3 md { get; set; }
        public Lg3 lg { get; set; }
        public Xl3 xl { get; set; }
        public Xx2 xx { get; set; }
    }

    public class Xs3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls24 urls { get; set; }
    }

    public class Urls24
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls25 urls { get; set; }
    }

    public class Urls25
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls26 urls { get; set; }
    }

    public class Urls26
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls27 urls { get; set; }
    }

    public class Urls27
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls28 urls { get; set; }
    }

    public class Urls28
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xx2
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls29 urls { get; set; }
    }

    public class Urls29
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _4
    {
        public Xs4 xs { get; set; }
        public Sm4 sm { get; set; }
        public Md4 md { get; set; }
        public Lg4 lg { get; set; }
        public Xl4 xl { get; set; }
        public Xx3 xx { get; set; }
    }

    public class Xs4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls30 urls { get; set; }
    }

    public class Urls30
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls31 urls { get; set; }
    }

    public class Urls31
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls32 urls { get; set; }
    }

    public class Urls32
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls33 urls { get; set; }
    }

    public class Urls33
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls34 urls { get; set; }
    }

    public class Urls34
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xx3
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls35 urls { get; set; }
    }

    public class Urls35
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _5
    {
        public Xs5 xs { get; set; }
        public Sm5 sm { get; set; }
        public Md5 md { get; set; }
        public Lg5 lg { get; set; }
        public Xl5 xl { get; set; }
        public Xx4 xx { get; set; }
    }

    public class Xs5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls36 urls { get; set; }
    }

    public class Urls36
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls37 urls { get; set; }
    }

    public class Urls37
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls38 urls { get; set; }
    }

    public class Urls38
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls39 urls { get; set; }
    }

    public class Urls39
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls40 urls { get; set; }
    }

    public class Urls40
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xx4
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls41 urls { get; set; }
    }

    public class Urls41
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _6
    {
        public Xs6 xs { get; set; }
        public Sm6 sm { get; set; }
        public Md6 md { get; set; }
        public Lg6 lg { get; set; }
        public Xl6 xl { get; set; }
        public Xx5 xx { get; set; }
    }

    public class Xs6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls42 urls { get; set; }
    }

    public class Urls42
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls43 urls { get; set; }
    }

    public class Urls43
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls44 urls { get; set; }
    }

    public class Urls44
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls45 urls { get; set; }
    }

    public class Urls45
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls46 urls { get; set; }
    }

    public class Urls46
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xx5
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls47 urls { get; set; }
    }

    public class Urls47
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _7
    {
        public Xs7 xs { get; set; }
        public Sm7 sm { get; set; }
        public Md7 md { get; set; }
        public Lg7 lg { get; set; }
        public Xl7 xl { get; set; }
        public Xx6 xx { get; set; }
    }

    public class Xs7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls48 urls { get; set; }
    }

    public class Urls48
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls49 urls { get; set; }
    }

    public class Urls49
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls50 urls { get; set; }
    }

    public class Urls50
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls51 urls { get; set; }
    }

    public class Urls51
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl7
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls52 urls { get; set; }
    }

    public class Urls52
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xx6
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls53 urls { get; set; }
    }

    public class Urls53
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Card_main_rect1
    {
        [JsonPropertyName("0")]
        public _8 _0 { get; set; }
        [JsonPropertyName("1")]
        public _9 _1 { get; set; }
        [JsonPropertyName("2")]
        public _10 _2 { get; set; }
        [JsonPropertyName("3")]
        public _11 _3 { get; set; }
        [JsonPropertyName("4")]
        public _12 _4 { get; set; }
        [JsonPropertyName("5")]
        public _13 _5 { get; set; }
        public string alternateText { get; set; }
        public int imageVersion { get; set; }
    }

    public class _8
    {
        public Xs8 xs { get; set; }
        public Sm8 sm { get; set; }
        public Md8 md { get; set; }
        public Lg8 lg { get; set; }
        public Xl8 xl { get; set; }
    }

    public class Xs8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls54 urls { get; set; }
    }

    public class Urls54
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls55 urls { get; set; }
    }

    public class Urls55
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls56 urls { get; set; }
    }

    public class Urls56
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls57 urls { get; set; }
    }

    public class Urls57
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl8
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls58 urls { get; set; }
    }

    public class Urls58
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _9
    {
        public Xs9 xs { get; set; }
        public Sm9 sm { get; set; }
        public Md9 md { get; set; }
        public Lg9 lg { get; set; }
        public Xl9 xl { get; set; }
    }

    public class Xs9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls59 urls { get; set; }
    }

    public class Urls59
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls60 urls { get; set; }
    }

    public class Urls60
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls61 urls { get; set; }
    }

    public class Urls61
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls62 urls { get; set; }
    }

    public class Urls62
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl9
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls63 urls { get; set; }
    }

    public class Urls63
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _10
    {
        public Xs10 xs { get; set; }
        public Sm10 sm { get; set; }
        public Md10 md { get; set; }
        public Lg10 lg { get; set; }
        public Xl10 xl { get; set; }
    }

    public class Xs10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls64 urls { get; set; }
    }

    public class Urls64
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls65 urls { get; set; }
    }

    public class Urls65
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls66 urls { get; set; }
    }

    public class Urls66
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls67 urls { get; set; }
    }

    public class Urls67
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl10
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls68 urls { get; set; }
    }

    public class Urls68
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _11
    {
        public Xs11 xs { get; set; }
        public Sm11 sm { get; set; }
        public Md11 md { get; set; }
        public Lg11 lg { get; set; }
        public Xl11 xl { get; set; }
    }

    public class Xs11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls69 urls { get; set; }
    }

    public class Urls69
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls70 urls { get; set; }
    }

    public class Urls70
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls71 urls { get; set; }
    }

    public class Urls71
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls72 urls { get; set; }
    }

    public class Urls72
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl11
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls73 urls { get; set; }
    }

    public class Urls73
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _12
    {
        public Xs12 xs { get; set; }
        public Sm12 sm { get; set; }
        public Md12 md { get; set; }
        public Lg12 lg { get; set; }
        public Xl12 xl { get; set; }
    }

    public class Xs12
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls74 urls { get; set; }
    }

    public class Urls74
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm12
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls75 urls { get; set; }
    }

    public class Urls75
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md12
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls76 urls { get; set; }
    }

    public class Urls76
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg12
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls77 urls { get; set; }
    }

    public class Urls77
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl12
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls78 urls { get; set; }
    }

    public class Urls78
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class _13
    {
        public Xs13 xs { get; set; }
        public Sm13 sm { get; set; }
        public Md13 md { get; set; }
        public Lg13 lg { get; set; }
        public Xl13 xl { get; set; }
    }

    public class Xs13
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls79 urls { get; set; }
    }

    public class Urls79
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Sm13
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls80 urls { get; set; }
    }

    public class Urls80
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Md13
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls81 urls { get; set; }
    }

    public class Urls81
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Lg13
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls82 urls { get; set; }
    }

    public class Urls82
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Xl13
    {
        public int width { get; set; }
        public int height { get; set; }
        public string url { get; set; }
        public Urls83 urls { get; set; }
    }

    public class Urls83
    {
        [JsonPropertyName("default")] public string default1 { get; set; }
        public string webp { get; set; }
    }

    public class Tags
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

    public class TimeTags
    {
        public int id { get; set; }
        public string name { get; set; }
        public int startTime { get; set; }
        public int endTime { get; set; }
    }

    public class Videos
    {
        public Full full { get; set; }
        public Mediabook mediabook { get; set; }
    }

    public class _080p1
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls84 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls84
    {
        public string view { get; set; }
    }

    public class _20p4
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls85 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls85
    {
        public string view { get; set; }
    }

    public class _80p1
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls86 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls86
    {
        public string view { get; set; }
    }

    public class _20p5
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls87 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls87
    {
        public string view { get; set; }
    }

    public class Hls
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls88 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls88
    {
        public string view { get; set; }
    }

    public class Dash
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls89 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls89
    {
        public string view { get; set; }
    }

    public class _20p6
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls90 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls90
    {
        public string view { get; set; }
        public string download { get; set; }
    }

    public class _20p7
    {
        public int id { get; set; }
        public string format { get; set; }
        public string multiCdnId { get; set; }
        public long sizeBytes { get; set; }
        public string type { get; set; }
        public Urls91 urls { get; set; }
        public string label { get; set; }
    }

    public class Urls91
    {
        public string view { get; set; }
        public string download { get; set; }
    }

    public class Groups
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
}