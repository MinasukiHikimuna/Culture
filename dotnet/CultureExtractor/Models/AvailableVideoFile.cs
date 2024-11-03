namespace CultureExtractor.Models;

public record AvailableVideoFile(
        string FileType,
        string ContentType,
        string Variant,
        string Url,
        int? ResolutionWidth,
        int? ResolutionHeight,
        double? FileSize,
        double? Fps,
        string? Codec)
    : IAvailableFile;
