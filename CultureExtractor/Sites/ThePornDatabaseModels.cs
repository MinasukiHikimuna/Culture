namespace CultureExtractor.Sites;

public class ThePornDatabaseSitesResponse
{
    public record RootObject(
        Data[] data,
        Links links,
        Meta meta
    );

    public record Data(
        string uuid,
        int id,
        object parent_id,
        int network_id,
        string name,
        string short_name,
        string url,
        string description,
        int rating,
        string logo,
        string favicon,
        string poster,
        Network network,
        object parent
    );

    public record Network(
        string uuid,
        int id,
        string name,
        string short_name
    );

    public record Links(
        string first,
        string last,
        object prev,
        object next
    );

    public record Meta(
        int current_page,
        int from,
        int last_page,
        Links1[] links,
        string path,
        int per_page,
        int to,
        int total
    );

    public record Links1(
        string url,
        string label,
        bool active
    );
}

public class ThePornDatabaseScenesResponse
{
    public record RootObject(
        Data[] data,
        Links links,
        Meta meta
    );

    public record Data(
        string id,
        int _id,
        string title,
        string type,
        string slug,
        string external_id,
        string description,
        int site_id,
        string date,
        string url,
        string image,
        string poster,
        string trailer,
        int duration,
        object format,
        object sku,
        Posters posters,
        Background background,
        string created,
        string last_updated,
        Performers[] performers,
        Site site,
        Tags[] tags,
        Hashes[] hashes
    );

    public record Posters(
        string large,
        string medium,
        string small
    );

    public record Background(
        string full,
        string large,
        string medium,
        string small
    );

    public record Performers(
        string id,
        int _id,
        string slug,
        int site_id,
        string name,
        object bio,
        bool is_parent,
        Extra extra,
        string image,
        string thumbnail,
        string face,
        Parent parent
    );

    public record Extra(
        string astrology,
        string birthday,
        string birthplace,
        string cupsize,
        string ethnicity,
        object eye_colour,
        bool? fakeboobs,
        string gender,
        string haircolor,
        string height,
        string measurements,
        string nationality,
        string piercings,
        string tattoos,
        string weight
    );

    public record Parent(
        string id,
        int _id,
        string slug,
        string name,
        string bio,
        bool is_parent,
        Extras extras,
        string image,
        string thumbnail,
        string face,
        Posters1[] posters
    );

    public record Extras(
        string gender,
        string birthday,
        int? birthday_timestamp,
        string birthplace,
        string birthplace_code,
        string astrology,
        string ethnicity,
        string nationality,
        string hair_colour,
        string weight,
        string height,
        string measurements,
        string cupsize,
        string tattoos,
        string piercings,
        string waist,
        string hips
    );

    public record Posters1(
        int id,
        string url,
        int size,
        int order
    );

    public record Site(
        string uuid,
        int id,
        object parent_id,
        int network_id,
        string name,
        string short_name,
        object url,
        string description,
        int rating,
        string logo,
        Network network,
        object parent
    );

    public record Network(
        string uuid,
        int id,
        string name,
        string short_name
    );

    public record Tags(
        int id,
        string name
    );

    public record Hashes(
        bool can_delete,
        string created_at,
        int duration,
        string hash,
        int id,
        int scene_id,
        int submissions,
        string type,
        string updated_at,
        string[] users
    );

    public record Links(
        string first,
        string last,
        object prev,
        string next
    );

    public record Meta(
        int current_page,
        int from,
        int last_page,
        Links1[] links,
        string path,
        int per_page,
        int to,
        int total
    );

    public record Links1(
        string url,
        string label,
        bool active
    );
}