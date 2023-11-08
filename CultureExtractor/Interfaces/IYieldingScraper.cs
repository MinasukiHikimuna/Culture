using CultureExtractor.Models;

namespace CultureExtractor.Interfaces;

public interface IYieldingScraper
{
    IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions);

    IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions);
}