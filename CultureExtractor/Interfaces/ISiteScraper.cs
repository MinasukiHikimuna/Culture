using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISiteScraper
{
    Task LoginAsync(Site site, IPage page);
    Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page);
    Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests);
    Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene);
    Task<Scene> ScrapeSceneAsync(Guid sceneUuid, Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests);
    Task DownloadAdditionalFilesAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene, IReadOnlyList<IRequest> requests);
    Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber);

    /// <summary>
    /// Can either capture a response by returning CapturedResponse or ignore it by returning null.
    /// </summary>
    Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response) { return Task.FromResult<CapturedResponse?>(null); }

    Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests);
}
