using Microsoft.Playwright;

namespace CultureExtractor
{
    public interface IDownloader
    {
        Task DownloadGalleryImageasync(Gallery gallery, string imageUrl);
        Task<Download> DownloadSceneAsync(IPage page, DownloadOption downloadDetails, Scene scene, string rippingPath, Func<Task> func);
        Task DownloadSceneImageAsync(Scene scene, string imageUrl, string referer = "");
        bool GalleryImageExists(Gallery gallery);
        bool SceneImageExists(Scene scene);
    }
}