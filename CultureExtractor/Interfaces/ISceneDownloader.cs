using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISceneDownloader : ISiteScraper
{
    Task DownloadSceneAsync(SceneEntity scene, IPage page, string rippingPath);
}