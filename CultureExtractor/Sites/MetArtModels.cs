namespace CultureExtractor.Sites.MetArtIndexModels
{
    public class MetArtMovies
    {
        public Gallery[] galleries { get; set; }
        public int total { get; set; }
    }

    public class Gallery
    {
        public Model[] models { get; set; }
        public Photographer[] photographers { get; set; }
        public string[] tags { get; set; }
        public string[] relatedGalleries { get; set; }
        public string[] categories { get; set; }
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
        public bool isIntimateSelection { get; set; }
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

    public class Model
    {
        public string UUID { get; set; }
        public string name { get; set; }
        public string path { get; set; }
        public string globalUUID { get; set; }
    }

    public class Photographer
    {
        public string UUID { get; set; }
        public string name { get; set; }
        public string path { get; set; }
    }

    public class Crew
    {
        public string[] names { get; set; }
        public string role { get; set; }
    }
}

namespace CultureExtractor.Sites.MetArtSceneModels
{
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
        public int? publishAge { get; set; }
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
}
