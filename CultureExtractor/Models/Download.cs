namespace CultureExtractor.Models;

public record Download(
    Release Release,
    string OriginalFilename,
    string SavedFilename,
    DownloadOption DownloadOption,
    VideoHashes VideoHashes);