namespace CultureExtractor;

public enum BrowserMode
{
    ClassicHeadless,
    Headless,
    Visible
}

public record BrowserSettings(BrowserMode BrowserMode, string BrowserChannel);
