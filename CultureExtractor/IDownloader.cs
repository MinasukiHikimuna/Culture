using Microsoft.Playwright;

namespace CultureExtractor
{
    public interface IDownloader
    {
        void CheckFreeSpace();
        Task DownloadGalleryImageasync(Gallery gallery, string imageUrl);
        Task<Download> DownloadSceneAsync(IPage page, DownloadOption downloadDetails, Scene scene, Func<Task> func);
        Task DownloadSceneImageAsync(Scene scene, string imageUrl, string referer = "");
        bool GalleryImageExists(Gallery gallery);
        bool SceneImageExists(Scene scene);
        Task<string> DownloadCaptchaAudioAsync(string captchaUrl);
    }
}