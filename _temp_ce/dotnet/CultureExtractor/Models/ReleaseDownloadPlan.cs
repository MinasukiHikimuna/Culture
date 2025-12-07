namespace CultureExtractor.Models;

public record ReleaseDownloadPlan(Release Release, IReadOnlyList<IAvailableFile> AvailableFiles);