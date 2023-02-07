using Microsoft.Extensions.Configuration;
using Microsoft.Playwright;
using System.Net;

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

    public bool SceneImageExists(Scene scene)
    {
        // TODO: extension might not be jpg
        var path = Path.Combine(_metadataPath, $@"{scene.Site.Name}\Metadata\SceneImages\{scene.Id}.jpg");
        return File.Exists(path);
    }

    public bool GalleryImageExists(Gallery gallery)
    {
        // TODO: extension might not be jpg
        var path = Path.Combine(_metadataPath, $@"{gallery.Site.Name}\Metadata\GalleryImages\{gallery.Id}.jpg");
        return File.Exists(path);
    }

    public async Task DownloadSceneImageAsync(Scene scene, string imageUrl, string referer = "")
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{scene.Site.Name}\Metadata\SceneImages\");
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(imageUrl, $"{scene.Id}.jpg", rippingPath, referer);
    }

    public async Task DownloadGalleryImageasync(Gallery gallery, string imageUrl)
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{gallery.Site.Name}\Metadata\GalleryImages\");
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(imageUrl, $"{gallery.Id}.jpg", rippingPath);
    }

    public async Task DownloadSceneSubtitlesAsync(Scene scene, string fileName, string subtitleUrl, string referer = "")
    {
        var rippingPath = Path.Combine(_metadataPath, $@"{scene.Site.Name}\Metadata\Subtitles\");
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(subtitleUrl, fileName, rippingPath, referer);
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadOption downloadDetails, PreferredDownloadQuality downloadQuality, Func<Task> func)
    {
        var waitForDownloadTask = page.WaitForDownloadAsync(new() { Timeout = (float) TimeSpan.FromHours(1).TotalMilliseconds });

        await func();

        IDownload download = await waitForDownloadTask;
        var suggestedFilename = download.SuggestedFilename;
        var suffix = Path.GetExtension(suggestedFilename);

        var name = SceneNamer.Name(scene, suffix);

        var downloadQualityDirectory = Path.Join(_downloadPath, Path.Join(scene.Site.Name, Enum.GetName(downloadQuality)));
        var path = Path.Join(downloadQualityDirectory, name);

        await download.SaveAsAsync(path);
        await download.DeleteAsync();

        return new Download(scene, suggestedFilename, name, downloadDetails);
    }

    private static async Task DownloadFileAsync(string url, string fileName, string rippingPath, string referer = "")
    {
        string? tempPath = null;
        try
        {
            tempPath = Path.Combine(rippingPath, $"{Guid.NewGuid()}");
            var finalPath = Path.Combine(rippingPath, fileName);

            WebClient.Headers.Clear();
            WebClient.Headers["Referer"] = referer;

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

    public async Task<string> DownloadCaptchaAudioAsync(string captchaUrl)
    {
        var captchaDirPath = Path.Combine(_metadataPath, "CaptchaAudios");
        Directory.CreateDirectory(captchaDirPath);

        var tempPath = Path.Combine(captchaDirPath, $"CAPTCHA_{DateTime.Now.ToString("yyyyMMddHHmmssfff")}.mp3");
        await WebClient.DownloadFileTaskAsync(new Uri(captchaUrl), tempPath);
        return tempPath;
    }
}
