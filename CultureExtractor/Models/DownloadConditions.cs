namespace CultureExtractor.Models;

public record DownloadConditions(
    DateRange DateRange,
    OrderEnum DownloadOrder,
    PreferredDownloadQuality PreferredDownloadQuality,
    int? MaxDownloads,
    IList<string>? PerformerNames,
    IList<string>? ReleaseUuids,
    IList<string>? DownloadedFileNames)
{
    public static DownloadConditions All(PreferredDownloadQuality preferredDownloadQuality) =>
        new(
            DateRange.All, 
            OrderEnum.Ascending,
            preferredDownloadQuality,
            null,
            null,
            null,
            null);
}