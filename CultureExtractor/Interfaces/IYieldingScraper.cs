using CultureExtractor.Models;

namespace CultureExtractor.Interfaces;

public interface IYieldingScraper
{
    IAsyncEnumerable<Release> ScrapeAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions);
}