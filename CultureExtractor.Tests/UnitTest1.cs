using FluentAssertions;
using Microsoft.Playwright;
using CultureExtractor.Pages;

namespace CultureExtractor.Tests;

public class Tests
{
    private IPlaywright _playwright;
    private IBrowser _browser;
    private IBrowserContext _context;
    private IPage _page;

    [SetUp]
    public async Task Setup()
    {
        _playwright = await Playwright.CreateAsync();
        _browser = await _playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
        {
            Headless = false,
        });

        _context = await _browser.NewContextAsync(new BrowserNewContextOptions()
        {
            BaseURL = "https://www.sexart.com",
            ViewportSize = new ViewportSize { Width = 1920, Height = 1080 },
        });

        _page = await _context.NewPageAsync();

        await _page.GotoAsync("/model/eva-brown-and-ricky/movie/20230101/BARRIER");
        await _page.WaitForLoadStateAsync();
    }

    [TearDown]
    public async Task TearDown()
    {
        await _page.CloseAsync();
        await _context.CloseAsync();
        await _browser.CloseAsync();
    }

    [Test]
    public async Task Test1()
    {
        var metArtScenePage = new MetArtScenePage(_page);
        string description = await metArtScenePage.ScrapeDescriptionAsync();
        description.Should().Be("Gorgeous brunette Eva Brown is seductive in sexy lingerie and black stockings, her hands running over her voluptuous body. As Andrej Lupin’s erotic movie \"Barrier\" begins, she’s separated from Ricky by a wall, but the sledgehammer-wielding stud and his paramour demolish it with powerful blows so they can be united. Ricky fondles Eva’s beautiful big breasts as they kiss hungrily, before she sinks to her knees, unzipping his jeans and sucking his stiff cock as it springs free. Eva leans against the wall and Ricky thrusts into her from behind, fucking her to an intense orgasm; she turns and he fingerbangs her to one peak of pleasure after another. Eva gives her man another eager blowjob before he penetrates her again, her stockinged thigh wrapped around his waist. With vigorous strokes, he drives her to another orgasm before she uses both hands to jerk his cum all over her bare pussy.");
    }
}
