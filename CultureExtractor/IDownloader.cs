using Microsoft.Playwright;
using System.Net;
using CultureExtractor.Models;

namespace CultureExtractor
{
    public interface IDownloader
    {
        void CheckFreeSpace();
        Task<Download> DownloadSceneAsync(Release release, IPage page, DownloadOption downloadDetails, PreferredDownloadQuality downloadQuality, Func<Task> func, string? filename = null);
        Task<Download> DownloadSceneDirectAsync(Release release, DownloadOption downloadDetails, PreferredDownloadQuality downloadQuality, Dictionary<HttpRequestHeader, string> headers = null, string fileName = "", string referer = "");
        Task DownloadSceneImageAsync(Release release, string imageUrl, string referer = "", Dictionary<HttpRequestHeader, string> headers = null);
        Task DownloadTrailerAsync(Release release, string url, string referer = "");
        bool SceneImageExists(Release release);
        Task<string> DownloadCaptchaAudioAsync(string captchaUrl);
        Task DownloadSceneSubtitlesAsync(Release release, string fileName, string subtitleUrl, string referer = "");
    }
}