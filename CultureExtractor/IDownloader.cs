using Microsoft.Playwright;
using System.Net;
using CultureExtractor.Models;

namespace CultureExtractor
{
    public interface IDownloader
    {
        void CheckFreeSpace();
        Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadOption downloadDetails, PreferredDownloadQuality downloadQuality, Func<Task> func, string? filename = null);
        Task<Download> DownloadSceneDirectAsync(Scene scene, DownloadOption downloadDetails, PreferredDownloadQuality downloadQuality, Dictionary<HttpRequestHeader, string> headers = null, string fileName = "", string referer = "");
        Task DownloadSceneImageAsync(Scene scene, string imageUrl, string referer = "", Dictionary<HttpRequestHeader, string> headers = null);
        Task DownloadTrailerAsync(Scene scene, string url, string referer = "");
        bool SceneImageExists(Scene scene);
        Task<string> DownloadCaptchaAudioAsync(string captchaUrl);
        Task DownloadSceneSubtitlesAsync(Scene scene, string fileName, string subtitleUrl, string referer = "");
    }
}