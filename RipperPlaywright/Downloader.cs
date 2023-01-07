using System.Net;

namespace RipperPlaywright
{
    public class Downloader
    {
        private static readonly WebClient WebClient = new();

        public async Task DownloadSceneImage(Scene scene, string imageUrl, int sceneId)
        {
            var rippingPath = $@"I:\Ripping\{scene.Site.Name}\Metadata\SceneImages\";
            Directory.CreateDirectory(rippingPath);

            await DownloadFileAsync(imageUrl, sceneId, rippingPath);
        }

        public async Task DownloadGalleryImage(Gallery gallery, string imageUrl, int galleryId)
        {
            var rippingPath = $@"I:\Ripping\{gallery.Site.Name}\Metadata\GalleryImages\";
            Directory.CreateDirectory(rippingPath);

            await DownloadFileAsync(imageUrl, galleryId, rippingPath);
        }

        private static async Task DownloadFileAsync(string imageUrl, int fileId, string rippingPath)
        {
            var tempPath = Path.Combine(rippingPath, $"{Guid.NewGuid()}.jpg");
            var finalPath = Path.Combine(rippingPath, $"{fileId}.jpg");
            await WebClient.DownloadFileTaskAsync(new Uri(imageUrl), tempPath);
            File.Move(tempPath, finalPath, true);
        }
    }
}
