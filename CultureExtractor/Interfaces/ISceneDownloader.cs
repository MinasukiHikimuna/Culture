using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISceneDownloader : ISiteScraper
{
    Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions);
}