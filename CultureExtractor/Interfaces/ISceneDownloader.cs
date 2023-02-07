using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISceneDownloader : ISiteScraper
{
    Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IList<CapturedResponse> responses);

    /// <summary>
    /// Can either capture a response by returning CapturedResponse or ignore it by returning null.
    /// </summary>
    Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response) { return Task.FromResult<CapturedResponse?>(null); }
}