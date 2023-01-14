namespace CultureExtractor.Interfaces;

public interface ISceneDownloaderLegacy
{
    Task DownloadScenesAsync(string shortName, DownloadConditions conditions, BrowserSettings browserSettings);
}
