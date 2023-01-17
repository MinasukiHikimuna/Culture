using Microsoft.Playwright;

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
    string? PerformerShortName,
    PreferredDownloadQuality PreferredDownloadQuality
)
{
    public static DownloadConditions All(PreferredDownloadQuality preferredDownloadQuality) => new(null, null, preferredDownloadQuality);
    public static DownloadConditions Performer(string performerShortName, PreferredDownloadQuality preferredDownloadQuality) => new(null, performerShortName, preferredDownloadQuality);
}

public record DateRange(
    DateOnly Start,
    DateOnly End);

public record Download(
    string OriginalFilename,
    string SavedFilename,
    DownloadDetails DownloadDetails);

public record DownloadDetails(
    string Description,
    int? ResolutionHeight,
    int? ResolutionWidth,
    double? FileSize,
    double? Fps,
    string? Url,
    string? Codec);

public enum PreferredDownloadQuality
{
    Best,
    Worst,
    Phash
}
