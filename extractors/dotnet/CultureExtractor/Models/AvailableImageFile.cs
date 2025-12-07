namespace CultureExtractor.Models;

public record AvailableImageFile(
        string FileType,
        string ContentType,
        string Variant,
        string Url,
        int? ResolutionWidth,
        int? ResolutionHeight,
        double? FileSize)
    : IAvailableFile;
