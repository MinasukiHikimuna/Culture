using Microsoft.Playwright;

namespace CultureExtractor.Models;

public record IndexScene(Scene? Scene, string ShortName, string Url, IElementHandle ElementHandle);