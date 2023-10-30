using CultureExtractor.Models;

namespace CultureExtractor
{
    public interface INetworkRipper
    {
        Task DownloadScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions);
        Task ScrapeScenesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions);
    }
}