using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISceneDownloader : ISite
{
    Task DownloadSceneAsync(SceneEntity scene, IPage page, string rippingPath);
}