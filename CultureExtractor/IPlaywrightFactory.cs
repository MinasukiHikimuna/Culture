using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor;

public interface IPlaywrightFactory
{
    Task<IPage> CreatePageAsync(Site site, BrowserSettings browserSettings);
}