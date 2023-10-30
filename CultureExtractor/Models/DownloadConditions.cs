namespace CultureExtractor.Models;

public record DownloadConditions(
    DateRange? DateRange,
    PreferredDownloadQuality PreferredDownloadQuality,
    int? MaxDownloads,
    IList<string>? PerformerNames,
    IList<string>? SceneIds,
    IList<string>? DownloadedFileNames
)
{
    public static DownloadConditions All(PreferredDownloadQuality preferredDownloadQuality) => new(null, preferredDownloadQuality, null, null, null, null);
}