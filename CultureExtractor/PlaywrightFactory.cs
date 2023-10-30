using CultureExtractor.Models;
using Microsoft.Playwright;

namespace CultureExtractor;

public class PlaywrightFactory : IPlaywrightFactory
{
    public async Task<IPage> CreatePageAsync(Site site, BrowserSettings browserSettings)
    {
        var playwright = await Playwright.CreateAsync();
        var browser = await playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
        {
            Headless = browserSettings.BrowserMode != BrowserMode.Visible,
            Channel = !string.IsNullOrEmpty(browserSettings.BrowserChannel)
                ? browserSettings.BrowserChannel
                : "chrome",
            SlowMo = 1000,
            Args = browserSettings.BrowserMode == BrowserMode.Headless
                ? new[] { "--headless=new" }
                : Array.Empty<string>()
        });
        var context = await browser.NewContextAsync(new BrowserNewContextOptions()
        {
            BaseURL = site.Url,
            ViewportSize = new ViewportSize { Width = 1920, Height = 1080 },
            StorageState = site.StorageState
        });
        var page = await context.NewPageAsync();
        await page.GotoAsync(site.Url);
        await page.WaitForLoadStateAsync();
        return page;
    }
}
