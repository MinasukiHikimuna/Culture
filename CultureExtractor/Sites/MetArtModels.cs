namespace CultureExtractor.Sites.MetArt;

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
