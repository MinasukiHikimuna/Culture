using System.Text.Json.Serialization;

namespace CultureExtractor.Sites;

public class MetArtMoviesRequest
{
    public record RootObject(
        Galleries[] galleries,
        int total
    );

    public record Galleries(
        Models[] models,
        Photographers[] photographers,
        string[] tags,
        string[] relatedGalleries,
        object[] categories,
        Crew[] crew,
        string UUID,
        string name,
        string description,
        string path,
        string coverImagePath,
        string thumbnailCoverPath,
        string type,
        string siteUUID,
        bool isPublic,
        string createdAt,
        DateTime publishedAt,
        double ratingAverage,
        int favoriteCount,
        int ratingCount,
        int views,
        Ranks ranks,
        LeaderboardViews leaderboardViews,
        string coverCleanImagePath,
        string zipFile,
        string splashImagePath,
        bool isStaffSelection,
        int imageCount,
        int runtime,
        string permalink,
        string metaDescription,
        string metaTitle,
        bool hasCleanCover,
        bool hasCover,
        bool isPrivate,
        bool downloadsDisabled,
        bool isIntimateSelection
    );

    public record Models(
        string UUID,
        string name,
        string path,
        string globalUUID
    );

    public record Photographers(
        string UUID,
        string name,
        string path
    );

    public record Crew(
        string[] names,
        string role
    );

    public record Ranks(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );

    public record LeaderboardViews(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );
}

public class MetArtMovieRequest
{
    public record RootObject(
        Models[] models,
        Photographers[] photographers,
        string[] tags,
        string[] relatedGalleries,
        object[] categories,
        Crew[] crew,
        string UUID,
        string name,
        string description,
        string path,
        string coverImagePath,
        string thumbnailCoverPath,
        string type,
        string siteUUID,
        bool isPublic,
        string createdAt,
        DateTime publishedAt,
        double ratingAverage,
        int favoriteCount,
        int ratingCount,
        int views,
        Ranks ranks,
        LeaderboardViews leaderboardViews,
        string coverCleanImagePath,
        string zipFile,
        string splashImagePath,
        bool isStaffSelection,
        int imageCount,
        int runtime,
        string permalink,
        string metaDescription,
        string metaTitle,
        bool hasCleanCover,
        bool hasCover,
        bool isPrivate,
        bool downloadsDisabled,
        bool hasPermissions,
        bool isIntimateSelection,
        Comments comments,
        Files files,
        GlobalContent[] globalContent,
        Media media,
        Photos photos,
        RelatedGallery relatedGallery
    );

    public record Models(
        int age,
        string breasts,
        Comments1 comments,
        Country country,
        string ethnicity,
        string eyes,
        int publishAge,
        int galleriesCount,
        string gender,
        string hair,
        string headshotImagePath,
        int height,
        int moviesCount,
        string name,
        string path,
        string pubicHair,
        Ranks1 ranks,
        string siteUUID,
        string size,
        object[] tags,
        string UUID,
        int weight,
        int ratingCount,
        int favoriteCount,
        double ratingAverage,
        int views,
        bool downloadsDisabled
    );

    public record Comments1(
        int total,
        object[] comments
    );

    public record Country(
        string UUID,
        string name,
        string isoCode3
    );

    public record Ranks1(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );

    public record Photographers(
        Comments2 comments,
        string coverImagePath,
        string coverSiteUUID,
        string coverCleanImagePath,
        int galleriesCount,
        int moviesCount,
        string name,
        string path,
        string siteUUID,
        string[] tags,
        string thumbnailCoverPath,
        string UUID,
        bool isPublic,
        int favoriteCount,
        int ratingCount,
        int views,
        object[] ranks,
        object[] leaderboardViews,
        double ratingAverage
    );

    public record Comments2(
        int total,
        object[] comments
    );

    public record Crew(
        string[] names,
        string role
    );

    public record Ranks(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );

    public record LeaderboardViews(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );

    public record Comments(
        int total,
        object[] comments
    );

    public record Files(
        string[] teasers,
        Sizes sizes
    );

    public record Sizes(
        RelatedPhotos[] relatedPhotos,
        Videos[] videos,
        Zips[] zips
    );

    public record RelatedPhotos(
        string id,
        string size
    );

    public record Videos(
        string id,
        string size
    );

    public record Zips(
        string fileName,
        string quality,
        string size
    );

    public record GlobalContent(
        string coverCleanImagePath,
        string coverImagePath,
        Models1[] models,
        string name,
        string path,
        DateTime publishedAt,
        string siteUUID,
        string thumbnailCoverPath,
        string type,
        string UUID
    );

    public record Models1(
        string UUID,
        string name,
        string path,
        string globalUUID
    );

    public record Media(
        string[] relatedGalleries,
        string UUID,
        string siteUUID,
        string galleryUUID,
        string rating,
        int ratingCount,
        int views,
        int displayOrder,
        string resolution,
        int runtime
    );

    public record Photos(
        Media1[] media,
        int total
    );

    public record Media1(
        string[] relatedGalleries,
        string UUID,
        string siteUUID,
        string galleryUUID,
        string rating,
        int ratingCount,
        int views,
        int displayOrder,
        string resolution,
        int runtime
    );

    public record RelatedGallery(
        Media2[] media,
        int total
    );

    public record Media2(
        string[] relatedGalleries,
        string UUID,
        string siteUUID,
        string galleryUUID,
        string rating,
        int ratingCount,
        int views,
        int displayOrder,
        string resolution,
        int runtime
    );
}

public class MetArtGalleriesRequest
{
    public record RootObject(
        Galleries[] galleries,
        int total
    );

    public record Galleries(
        Models[] models,
        Photographers[] photographers,
        string[] tags,
        object[] relatedGalleries,
        object[] categories,
        object[] crew,
        string UUID,
        string name,
        string description,
        string path,
        string coverImagePath,
        string thumbnailCoverPath,
        string type,
        string siteUUID,
        bool isPublic,
        string createdAt,
        DateTime publishedAt,
        double ratingAverage,
        int favoriteCount,
        int ratingCount,
        int views,
        Ranks ranks,
        LeaderboardViews leaderboardViews,
        string coverCleanImagePath,
        string zipFile,
        string splashImagePath,
        bool isStaffSelection,
        int imageCount,
        int runtime,
        string permalink,
        string metaDescription,
        string metaTitle,
        bool hasCleanCover,
        bool hasCover,
        bool isPrivate,
        bool downloadsDisabled,
        bool isIntimateSelection
    );

    public record Models(
        string UUID,
        string name,
        string path,
        string globalUUID
    );

    public record Photographers(
        string UUID,
        string name,
        string path
    );

    public record Ranks(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );

    public record LeaderboardViews(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );
}

public class MetArtGalleryRequest
{
    public record RootObject(
        string coverImagePath,
        string coverCleanImagePath,
        Comments comments,
        string description,
        string metaDescription,
        string metaTitle,
        GlobalContent[] globalContent,
        Models[] models,
        string name,
        string path,
        Photographers[] photographers,
        Photos photos,
        DateTime publishedAt,
        Ranks ranks,
        string siteUUID,
        string[] tags,
        string type,
        string thumbnailCoverPath,
        string UUID,
        string originalUUID,
        bool hasPermissions,
        int favoriteCount,
        double ratingAverage,
        int ratingCount,
        int views,
        bool downloadsDisabled,
        PreviousGallery previousGallery,
        Files files
    );

    public record Comments(
        int total,
        object[] comments
    );

    public record GlobalContent(
        string coverCleanImagePath,
        string coverImagePath,
        string name,
        string path,
        string siteUUID,
        string thumbnailCoverPath,
        string UUID
    );

    public record Models(
        int age,
        string breasts,
        Comments1 comments,
        Country country,
        string ethnicity,
        string eyes,
        int publishAge,
        int galleriesCount,
        string gender,
        string hair,
        string headshotImagePath,
        int height,
        int moviesCount,
        string name,
        string path,
        string pubicHair,
        Ranks1 ranks,
        int ratingCount,
        string siteUUID,
        string size,
        object[] tags,
        string UUID,
        int weight,
        int favoriteCount,
        double ratingAverage,
        int views,
        bool downloadsDisabled
    );

    public record Comments1(
        int total,
        object[] comments
    );

    public record Country(
        string UUID,
        string name,
        string isoCode3
    );

    public record Ranks1(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );

    public record Photographers(
        Comments2 comments,
        string coverImagePath,
        string coverCleanImagePath,
        int galleriesCount,
        int moviesCount,
        string name,
        string path,
        string siteUUID,
        string[] tags,
        string thumbnailCoverPath,
        string UUID,
        int favoriteCount,
        double ratingAverage,
        int ratingCount,
        int views
    );

    public record Comments2(
        int total,
        object[] comments
    );

    public record Photos(
        Media[] media,
        int total,
        int megapixels
    );

    public record Media(
        object[] relatedGalleries,
        string UUID,
        string siteUUID,
        string galleryUUID,
        string rating,
        int ratingCount,
        int views,
        int displayOrder,
        string resolution,
        int runtime,
        ImgPath imgPath
    );

    public record ImgPath(
        string low,
        string medium,
        string high
    );

    public record Ranks(
        int day,
        int week,
        int month,
        int year,
        string siteUUID
    );

    public record PreviousGallery(
        string UUID,
        Models1[] models,
        string path,
        string name,
        string thumbnailCoverPath,
        string coverCleanImagePath,
        string siteUUID
    );

    public record Models1(
        string UUID,
        string name,
        string path,
        string globalUUID
    );

    public record Files(
        object[] teasers,
        Sizes sizes
    );

    public record Sizes(
        RelatedPhotos[] relatedPhotos,
        object[] videos,
        Zips[] zips
    );

    public record RelatedPhotos(
        string id,
        string size
    );

    public record Zips(
        string fileName,
        string quality,
        string size
    );
}

public class MetArtCommentsRequest
{
    public record RootObject(
        int total,
        Comments[] comments
    );

    public class Comments
    {
        public Comments(bool isEdited,
            string parentUUID,
            string siteUUID,
            string text,
            string timestamp,
            string userDisplayName,
            string UUID,
            string networkUserUUID,
            bool isSilenced,
            bool visible,
            object badges,
            MetArtObject metArtObject,
            int rating)
        {
            this.isEdited = isEdited;
            this.parentUUID = parentUUID;
            this.siteUUID = siteUUID;
            this.text = text;
            this.timestamp = timestamp;
            this.userDisplayName = userDisplayName;
            this.UUID = UUID;
            this.networkUserUUID = networkUserUUID;
            this.isSilenced = isSilenced;
            this.visible = visible;
            this.badges = badges;
            this.metArtObject = metArtObject;
            this.rating = rating;
        }

        public bool isEdited { get; init; }
        public string parentUUID { get; init; }
        public string siteUUID { get; init; }
        public string text { get; init; }
        public string timestamp { get; init; }
        public string userDisplayName { get; init; }
        public string UUID { get; init; }
        public string networkUserUUID { get; init; }
        public bool isSilenced { get; init; }
        public bool visible { get; init; }
        public object badges { get; init; }
        [JsonPropertyName("object")]
        public MetArtObject metArtObject { get; init; }
        public int rating { get; init; }
    }

    public record MetArtObject(
        string name,
        string path
    );
}
