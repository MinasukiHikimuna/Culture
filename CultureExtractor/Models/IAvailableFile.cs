using System.Text.Json.Serialization;

namespace CultureExtractor.Models;

[JsonDerivedType(typeof(AvailableGalleryZipFile), typeDiscriminator: nameof(AvailableGalleryZipFile))]
[JsonDerivedType(typeof(AvailableImageFile), typeDiscriminator: nameof(AvailableImageFile))]
[JsonDerivedType(typeof(AvailableVideoFile), typeDiscriminator: nameof(AvailableVideoFile))]
[JsonDerivedType(typeof(AvailableVttFile), typeDiscriminator: nameof(AvailableVttFile))]
public interface IAvailableFile
{
    // This can be anything that the site provides such as a scene, a trailer, a subtitle file, etc.
    string FileType { get; }
    string ContentType { get; }
    string Variant { get; }
    string Url { get; }
}
