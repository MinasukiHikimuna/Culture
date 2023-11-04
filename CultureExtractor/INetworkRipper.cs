using CultureExtractor.Models;

namespace CultureExtractor
{
    public interface INetworkRipper
    {
        Task DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions);
        Task ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions);
    }
}