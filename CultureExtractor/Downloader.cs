using System.Net;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.Extensions.Configuration;
using Polly;
using Polly.Fallback;
using Serilog;

namespace CultureExtractor;

public class Downloader : IDownloader
{
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
        var strategy = new ResiliencePipelineBuilder<FileInfo?>()
            .AddFallback(new FallbackStrategyOptions<FileInfo?>
            {
                FallbackAction = _ => Outcome.FromResultAsValueTask<FileInfo?>(null)
            })
            .AddRetry(new ()
            {
                MaxRetryAttempts = 3,
                Delay = TimeSpan.FromSeconds(10),
                OnRetry = args =>
                {
                    var ex = args.Outcome.Exception;
                    Log.Error($"Caught following exception while downloading {url}: " + ex, ex);
                    return default;
                }
            })
            .Build();

        var fileInfo = await strategy.ExecuteAsync(async token =>
            await DownloadFileAsync(
                release,
                url,
                fileName,
                convertedHeaders,
                release.Url,
                token)
        );
        return fileInfo;
    }

    private async Task<FileInfo> DownloadFileAsync(Release release, string url, string fileName,
        WebHeaderCollection headers, string referer,
        CancellationToken cancellationToken)
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{release.Site.Name}\Metadata\{release.Uuid}\");
        Directory.CreateDirectory(rippingPath);

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

            using var response = await HttpClient.SendAsync(new HttpRequestMessage(HttpMethod.Get, url), HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                throw new Exception($"Error {response.StatusCode} downloading {url}");
            }

            var totalBytes = response.Content.Headers.ContentLength;

            {
                await using var contentStream = await response.Content.ReadAsStreamAsync(cancellationToken);
                await using var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None,
                    16384, true);
                var totalRead = 0L;
                var buffer = new byte[16384];
                var isMoreToRead = true;

                do
                {
                    var innerCancellationSource = new CancellationTokenSource(TimeSpan.FromSeconds(60));
                    var linkedCancellationSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, innerCancellationSource.Token);

                    try
                    {
                        var read = await contentStream.ReadAsync(buffer, linkedCancellationSource.Token);
                        if (read == 0)
                        {
                            isMoreToRead = false;
                        }
                        else
                        {
                            await fileStream.WriteAsync(buffer.AsMemory(0, read), linkedCancellationSource.Token);

                            totalRead += read;
                            var percentage = totalBytes.HasValue ? totalRead * 1d / (totalBytes.Value * 1d) * 100 : -1;
                            // Displays the operation identifier, and the transfer progress.
                            Console.Write("\r{3:HH:mm:ss} Downloaded {0}/{1} bytes. {2:0.00}% complete...",
                                totalRead,
                                totalBytes,
                                percentage,
                                DateTime.Now);
                        }
                    }
                    catch (OperationCanceledException ex)
                    {
                        if (ex.CancellationToken == cancellationToken)
                        {
                            throw; // Rethrow the exception to cancel the operation
                        }

                        if (ex.CancellationToken == innerCancellationSource.Token)
                        {
                            // Restart the download
                            Log.Information("Downloading stalled for release {Name} [{Uuid}]", release.Name, release.Uuid);
                            totalRead = 0;
                            fileStream.Position = 0;
                        }
                    }
                    finally
                    {
                        innerCancellationSource.Dispose();
                        linkedCancellationSource.Dispose();
                    }
                } while (isMoreToRead);
            }

            Console.Write("\r");
            File.Move(tempPath, finalPath, true);

            return new FileInfo(Path.Combine(rippingPath, fileName));
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
