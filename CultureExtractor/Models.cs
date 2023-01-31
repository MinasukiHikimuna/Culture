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
    string ShortName,
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
    IEnumerable<SiteTag> Tags,
    IEnumerable<DownloadOption> DownloadOptions);

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
    PreferredDownloadQuality PreferredDownloadQuality,
    int? MaxDownloads,
    IList<string>? PerformerShortNames,
    IList<string>? SceneIds
)
{
    public static DownloadConditions All(PreferredDownloadQuality preferredDownloadQuality) => new(null, preferredDownloadQuality, null, null, null);
}

public record DateRange(
    DateOnly Start,
    DateOnly End);

public record Download(
    Scene Scene,
    string OriginalFilename,
    string SavedFilename,
    DownloadOption DownloadOption);

public record DownloadOption(
    string Description,
    int? ResolutionWidth,
    int? ResolutionHeight,
    double? FileSize,
    double? Fps,
    string? Codec,
    string Url);

public record DownloadDetailsAndElementHandle(
    DownloadOption DownloadOption,
    IElementHandle ElementHandle);

public enum PreferredDownloadQuality
{
    Best,
    Worst,
    Phash
}

public class PathsOptions
{
    public const string Paths = "Paths";

    public string MetadataPath { get; set; } = String.Empty;
    public string DownloadPath { get; set; } = String.Empty;
}
