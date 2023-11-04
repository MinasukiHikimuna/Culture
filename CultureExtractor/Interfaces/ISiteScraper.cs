using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISiteScraper
{
    Task LoginAsync(Site site, IPage page);
    Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page);
    Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests);
    Task<Scene> ScrapeSceneAsync(Guid sceneUuid, Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests);
    Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber);
    Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests);
}
