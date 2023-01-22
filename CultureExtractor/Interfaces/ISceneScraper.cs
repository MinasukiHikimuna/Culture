using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISceneScraper : ISiteScraper
{
    Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page);
    Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(IPage page);
    Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene);
    Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page);
    Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene);
    Task GoToNextFilmsPageAsync(IPage page);
}
