using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISiteScraper
{
    Task LoginAsync(Site site, IPage page);

    Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page);
    Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page);
    Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene);
    Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses);
    Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene);
    Task GoToNextFilmsPageAsync(IPage page);

    /// <summary>
    /// Can either capture a response by returning CapturedResponse or ignore it by returning null.
    /// </summary>
    Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response) { return Task.FromResult<CapturedResponse?>(null); }

    Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IList<CapturedResponse> responses);
}
