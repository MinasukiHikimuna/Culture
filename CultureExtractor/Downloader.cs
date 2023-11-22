using System.Net;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.Extensions.Configuration;
using Serilog;

namespace CultureExtractor;

public class Downloader : IDownloader
{
    private static readonly WebClient WebClient = new();
    private static readonly HttpClient HttpClient = new();

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
                                          (ex.InnerException.Message.Contains("The response ended prematurely") || 
                                           ex.InnerException.Message.Contains("Received an unexpected EOF or 0 bytes from the transport stream.")))
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

            HttpClient.DefaultRequestHeaders.Clear();
            if (headers != null && headers.Count > 0)
            {
                foreach (var key in headers.AllKeys)
                {
                    HttpClient.DefaultRequestHeaders.Add(key, headers[key]);
                }
            }
            else
            {
                HttpClient.DefaultRequestHeaders.Add("referer", referer);
            }

            using var response = await HttpClient.SendAsync(new HttpRequestMessage(HttpMethod.Get, url), HttpCompletionOption.ResponseHeadersRead);
            if (!response.IsSuccessStatusCode)
            {
                throw new Exception($"Error {response.StatusCode} downloading {url}");
            }

            var totalBytes = response.Content.Headers.ContentLength;

            {
                await using var contentStream = await response.Content.ReadAsStreamAsync();
                await using var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None,
                    8192, true);
                var totalRead = 0L;
                var buffer = new byte[8192];
                var isMoreToRead = true;

                do
                {
                    var read = await contentStream.ReadAsync(buffer, 0, buffer.Length);
                    if (read == 0)
                    {
                        isMoreToRead = false;
                    }
                    else
                    {
                        await fileStream.WriteAsync(buffer, 0, read);

                        totalRead += read;
                        var percentage = totalBytes.HasValue ? (totalRead * 1d) / (totalBytes.Value * 1d) * 100 : -1;
                        // Displays the operation identifier, and the transfer progress.
                        Console.Write("\rDownloaded {0}/{1} bytes. {2:0.00}% complete...",
                            totalRead,
                            totalBytes, percentage);
                    }
                } while (isMoreToRead);
            }

            Console.Write("\n");
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
}
