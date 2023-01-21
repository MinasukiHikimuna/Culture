namespace CultureExtractor.Interfaces;

[Obsolete("Use ISceneScraper, ISiteScraper and ISceneDownloader instead")]
public interface ISiteRipper
{
    Task ScrapeScenesAsync(string shortName, BrowserSettings browserSettings);
    Task ScrapeGalleriesAsync(string shortName, BrowserSettings browserSettings);
}
