using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISiteScraper
{
    Task LoginAsync(Site site, IPage page);
}
