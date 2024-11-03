namespace CultureExtractor.Sites;

internal class Watch4BeautyModels
{
    internal class Updates
    {
        public class RootObject
        {
            public Latest[] latest { get; set; }
            public Popularity[] popularity { get; set; }
            public int offset { get; set; }
            public int pageSize { get; set; }
        }

        public class Latest
        {
            public int issue_id { get; set; }
            public int issue_category { get; set; }
            public DateTime issue_datetime { get; set; }
            public string issue_title { get; set; }
            public string issue_simple_title { get; set; }
            public int issue_size { get; set; }
            public string issue_text { get; set; }
            public float issue_rating { get; set; }
            public int issue_video_present { get; set; }
            public string issue_tags { get; set; }
            public int magazine_id { get; set; }
            public int magazine_category { get; set; }
            public DateTime magazine_datetime { get; set; }
            public string magazine_title { get; set; }
            public string magazine_simple_title { get; set; }
            public string magazine_text { get; set; }
            public float magazine_rating { get; set; }
            public string magazine_tags { get; set; }
            public int magazine_size { get; set; }
        }

        public class Popularity
        {
            public int issue_id { get; set; }
            public int issue_category { get; set; }
            public DateTime issue_datetime { get; set; }
            public string issue_title { get; set; }
            public string issue_simple_title { get; set; }
            public int issue_size { get; set; }
            public string issue_text { get; set; }
            public float issue_rating { get; set; }
            public int issue_video_present { get; set; }
            public string issue_tags { get; set; }
            public int magazine_id { get; set; }
            public int magazine_category { get; set; }
            public DateTime magazine_datetime { get; set; }
            public string magazine_title { get; set; }
            public string magazine_simple_title { get; set; }
            public string magazine_text { get; set; }
            public float magazine_rating { get; set; }
            public string magazine_tags { get; set; }
            public int magazine_size { get; set; }
        }


    }

    internal class Models
    {
        public class Issues
        {
            public int issue_id { get; set; }
            public List<Model> Models { get; set; }
        }

        public class Model
        {
            public int model_id { get; set; }
            public string model_nickname { get; set; }
            public string model_simple_nickname { get; set; }
            public bool widecover { get; set; }
        }
    }
}
