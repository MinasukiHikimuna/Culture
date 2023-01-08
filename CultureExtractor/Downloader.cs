using System.Net;

namespace CultureExtractor;

public class Downloader
{
    private static readonly WebClient WebClient = new();

    public bool SceneImageExists(Scene scene)
    {
        // TODO: extension might not be jpg
        var path = $@"I:\Ripping\{scene.Site.Name}\Metadata\SceneImages\{scene.Id}.jpg";
        return File.Exists(path);
    }

    public bool GalleryImageExists(Gallery gallery)
    {
        // TODO: extension might not be jpg
        var path = $@"I:\Ripping\{gallery.Site.Name}\Metadata\GalleryImages\{gallery.Id}.jpg";
        return File.Exists(path);
    }

    public async Task DownloadSceneImageAsync(Scene scene, string imageUrl)
    {
        var rippingPath = $@"I:\Ripping\{scene.Site.Name}\Metadata\SceneImages\";
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(imageUrl, (int)scene.Id, rippingPath);
    }

    public async Task DownloadGalleryImageasync(Gallery gallery, string imageUrl)
    {
        var rippingPath = $@"I:\Ripping\{gallery.Site.Name}\Metadata\GalleryImages\";
        Directory.CreateDirectory(rippingPath);

        await DownloadFileAsync(imageUrl, (int)gallery.Id, rippingPath);
    }

    private static async Task DownloadFileAsync(string imageUrl, int fileId, string rippingPath)
    {
        string? tempPath = null;
        try
        {
            tempPath = Path.Combine(rippingPath, $"{Guid.NewGuid()}.jpg");
            var finalPath = Path.Combine(rippingPath, $"{fileId}.jpg");
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
