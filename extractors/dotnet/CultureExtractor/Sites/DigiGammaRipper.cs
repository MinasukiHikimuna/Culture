using System.Text;
using System.Text.Json;
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
        var jsonContent = Encoding.UTF8.GetString(algoliaBody);
        
        SetHeadersFromActualRequest(requests);


        var pageNumber = 1;
        var json = $$"""
                        {
                             "requests": [
                                 {
                                     "indexName":"all_scenes_latest_desc",
                                     "params":"query=&hitsPerPage=60&maxValuesPerFacet=1000&page={{pageNumber - 0}}&analytics=true&analyticsTags=%5B%22component%3Asearchlisting%22%2C%22section%3Amembers%22%2C%22site%3Agirlfriendsfilms%22%2C%22context%3Avideos%22%2C%22device%3Adesktop%22%5D&highlightPreTag=%3Cais-highlight-0000000000%3E&highlightPostTag=%3C%2Fais-highlight-0000000000%3E&facetingAfterDistinct=true&clickAnalytics=true&filters=&facets=%5B%22channels.name%22%2C%22categories.name%22%2C%22actors.name%22%2C%22video_formats.format%22%2C%22availableOnSite%22%2C%22upcoming%22%5D&tagFilters=&facetFilters=%5B%5B%22upcoming%3A0%22%5D%5D"
                                 },
                                 {
                                     "indexName":"all_scenes_latest_desc",
                                     "params":"query=&hitsPerPage=1&maxValuesPerFacet=1000&page={{pageNumber - 0}}&analytics=false&analyticsTags=%5B%22component%3Asearchlisting%22%2C%22section%3Amembers%22%2C%22site%3Agirlfriendsfilms%22%2C%22context%3Avideos%22%2C%22device%3Adesktop%22%5D&highlightPreTag=%3Cais-highlight-0000000000%3E&highlightPostTag=%3C%2Fais-highlight-0000000000%3E&facetingAfterDistinct=true&clickAnalytics=false&filters=&attributesToRetrieve=%5B%5D&attributesToHighlight=%5B%5D&attributesToSnippet=%5B%5D&tagFilters=&facets=upcoming"
                                 }
                             ]
                        }
                     """;
        var request = new HttpRequestMessage
        {
            Method = HttpMethod.Post,
            RequestUri = new Uri(algoliaRequest.Url),
            Content = new StringContent(json, Encoding.UTF8, "application/x-www-form-urlencoded")
        };
        var response = await Client.SendAsync(request);
        var responseContent = await response.Content.ReadAsStringAsync();
        
        var scenes = JsonSerializer.Deserialize<DigiGammaModels.RootObject>(responseContent);
        
        
        yield break;
    }

    private static Dictionary<string, string> SetHeadersFromActualRequest(IList<IRequest> requests)
    {
        var algoliaRequest = requests.FirstOrDefault(r => r.Url.Contains("algolia.net"));
        if (algoliaRequest == null)
        {
            var requestUrls = requests.Select(r => r.Url + Environment.NewLine).ToList();
            throw new InvalidOperationException($"Could not read galleries API request from following requests:{Environment.NewLine}{string.Join("", requestUrls)}");
        }
        
        Client.DefaultRequestHeaders.Clear();
        foreach (var key in algoliaRequest.Headers.Keys.Where(key => key != "content-type"))
        {
            Client.DefaultRequestHeaders.Add(key, algoliaRequest.Headers[key]);
        }
        
        return algoliaRequest.Headers;
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