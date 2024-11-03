namespace CultureExtractor.Models;

public record AvailableGalleryZipFile(
        string FileType,
        string ContentType,
        string Variant,
        string Url,
        int? ResolutionWidth,
        int? ResolutionHeight,
        double? FileSize)
    : IAvailableFile;
