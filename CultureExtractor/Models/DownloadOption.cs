namespace CultureExtractor.Models;

public record DownloadOption(
    string Description,
    int? ResolutionWidth,
    int? ResolutionHeight,
    double? FileSize,
    double? Fps,
    string? Codec,
    string Url);