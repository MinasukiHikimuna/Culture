namespace CultureExtractor.Models;

public record Release(
    Guid Uuid,
    Site Site,
    SubSite? SubSite,
    DateOnly ReleaseDate,
    string ShortName,
    string Name,
    string Url,
    string Description,
    double Duration,
    IEnumerable<SitePerformer> Performers,
    IEnumerable<SiteTag> Tags,
    IEnumerable<IAvailableFile> DownloadOptions,
    string JsonDocument,
    DateTime LastUpdated);
