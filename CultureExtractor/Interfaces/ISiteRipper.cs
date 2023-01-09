namespace CultureExtractor.Interfaces;

public interface ISiteRipper
{
    Task ScrapeScenesAsync(string shortName, BrowserSettings browserSettings);
    Task ScrapeGalleriesAsync(string shortName, BrowserSettings browserSettings);
}
