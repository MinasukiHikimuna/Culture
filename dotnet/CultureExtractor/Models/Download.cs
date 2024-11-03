namespace CultureExtractor.Models;

public record Download(
    Release Release,
    string OriginalFilename,
    string SavedFilename,
    IAvailableFile AvailableFile,
    IFileMetadata FileMetadata);