using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.Playwright;
using Polly;
using Serilog;

namespace CultureExtractor;

public class PlaywrightFactory : IPlaywrightFactory
{
    public async Task<IPage> CreatePageAsync(Site site, BrowserSettings browserSettings)
    {
        var strategy = new ResiliencePipelineBuilder<IPage>()
            .AddRetry(new ()
            {
                MaxRetryAttempts = 3,
                Delay = TimeSpan.FromSeconds(10),
                OnRetry = args =>
                {
                    var ex = args.Outcome.Exception;
                    Log.Error($"Caught following exception while creating page for {site.Url}: " + ex, ex);
                    return default;
                }
            })
            .Build();
        
        return await strategy.ExecuteAsync(async token =>
            await CreatePageInternalAsync(site, browserSettings, token)
        );
    }

    private async Task<IPage> CreatePageInternalAsync(Site site, BrowserSettings browserSettings, CancellationToken token)
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
