using CultureExtractor.Models;

namespace CultureExtractor.Sites;

public interface IYieldingScraper
{
    IAsyncEnumerable<Release> ScrapeAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions);
}