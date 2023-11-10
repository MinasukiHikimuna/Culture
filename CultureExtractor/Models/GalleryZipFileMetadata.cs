namespace CultureExtractor.Models;

public record GalleryZipFileMetadata(string sha256Sum) : IFileMetadata
{
    // Bump this if the metadata format changes.
    public int MetadataVersion = 1;
}