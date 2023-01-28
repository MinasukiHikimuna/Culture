namespace CultureExtractor
{
    public interface INetworkRipper
    {
        Task DownloadScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions);
        Task ScrapeScenesAsync(Site site, BrowserSettings browserSettings, bool fullScrape);
    }
}