using System.Net;
using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface IDownloader
{
    void CheckFreeSpace();
    Task<Download> DownloadSceneAsync(Release release, IPage page, AvailableVideoFile downloadDetails, PreferredDownloadQuality downloadQuality, Func<Task> func, string? filename = null);
    Task<Download> DownloadSceneDirectAsync(Release release, AvailableVideoFile downloadDetails, PreferredDownloadQuality downloadQuality, Dictionary<HttpRequestHeader, string> headers = null, string fileName = "", string referer = "");

    Task<FileInfo> DownloadFileAsync(Release release, string url, string fileName, string referer = "", Dictionary<HttpRequestHeader, string>? headers = null);
    Task DownloadSceneImageAsync(Release release, string imageUrl, string referer = "", Dictionary<HttpRequestHeader, string> headers = null, string fileName = "");
    Task DownloadTrailerAsync(Release release, string url, string referer = "");
    bool SceneImageExists(Release release);
    Task<string> DownloadCaptchaAudioAsync(string captchaUrl);
    Task DownloadSceneSubtitlesAsync(Release release, string fileName, string subtitleUrl, string referer = "");
}