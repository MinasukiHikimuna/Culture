using System.Net;
using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ILegacyDownloader
{
    void CheckFreeSpace();
    Task<Download> DownloadSceneAsync(Release release, IPage page, AvailableVideoFile downloadDetails, PreferredDownloadQuality downloadQuality, Func<Task> func, string? filename = null);
    Task<Download> DownloadSceneDirectAsync(Release release, AvailableVideoFile downloadDetails, PreferredDownloadQuality downloadQuality, WebHeaderCollection? headers = null, string fileName = "", string referer = "");

    Task<FileInfo> DownloadFileAsync(Release release, string url, string fileName, string referer = "", WebHeaderCollection? headers = null);
    Task DownloadSceneImageAsync(Release release, string imageUrl, string referer = "", WebHeaderCollection? headers = null, string fileName = "");
    Task DownloadTrailerAsync(Release release, string url, string referer = "");
    bool SceneImageExists(Release release);
    Task<string> DownloadCaptchaAudioAsync(string captchaUrl);
    Task DownloadSceneSubtitlesAsync(Release release, string fileName, string subtitleUrl, string referer = "");
}