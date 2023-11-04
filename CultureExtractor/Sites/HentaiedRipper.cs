using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

public class Sources
{
    [JsonPropertyName("sources")]
    public IList<FileSource> FileSources { get; set; }
}

public class FileSource
{
    [JsonPropertyName("file")]
    public string Url { get; set; }
    [JsonPropertyName("label")]
    public string Resolution { get; set; }
}


[PornSite("hentaied")]
public class HentaiedRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public HentaiedRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(10000);

        var modalContentClose = page.Locator("div.modal-content span.close-btn");
        if (await modalContentClose.IsVisibleAsync())
        {
            await modalContentClose.ClickAsync();
        }

        var loginLink = page.GetByRole(AriaRole.Link).Filter(new LocatorFilterOptions() { HasText = "Login" });
        if (await loginLink.IsVisibleAsync())
        {
            await loginLink.ClickAsync();
        }

        var usernameInput = page.Locator("input#amember-login");
        if (await usernameInput.IsVisibleAsync())
        {
            await usernameInput.FillAsync(site.Username);
        }

        var passwordInput = page.Locator("input#amember-pass");
        if (await passwordInput.IsVisibleAsync())
        {
            await passwordInput.FillAsync(site.Password);
            await passwordInput.PressAsync("Enter");
            await Task.Delay(5000);
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GotoAsync("/all-videos/");

        var lastPageLink = page.Locator("section.pagination > p > a.page-numbers").Nth(-2);
        var lastPageRaw = await lastPageLink.TextContentAsync();
        return int.Parse(lastPageRaw);
    }

    public async Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/all-videos/page/{pageNumber}/");
        await Task.Delay(5000);
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var sceneHandles = await page.Locator("div.catposts div.half").ElementHandlesAsync();

        var indexScenes = new List<IndexScene>();
        foreach (var sceneHandle in sceneHandles.Reverse())
        {
            var sceneIdAndUrl = await GetSceneIdAsync(site, sceneHandle);
            indexScenes.Add(new IndexScene(null, sceneIdAndUrl.Id, sceneIdAndUrl.Url, sceneHandle));
        }

        return indexScenes.AsReadOnly();
    }

    private static async Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var link = await currentScene.QuerySelectorAsync("div.allvideostitle > a");
        var url = await link.GetAttributeAsync("href");
        var shortName = url.Replace(site.Url, "").Replace("/", "");
        return new SceneIdAndUrl(shortName, url);
    }

    public async Task<Scene> ScrapeSceneAsync(Guid sceneUuid, Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var releaseDateElement = await page.QuerySelectorAsync("div.durationandtime > div.entry-date");
        string releaseDateRaw = await releaseDateElement.TextContentAsync();
        releaseDateRaw = releaseDateRaw.Trim();
        DateOnly releaseDate = DateOnly.Parse(releaseDateRaw);

        var durationRaw = await page.Locator("div.durationandtime > div.duration").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("div.left-top-part h1").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var castElements = await page.Locator("div.tagsmodels > a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");
            var castId = castUrl.Replace($"{site.Url}/tag/", "").Replace("/", "");
            var castName = await castElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl));
        }

        var descriptionRaw = await page.Locator("div#fullstory").TextContentAsync();
        string pattern = @"\s*Read Less$";
        string description = Regex.Replace(descriptionRaw, pattern, "").Trim();

        var tagElements = await page.Locator("ul.post-categories a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Replace(site.Url + "/category/", "").Replace("/", "");
            var tagNameRaw = await tagElement.TextContentAsync();
            var tagName = tagNameRaw.Replace("\n", "").Trim();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        var scene = new Scene(
            sceneUuid,
            site,
            subSite,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            "{}",
            DateTime.Now);
        
        var ogImageMeta = await page.QuerySelectorAsync("meta[property='og:image']");
        string ogImageUrl = await ogImageMeta.GetAttributeAsync("content");

        try
        {
            await _downloader.DownloadSceneImageAsync(scene, ogImageUrl, scene.Url);
        }
        catch (Exception ex)
        {
            Log.Warning($"Could not download preview image: {ex}" );
        }
        
        return scene;
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var input = await page.EvaluateAsync<string>(@"
            Array.from(document.querySelectorAll('script'))
            .map(script => script.innerHTML)
            .find(content => content && content.includes('var playerInstance_'))
        ");
        var sources = ParseSources(input);

        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var fileSource in sources.FileSources)
        {
            var description = fileSource.Resolution;
            var url = fileSource.Url;

            var resolutionRaw = fileSource.Resolution.Replace(" ", "").Trim().ToUpperInvariant();

            var resolutionWidth = -1;
            var resolutionHeight = -1;

            if (resolutionRaw == "HD")
            {
                resolutionWidth = 1280;
                resolutionHeight = 720;
            }
            else if (resolutionRaw == "FULLHD" || resolutionRaw == "FULLDH")
            {
                resolutionWidth = 1920;
                resolutionHeight = 1080;
            }
            else if (resolutionRaw == "4K")
            {
                resolutionWidth = 3840;
                resolutionHeight = 2160;
            }

            if (resolutionWidth == -1)
            {
                throw new Exception("Could not parse resolutionWidth");
            }

            if (resolutionHeight == -1)
            {
                throw new Exception("Could not parse resolutionHeight");
            }

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        -1,
                        -1,
                        string.Empty,
                        url),
                    null));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.ResolutionHeight).ToList();
    }

    private static Sources ParseSources(string input)
    {
        var sourcesRegex = new Regex(@"sources:\s*\[(.*?)\]", RegexOptions.Singleline);
        var sourcesMatch = sourcesRegex.Match(input);
        if (sourcesMatch.Success)
        {
            string sourcesContent = sourcesMatch.Groups[1].Value;
            // Wrap property names with double quotes and fix extra double quotes in URLs
            string sourcesJson = Regex.Replace(sourcesContent, @"(\w+):\s*""", "\"$1\": \"");
            // Remove trailing comma if present
            sourcesJson = Regex.Replace(sourcesJson.Trim(), @",\s*$", "");
            // Wrap the entire JSON string with the "sources" property name
            sourcesJson = "{\"sources\": [" + sourcesJson + "]}";
            return JsonSerializer.Deserialize<Sources>(sourcesJson);
        }

        return new Sources { FileSources = new List<FileSource>() };
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        var cookies = await page.Context.CookiesAsync();


        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        string cookieString = string.Join("; ", cookies.Select(c => $"{c.Name}={c.Value}"));

        var headers = new Dictionary<HttpRequestHeader, string>
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };

        return await _downloader.DownloadSceneDirectAsync(scene, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url);
    }
}
