using CultureExtractor.Models;

namespace CultureExtractor
{
    public interface IRepository
    {
        Task<Scene?> GetSceneAsync(string siteShortName, string sceneShortName);
        Task<IReadOnlyList<Scene>> GetScenesAsync(string siteShortName, IList<string> sceneShortNames);
        Task<IEnumerable<Scene>> GetScenesAsync();
        Task<Site> GetSiteAsync(string shortName);
        Task<IEnumerable<Site>> GetSitesAsync();
        Task<IEnumerable<SubSite?>> GetSubSitesAsync(int siteId);
        Task<IEnumerable<Scene>> QueryScenesAsync(Site site, DownloadConditions downloadConditions);
        Task SaveDownloadAsync(Download download, PreferredDownloadQuality preferredDownloadQuality);
        Task UpdateStorageStateAsync(Site site, string storageState);
        Task<Scene> UpsertScene(Scene scene);
        Task<SubSite> UpsertSubSite(SubSite subSite);
    }
}