using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor.Sites;

[Site("girlfriendsfilms")]
public class DigiGammaRipper : IYieldingScraper
{
    private static readonly HttpClient Client = new();
    
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly ICaptchaSolver _captchaSolver;
    private readonly IRepository _repository;

    public DigiGammaRipper(IPlaywrightFactory playwrightFactory, ICaptchaSolver captchaSolver, IRepository repository)
    {
        _playwrightFactory = playwrightFactory;
        _captchaSolver = captchaSolver;
        _repository = repository;
    }

    private static string GalleriesUrl(Site site, int pageNumber) =>
        $"{site.Url}/en/videos/{pageNumber}";
    
    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);

        var requests = await CaptureRequestsAsync(site, page);

        /*await foreach (var scene in ScrapeScenesAsync(site, scrapeOptions))
        {
            yield return scene;
        }*/
        
        var algoliaRequest = requests.First(r => r.Url.Contains("algolia.net"));
        var algoliaResponse = await algoliaRequest.ResponseAsync();
        var algoliaBody = await algoliaResponse.BodyAsync();
        var jsonContent = System.Text.Encoding.UTF8.GetString(algoliaBody);
        
        yield break;
    }

    public IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings,
        DownloadConditions downloadConditions)
    {
        throw new NotImplementedException();
    }
    
    private static async Task<List<IRequest>> CaptureRequestsAsync(Site site, IPage page)
    {
        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });

        await page.GotoAsync(GalleriesUrl(site, 1));
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        await page.UnrouteAsync("**/*");
        return requests;
    }
    
    private async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var usernameInput = page.GetByPlaceholder("Username");
        if (await usernameInput.IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username").ClickAsync();
            await page.GetByPlaceholder("Username").FillAsync(site.Username);

            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
            await page.WaitForLoadStateAsync();

            await Task.Delay(5000);

            /*if (await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).IsVisibleAsync())
            {
                await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
                await page.WaitForLoadStateAsync();
            }*/
        }
 
        await Task.Delay(5000);
        
        await _captchaSolver.SolveCaptchaIfNeededAsync(page);
        
        await Task.Delay(5000);

        await page.GotoAsync(site.Url);

        Log.Information($"Logged into {site.Name}.");
        
        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
    }
}