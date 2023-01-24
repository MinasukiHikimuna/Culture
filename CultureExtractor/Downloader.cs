using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.RegularExpressions;

namespace CultureExtractor;

public class Downloader
{
    private static readonly WebClient WebClient = new();

    public bool SceneImageExists(Scene scene)
    {
        // TODO: extension might not be jpg
        var path = $@"B:\Ripping\{scene.Site.Name}\Metadata\SceneImages\{scene.Id}.jpg";
        return File.Exists(path);
    }

    public bool GalleryImageExists(Gallery gallery)
    {
        // TODO: extension might not be jpg
        var path = $@"B:\Ripping\{gallery.Site.Name}\Metadata\GalleryImages\{gallery.Id}.jpg";
        return File.Exists(path);
    }

    public async Task DownloadSceneImageAsync(Scene scene, string imageUrl, string referer = "")
    {
        var rippingPath = $@"B:\Ripping\{scene.Site.Name}\Metadata\SceneImages\";
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(imageUrl, (int)scene.Id, rippingPath, referer);
    }

    public async Task DownloadGalleryImageasync(Gallery gallery, string imageUrl)
    {
        var rippingPath = $@"B:\Ripping\{gallery.Site.Name}\Metadata\GalleryImages\";
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(imageUrl, (int)gallery.Id, rippingPath);
    }

    public async Task<Download> DownloadSceneAsync(IPage page, DownloadOption downloadDetails, Scene scene, string rippingPath, Func<Task> func)
    {
        var performerNames = scene.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1
            ? string.Join(", ", performerNames.SkipLast(1)) + " & " + performerNames.Last()
            : performerNames.FirstOrDefault();

        var waitForDownloadTask = page.WaitForDownloadAsync();

        await func();

        var download = await waitForDownloadTask;
        var suggestedFilename = download.SuggestedFilename;
        var suffix = Path.GetExtension(suggestedFilename);
        var nameWithoutSuffix = Regex.Replace($"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}", @"\s+", " ");

        var name = (nameWithoutSuffix + suffix).Length > 260 
            ? nameWithoutSuffix[..(260 - suffix.Length - 3)] + "..." + suffix
            : nameWithoutSuffix + suffix;

        name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));
        var path = Path.Join(rippingPath, name);

        Log.Verbose($"Downloading\r\n    URL:  {downloadDetails.Url}\r\n    Path: {path}");

        await download.SaveAsAsync(path);

        return new Download(scene, suggestedFilename, name, downloadDetails);
    }

    private static async Task DownloadFileAsync(string imageUrl, int fileId, string rippingPath, string referer = "")
    {
        string? tempPath = null;
        try
        {
            tempPath = Path.Combine(rippingPath, $"{Guid.NewGuid()}.jpg");
            var finalPath = Path.Combine(rippingPath, $"{fileId}.jpg");

            WebClient.Headers.Clear();
            WebClient.Headers["Referer"] = referer;

            await WebClient.DownloadFileTaskAsync(new Uri(imageUrl), tempPath);
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
