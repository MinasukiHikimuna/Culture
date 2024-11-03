using Microsoft.Playwright;

namespace CultureExtractor.Models;

public record DownloadDetailsAndElementHandle(
    AvailableVideoFile AvailableVideoFile,
    IElementHandle ElementHandle);