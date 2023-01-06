using Microsoft.Playwright;

namespace RipperPlaywright
{
    public static class PlaywrightFactory
    {
        public static async Task<IPage> CreatePageAsync(Site site, bool headless)
        {
            var playwright = await Playwright.CreateAsync();
            var browser = await playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
            {
                Headless = headless,
            });
            var context = await browser.NewContextAsync(new BrowserNewContextOptions()
            {
                BaseURL = site.Url,
                ViewportSize = new ViewportSize { Width = 1920, Height = 1080 },
                StorageState = site.StorageState
            });
            var page = await context.NewPageAsync();
            await page.GotoAsync("/");
            await page.WaitForLoadStateAsync();
            return page;
        }
    }
}
