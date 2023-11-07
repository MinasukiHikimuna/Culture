using Microsoft.Extensions.Configuration;
using Microsoft.Playwright;
using System.Net;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;

namespace CultureExtractor;

public class Downloader : IDownloader
{
    private static readonly WebClient WebClient = new();

    private readonly string _metadataPath;
    private readonly string _downloadPath;

    public Downloader(IConfiguration configuration)
    {
        var pathsOptions = new PathsOptions();
        configuration.GetSection(PathsOptions.Paths).Bind(pathsOptions);

        _metadataPath = pathsOptions.MetadataPath;
        _downloadPath = pathsOptions.DownloadPath;
    }

    public void CheckFreeSpace()
    {
        const long minimumFreeDiskSpace = 5L * 1024 * 1024 * 1024;
        DirectoryInfo targetDirectory = new(_downloadPath);
        DriveInfo drive = new(targetDirectory.Root.FullName);
        if (drive.AvailableFreeSpace < minimumFreeDiskSpace)
        {
            throw new InvalidOperationException($"Drive {drive.Name} has less than {minimumFreeDiskSpace} bytes free.");
        }
    }

    public bool SceneImageExists(Release release)
    {
        // TODO: extension might not be jpg
        var path = Path.Combine(_metadataPath, $@"{release.Site.Name}\Metadata\SceneImages\{release.Uuid}.jpg");
        return File.Exists(path);
    }

    public async Task DownloadSceneImageAsync(Release release, string imageUrl, string referer = "", Dictionary<HttpRequestHeader, string>? headers = null, string fileName = "")
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{release.Site.Name}\Metadata\{release.Uuid}\");
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(
            imageUrl, 
            string.IsNullOrWhiteSpace(fileName)
                ? $"{release.Uuid}.jpg"
                : fileName,
            rippingPath,
            referer: referer,
            headers: headers);
    }

    public async Task<FileInfo> DownloadFileAsync(Release release, string url, string fileName, string referer = "", Dictionary<HttpRequestHeader, string>? headers = null)
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
    
    public async Task DownloadTrailerAsync(Release release, string url, string referer = "")
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{release.Site.Name}\Metadata\Trailers\");
        Directory.CreateDirectory(rippingPath);

        // parse extension from url
        var extension = Path.GetExtension(url);
        var fileName = $"{release.Uuid}{extension}";

        await DownloadFileAsync(url, fileName, rippingPath, referer: referer);
    }

    public async Task DownloadSceneSubtitlesAsync(Release release, string fileName, string subtitleUrl, string referer = "")
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{release.Site.Name}\Metadata\Subtitles\");
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(subtitleUrl, fileName, rippingPath, referer: referer);
    }

    public async Task<Download> DownloadSceneAsync(Release release, IPage page, AvailableVideoFile downloadDetails, PreferredDownloadQuality downloadQuality, Func<Task> func, string? filename = null)
    {
        var waitForDownloadTask = page.WaitForDownloadAsync(new() { Timeout = (float) TimeSpan.FromHours(1).TotalMilliseconds });

        await func();

        IDownload download = await waitForDownloadTask;
        var suggestedFilename = download.SuggestedFilename;
        var suffix = Path.GetExtension(suggestedFilename);

        var name = string.IsNullOrWhiteSpace(filename)
            ? ReleaseNamer.Name(release, suffix)
            : $"{filename}";

        var downloadQualityDirectory = Path.Join(_downloadPath, Path.Join(release.Site.Name, Enum.GetName(downloadQuality)));
        var path = Path.Join(downloadQualityDirectory, name);

        await download.SaveAsAsync(path);
        await download.DeleteAsync();

        var videoHashes = Hasher.Phash(@"""" + path + @"""");

        return new Download(release, suggestedFilename, name, downloadDetails, videoHashes);
    }

    public async Task<Download> DownloadSceneDirectAsync(Release release, AvailableVideoFile downloadDetails, PreferredDownloadQuality downloadQuality, Dictionary<HttpRequestHeader, string> headers, string fileName = "", string referer = "")
    {
        var suggestedFilename = downloadDetails.Url.Substring(downloadDetails.Url.LastIndexOf("/") + 1);
        var suffix = Path.GetExtension(suggestedFilename);

        var name = string.IsNullOrWhiteSpace(fileName)
            ? ReleaseNamer.Name(release, suffix)
            : $"{fileName}";

        var downloadQualityDirectory = Path.Join(_downloadPath, Path.Join(release.Site.Name, Enum.GetName(downloadQuality)));
        var path = Path.Join(downloadQualityDirectory, name);
        Directory.CreateDirectory(downloadQualityDirectory);

        var url = downloadDetails.Url.StartsWith("https://")
            ? downloadDetails.Url
            : release.Site.Url + downloadDetails.Url;

        await DownloadFileAsync(url, name, downloadQualityDirectory, headers, referer);

        var videoHashes = Hasher.Phash(@"""" + path + @"""");

        return new Download(release, suggestedFilename, name, downloadDetails, videoHashes);
    }

    private static async Task DownloadFileAsync(string url, string fileName, string rippingPath, Dictionary<HttpRequestHeader, string>? headers = null, string referer = "")
    {
        string? tempPath = null;
        try
        {
            tempPath = Path.Combine(rippingPath, $"{Guid.NewGuid()}");
            var finalPath = Path.Combine(rippingPath, fileName);

            WebClient.Headers.Clear();
            if (headers != null && headers.Count > 0)
            {
                foreach (var key in headers.Keys)
                {
                    WebClient.Headers[key] = headers[key];
                }
            }
            else
            {
                WebClient.Headers[HttpRequestHeader.Referer] = referer;
            }

            WebClient.DownloadProgressChanged += new DownloadProgressChangedEventHandler(DownloadProgressCallback4);

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
        finally
        {
            Console.WriteLine();
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

    public async Task<string> DownloadCaptchaAudioAsync(string captchaUrl)
    {
        var captchaDirPath = Path.Combine(_metadataPath, "CaptchaAudios");
        Directory.CreateDirectory(captchaDirPath);

        var tempPath = Path.Combine(captchaDirPath, $"CAPTCHA_{DateTime.Now.ToString("yyyyMMddHHmmssfff")}.mp3");
        await WebClient.DownloadFileTaskAsync(new Uri(captchaUrl), tempPath);
        return tempPath;
    }
}
