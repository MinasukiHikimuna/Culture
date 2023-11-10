namespace CultureExtractor.Models;

public record VideoFileMetadata(int Duration, string SHA256Sum, VideoHashes Hashes) : IFileMetadata
{
    // Bump this if the metadata format changes.
    public int MetadataVersion = 1;
}
