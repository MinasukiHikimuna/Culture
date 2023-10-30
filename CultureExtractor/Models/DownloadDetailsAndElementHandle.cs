using Microsoft.Playwright;

namespace CultureExtractor.Models;

public record DownloadDetailsAndElementHandle(
    DownloadOption DownloadOption,
    IElementHandle ElementHandle);