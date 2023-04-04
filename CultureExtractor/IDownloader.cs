using Microsoft.Playwright;
using System.Net;

namespace CultureExtractor
{
    public interface IDownloader
    {
        void CheckFreeSpace();
        Task DownloadGalleryImageasync(Gallery gallery, string imageUrl);
        Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadOption downloadDetails, PreferredDownloadQuality downloadQuality, Func<Task> func, string? filename = null);
        Task<Download> DownloadSceneDirectAsync(Scene scene, DownloadOption downloadDetails, PreferredDownloadQuality downloadQuality, Dictionary<HttpRequestHeader, string> headers = null, string fileName = "", string referer = "");
        Task DownloadSceneImageAsync(Scene scene, string imageUrl, string referer = "");
        bool GalleryImageExists(Gallery gallery);
        bool SceneImageExists(Scene scene);
        Task<string> DownloadCaptchaAudioAsync(string captchaUrl);
        Task DownloadSceneSubtitlesAsync(Scene scene, string fileName, string subtitleUrl, string referer = "");
    }
}