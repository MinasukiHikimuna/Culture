using Microsoft.Extensions.DependencyInjection;

namespace CultureExtractor.Tests;

[TestFixture]
public class E2ETests
{
    // [Test]
    public async Task BasicData()
    {
        var scrapeOptions = new ScrapeOptions()
        {
            SiteShortName = "sexart",
            MaxReleases = int.MaxValue
        };

        var host = AppHostFactory.CreateHost(new string[0], scrapeOptions.SiteShortName);
        var networkRipper = host.Services.GetRequiredService<INetworkRipper>();
        var repository = host.Services.GetRequiredService<IRepository>();

        var browserSettings = new BrowserSettings(BrowserMode.Headless, "chrome");

        var site = await repository.GetSiteAsync(scrapeOptions.SiteShortName);

        await networkRipper.ScrapeReleasesAsync(site, browserSettings, scrapeOptions);
    }
}
