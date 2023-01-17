using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISceneDownloader : ISiteScraper
{
    Task<Download> DownloadSceneAsync(SceneEntity scene, IPage page, string rippingPath, DownloadConditions downloadConditions);
}