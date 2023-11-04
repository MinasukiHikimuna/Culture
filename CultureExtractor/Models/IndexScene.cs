using Microsoft.Playwright;

namespace CultureExtractor.Models;

public record IndexScene(Release? Scene, string ShortName, string Url, IElementHandle ElementHandle);