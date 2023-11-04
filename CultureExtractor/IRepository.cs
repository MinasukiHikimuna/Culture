using CultureExtractor.Models;

namespace CultureExtractor
{
    public interface IRepository
    {
        Task<Release?> GetSceneAsync(string siteShortName, string sceneShortName);
        Task<IReadOnlyList<Release>> GetReleasesAsync(string siteShortName, IList<string> sceneShortNames);
        Task<IEnumerable<Release>> GetReleasesAsync();
        Task<Site> GetSiteAsync(string shortName);
        Task<IEnumerable<Site>> GetSitesAsync();
        Task<IEnumerable<SubSite?>> GetSubSitesAsync(Guid siteUuid);
        Task<IEnumerable<Release>> QueryReleasesAsync(Site site, DownloadConditions downloadConditions);
        Task SaveDownloadAsync(Download download, PreferredDownloadQuality preferredDownloadQuality);
        Task UpdateStorageStateAsync(Site site, string storageState);
        Task<Release> UpsertScene(Release release);
        Task<SubSite> UpsertSubSite(SubSite subSite);
    }
}