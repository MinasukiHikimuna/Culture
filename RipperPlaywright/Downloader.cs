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

            await WebClient.DownloadFileTaskAsync(new Uri(imageUrl), Path.Combine(rippingPath, $"{sceneId}.jpg"));
        }

        public async Task DownloadGalleryImage(Gallery gallery, string imageUrl, int galleryId)
        {
            var rippingPath = $@"I:\Ripping\{gallery.Site.Name}\Metadata\GalleryImages\";
            Directory.CreateDirectory(rippingPath);

            await WebClient.DownloadFileTaskAsync(new Uri(imageUrl), Path.Combine(rippingPath, $"{galleryId}.jpg"));
        }
    }
}
