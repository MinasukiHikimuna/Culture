using System.Net;

namespace RipperPlaywright
{
    public class Downloader
    {
        private static readonly WebClient WebClient = new();

        public async Task DownloadSceneImage(Scene scene, string imageUrl, int sceneId)
        {
            var rippingPath = $@"I:\Ripping\{scene.Site.Name}\Images\";
            Directory.CreateDirectory(rippingPath);

            await WebClient.DownloadFileTaskAsync(new Uri(imageUrl), Path.Combine(rippingPath, $"{sceneId}.jpg"));
        }
    }
}
