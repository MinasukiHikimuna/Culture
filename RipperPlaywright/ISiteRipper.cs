namespace RipperPlaywright
{
    public interface ISiteRipper
    {
        Task ScrapeScenesAsync(string shortName);
        Task ScrapeGalleriesAsync(string shortName);
        Task DownloadAsync(string shortName, DownloadConditions conditions);
    }
}
