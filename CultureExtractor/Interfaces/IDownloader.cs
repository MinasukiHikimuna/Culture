using System.Net;
using CultureExtractor.Models;

namespace CultureExtractor.Interfaces;

public interface IDownloader
{
    Task<FileInfo?> TryDownloadAsync(Release release, IAvailableFile availableFile, string url, string fileName, WebHeaderCollection convertedHeaders);
}
