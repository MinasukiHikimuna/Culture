using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISiteScraper
{
    Task LoginAsync(Site site, IPage page);
    Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page);
    Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber);
    Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests);
    Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests);
}
