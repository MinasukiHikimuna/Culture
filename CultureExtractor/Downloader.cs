using System.Net;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.Extensions.Configuration;
using Serilog;

namespace CultureExtractor;

public class Downloader : IDownloader
{
    private static readonly WebClient WebClient = new();

    private readonly string _metadataPath;

    public Downloader(IConfiguration configuration)
    {
        var pathsOptions = new PathsOptions();
        configuration.GetSection(PathsOptions.Paths).Bind(pathsOptions);

        _metadataPath = pathsOptions.MetadataPath;
    }
    
    public async Task<FileInfo?> TryDownloadAsync(Release release, IAvailableFile availableFile, string url,
        string fileName, WebHeaderCollection convertedHeaders)
    {
        const int maxRetryCount = 3; // Set the maximum number of retries
        var retryCount = 0;

        while (retryCount < maxRetryCount)
        {
            retryCount++;
            try
            {
                return await DownloadFileAsync(
                    release,
                    url,
                    fileName,
                    release.Url,
                    convertedHeaders);
            }
            catch (WebException ex) when ((ex.Response as HttpWebResponse)?.StatusCode == HttpStatusCode.NotFound)
            {
                Log.Warning("Could not find {FileType} {ContentType} for {Release} from URL {Url}",
                    availableFile.FileType, availableFile.ContentType, release.Uuid, url);
                return null;
            }
            catch (WebException ex) when (ex.InnerException is IOException &&
                                          ex.InnerException.Message.Contains("The response ended prematurely"))
            {
                if (retryCount >= maxRetryCount)
                {
                    Log.Error("Max retry attempts reached for {FileType} {ContentType} for {Release} from URL {Url}.",
                        availableFile.FileType, availableFile.ContentType, release.Uuid, url);
                    return null;
                }

                Log.Warning(
                    "Download ended prematurely for {FileType} {ContentType} for {Release} from URL {Url}. Retrying...",
                    availableFile.FileType, availableFile.ContentType, release.Uuid, url);
            }
            catch (WebException ex)
            {
                Log.Error(ex, "Error downloading {FileType} {ContentType} for {Release} from URL {Url}",
                    availableFile.FileType, availableFile.ContentType, release.Uuid, url);
                return null;
            }
        }

        return null;
    }

    private async Task<FileInfo> DownloadFileAsync(Release release, string url, string fileName, string referer = "",
        WebHeaderCollection? headers = null)
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{release.Site.Name}\Metadata\{release.Uuid}\");
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(
            url,
            fileName,
            rippingPath,
            referer: referer,
            headers: headers);

        return new FileInfo(Path.Combine(rippingPath, fileName));
    }

    private static async Task DownloadFileAsync(string url, string fileName, string rippingPath,
        WebHeaderCollection? headers = null, string referer = "")
    {
        string? tempPath = null;
        try
        {
            tempPath = Path.Combine(rippingPath, $"{Guid.NewGuid()}");
            var finalPath = Path.Combine(rippingPath, fileName);

            WebClient.Headers.Clear();
            if (headers != null && headers.Count > 0)
            {
                foreach (var key in headers.AllKeys)
                {
                    WebClient.Headers[key] = headers[key];
                }
            }
            else
            {
                WebClient.Headers[HttpRequestHeader.Referer] = referer;
            }

            WebClient.DownloadProgressChanged += DownloadProgressCallback4;

            await WebClient.DownloadFileTaskAsync(new Uri(url), tempPath);
            File.Move(tempPath, finalPath, true);
        }
        catch
        {
            if (!string.IsNullOrWhiteSpace(tempPath))
            {
                File.Delete(tempPath);
            }

            throw;
        }
    }
    
    private static void DownloadProgressCallback4(object sender, DownloadProgressChangedEventArgs e)
    {
        // Displays the operation identifier, and the transfer progress.
        Console.Write("\rDownloaded {0}/{1} bytes. {2}% complete...",
            e.BytesReceived,
            e.TotalBytesToReceive,
            e.ProgressPercentage);
    }
}
