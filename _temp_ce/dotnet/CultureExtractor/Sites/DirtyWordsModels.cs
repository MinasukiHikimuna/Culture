using System.Text.Json.Serialization;

namespace CultureExtractor.Sites;

public class DirtyWordsModels
{
    public class Rootobject
    {
        [JsonPropertyName("@context")]
        public string context { get; set; }
        [JsonPropertyName("@graph")]
        public Graph[] graph { get; set; }
    }

    public class Graph
    {
        [JsonPropertyName("@type")]
        public string type { get; set; }
        [JsonPropertyName("@id")]
        public string id { get; set; }
        public Itemlistelement[] itemListElement { get; set; }
        public string url { get; set; }
        public string name { get; set; }
        public string description { get; set; }
        public string inLanguage { get; set; }
        public Ispartof isPartOf { get; set; }
        public Breadcrumb breadcrumb { get; set; }
        public About about { get; set; }
        public Image image { get; set; }
        public Publisher publisher { get; set; }
        public Potentialaction potentialAction { get; set; }
    }

    public class Ispartof
    {
        public string id { get; set; }
    }

    public class Breadcrumb
    {
        public string id { get; set; }
    }

    public class About
    {
        public string id { get; set; }
    }

    public class Image
    {
        public string type { get; set; }
        public string id { get; set; }
        public string url { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string caption { get; set; }
    }

    public class Publisher
    {
        public string id { get; set; }
    }

    public class Potentialaction
    {
        public string type { get; set; }
        public Target target { get; set; }
        public string queryinput { get; set; }
    }

    public class Target
    {
        public string type { get; set; }
        public string urlTemplate { get; set; }
    }

    public class Itemlistelement
    {
        public string type { get; set; }
        public string id { get; set; }
        public int position { get; set; }
        public string name { get; set; }
    }
}
