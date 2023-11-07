using CultureExtractor.Models;

namespace CultureExtractor;

public interface IYieldingScraper
{
    IAsyncEnumerable<Release> ScrapeAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions);
}