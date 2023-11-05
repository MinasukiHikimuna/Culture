namespace CultureExtractor.Models;

public record Download(
    Release Release,
    string OriginalFilename,
    string SavedFilename,
    AvailableVideoFile AvailableVideoFile,
    VideoHashes VideoHashes);