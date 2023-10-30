namespace CultureExtractor.Models;

public record Download(
    Scene Scene,
    string OriginalFilename,
    string SavedFilename,
    DownloadOption DownloadOption,
    VideoHashes VideoHashes);