using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISubSiteScraper : ISiteScraper
{
    Task<IReadOnlyList<SubSite>> GetSubSitesAsync(Site site, IPage page);
    Task<int> NavigateToSubSiteAndReturnPageCountAsync(Site site, SubSite subSite, IPage page);
}
