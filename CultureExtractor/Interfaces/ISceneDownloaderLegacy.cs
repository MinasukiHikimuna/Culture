namespace CultureExtractor.Interfaces;

[Obsolete("Use ISceneDownloader instead")]
public interface ISceneDownloaderLegacy
{
    Task DownloadScenesAsync(string shortName, DownloadConditions conditions, BrowserSettings browserSettings);
}
