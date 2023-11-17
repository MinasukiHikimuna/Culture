using CultureExtractor.Models;

namespace CultureExtractor.Interfaces;

public interface IRepository
{
    Task<Release?> GetReleaseAsync(string siteShortName, string releaseShortName);
    Task<IReadOnlyList<Release>> GetReleasesAsync(string siteShortName, IList<string> releaseShortNames);
    Task<IEnumerable<Release>> GetReleasesAsync();
    Task<Site> GetSiteAsync(string shortName);
    Task<IEnumerable<Site>> GetSitesAsync();
    Task<IEnumerable<SubSite?>> GetSubSitesAsync(Guid siteUuid);
    Task<IEnumerable<Release>> QueryReleasesAsync(Site site, DownloadConditions downloadConditions, DownloadOptions downloadOptions);
    Task SaveDownloadAsync(Download download, PreferredDownloadQuality preferredDownloadQuality);
    Task UpdateStorageStateAsync(Site site, string storageState);
    Task<Release> UpsertRelease(Release release);
    Task<SubSite> UpsertSubSite(SubSite subSite);
}