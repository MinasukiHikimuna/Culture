using Microsoft.Playwright;

namespace CultureExtractor;

public static class PlaywrightFactory
{
    public static async Task<IPage> CreatePageAsync(Site site, BrowserSettings browserSettings)
    {
        var playwright = await Playwright.CreateAsync();
        var browser = await playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
        {
            Headless = browserSettings.Headless,
            Channel = !string.IsNullOrEmpty(browserSettings.BrowserChannel)
                ? browserSettings.BrowserChannel
                : "chrome",
            SlowMo = 1000,
            // This should be parameterized
            /* Args = browserSettings.Headless
                ? new[] { "--headless=new" }
                : Array.Empty<string>()*/
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
