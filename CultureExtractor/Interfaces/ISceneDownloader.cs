using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISceneDownloader : ISiteScraper
{
    Task<DownloadDetails> DownloadSceneAsync(SceneEntity scene, IPage page, string rippingPath, DownloadConditions downloadConditions);
}