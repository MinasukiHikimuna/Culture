namespace RipperPlaywright
{
    public interface ISiteRipper
    {
        Task ScrapeScenes(string shortName);
        Task DownloadAsync(string shortName, DownloadConditions conditions);
    }
}
