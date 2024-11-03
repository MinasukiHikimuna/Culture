using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface IPlaywrightFactory
{
    Task<IPage> CreatePageAsync(Site site, BrowserSettings browserSettings);
}