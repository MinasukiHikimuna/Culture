namespace RipperPlaywright
{
    public interface ISiteRipper
    {
        Task RipAsync(string shortName);
        Task DownloadAsync(string shortName, DownloadConditions conditions);
    }
}
