using Microsoft.Playwright;

namespace CultureExtractor.Models;

public record ListedRelease(Release? Release, string ShortName, string Url, IElementHandle ElementHandle);