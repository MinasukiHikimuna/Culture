using System.Text.Json.Serialization;

namespace CultureExtractor.Models;

[JsonDerivedType(typeof(GalleryZipFileMetadata), typeDiscriminator: nameof(GalleryZipFileMetadata))]
[JsonDerivedType(typeof(ImageFileMetadata), typeDiscriminator: nameof(ImageFileMetadata))]
[JsonDerivedType(typeof(VideoFileMetadata), typeDiscriminator: nameof(VideoFileMetadata))]
[JsonDerivedType(typeof(VttFileMetadata), typeDiscriminator: nameof(VttFileMetadata))]
[JsonDerivedType(typeof(VideoHashes), typeDiscriminator: nameof(VideoHashes))]
public interface IFileMetadata
{
}