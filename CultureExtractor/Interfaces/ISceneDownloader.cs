namespace CultureExtractor.Interfaces;

public interface ISceneDownloader
{
    Task DownloadScenesAsync(string shortName, DownloadConditions conditions, BrowserSettings browserSettings);
}
