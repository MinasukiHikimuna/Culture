using CultureExtractor.Models;

namespace CultureExtractor.Interfaces;

public interface IYieldingScraper : IScraper
{
    IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions);

    IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions);
}
