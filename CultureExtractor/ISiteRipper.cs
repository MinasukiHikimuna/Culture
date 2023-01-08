namespace CultureExtractor
{
    public interface ISiteRipper
    {
        Task ScrapeScenesAsync(string shortName, BrowserSettings browserSettings);
        Task ScrapeGalleriesAsync(string shortName, BrowserSettings browserSettings);
        Task DownloadAsync(string shortName, DownloadConditions conditions, BrowserSettings browserSettings);
    }
}
