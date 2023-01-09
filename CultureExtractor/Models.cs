namespace CultureExtractor;

public record Site(
    int Id,
    string ShortName,
    string Name,
    string Url,
    string Username,
    string Password,
    string StorageState);

public record SitePerformer(
    string Id,
    string Name,
    string Url);

public record SiteTag(
    string Id,
    string Name,
    string Url);

public record Scene(
    int? Id,
    Site Site,
    DateOnly ReleaseDate,
    string ShortName,
    string Name,
    string Url,
    string Description,
    double Duration,
    IEnumerable<SitePerformer> Performers,
    IEnumerable<SiteTag> Tags);

public record Gallery(
    int? Id,
    Site Site,
    DateOnly ReleaseDate,
    string ShortName,
    string Name,
    string Url,
    string Description,
    int Pictures,
    IEnumerable<SitePerformer> Performers,
    IEnumerable<SiteTag> Tags);

public record DownloadConditions(
    DateRange? DateRange,
    string? PerformerShortName
)
{
    public static DownloadConditions All() => new(null, null);
    public static DownloadConditions Performer(string performerShortName) => new(null, performerShortName);
}

public record DateRange(
    DateOnly Start,
    DateOnly End);
