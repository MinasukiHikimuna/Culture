namespace CultureExtractor.Models;

public record AvailableVttFile(
        string FileType,
        string ContentType,
        string Variant,
        string Url)
    : IAvailableFile;
