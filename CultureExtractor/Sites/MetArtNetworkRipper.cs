using Microsoft.Playwright;
using CultureExtractor.Interfaces;
using CultureExtractor.Exceptions;
using System.Text.Json;
using CultureExtractor.Sites.MetArtIndexModels;
using CultureExtractor.Sites.MetArtSceneModels;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

[PornNetwork("metart")]
[PornSite("metart")]
[PornSite("metartx")]
[PornSite("sexart")]
[PornSite("vivthomas")]
[PornSite("thelifeerotic")]
[PornSite("eternaldesire")]
[PornSite("straplez")]
[PornSite("hustler")]
public class MetArtNetworkRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public MetArtNetworkRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        if (await page.IsVisibleAsync(".sign-in"))
        {
            if (await page.Locator("#onetrust-accept-btn-handler").IsVisibleAsync())
            {
                await page.Locator("#onetrust-accept-btn-handler").ClickAsync();
            }

            await page.ClickAsync(".sign-in");
            await page.WaitForLoadStateAsync();

            await page.Locator("[name='email']").TypeAsync(site.Username);
            await page.Locator("[name='password']").TypeAsync(site.Password);
            await page.Locator("button[type='submit']").ClickAsync();
            await page.WaitForLoadStateAsync();
        }

        // Close the modal dialog if one is shown.
        try
        {
            await page.WaitForLoadStateAsync();
            if (await page.Locator(".close-btn").IsVisibleAsync())
            {
                await page.Locator(".close-btn").ClickAsync();
            }

            var modalClose = page.Locator("div.modal-content a.alt-close");
            if (await modalClose.IsVisibleAsync())
            {
                await modalClose.ClickAsync();
            }
        }
        catch (Exception ex)
        {
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        // Close the modal dialog if one is shown.
        try
        {
            await page.WaitForLoadStateAsync();
            if (await page.Locator(".close-btn").IsVisibleAsync())
            {
                await page.Locator(".close-btn").ClickAsync();
            }
            if (await page.Locator(".fa-times-circle").IsVisibleAsync())
            {
                await page.Locator(".fa-times-circle").ClickAsync();
            }
        }
        catch (Exception ex)
        {
        }

        await page.Locator("nav a[href='/movies']").ClickAsync();
        await page.WaitForLoadStateAsync();

        // Close the modal dialog if one is shown.
        try
        {
            await page.WaitForLoadStateAsync();
            if (await page.Locator(".close-btn").IsVisibleAsync())
            {
                await page.Locator(".close-btn").ClickAsync();
            }
            if (await page.Locator(".fa-times-circle").IsVisibleAsync())
            {
                await page.Locator(".fa-times-circle").ClickAsync();
            }
        }
        catch (Exception ex)
        {
        }

        var totalPagesStr = await page.Locator("nav.pagination > a:nth-child(5)").TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);

        return totalPages;
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var moviesRequest = requests.SingleOrDefault(r => r.Url.StartsWith(site.Url + "/api/movies?"));
        var response = await moviesRequest.ResponseAsync();
        var content = await response.TextAsync();
        var data = JsonSerializer.Deserialize<MetArtMovies>(content);

        var currentPage = page.Url.Substring(page.Url.LastIndexOf("/") + 1);
        var skipAdScene = currentPage == "1" && site.ShortName != "hustler";

        return data.galleries.Skip(skipAdScene ? 1 : 0)
            .Select(g => new IndexScene(null, g.path.Substring(g.path.LastIndexOf("/movie/") + "/movie/".Length + 1), g.path, null))
            .Reverse()
            .ToList()
            .AsReadOnly();
    }

    public async Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var url = await currentScene.GetAttributeAsync("href");
        var sceneShortName = url.Substring(url.LastIndexOf("/movie/") + "/movie/".Length + 1);
        return new SceneIdAndUrl(sceneShortName, url);
    }

    public async Task<CapturedResponse?> FilterResponsesAsync(string sceneShortName, IResponse response)
    {
        if (response.Url.Contains("/api/movie?name="))
        {
            return new CapturedResponse(Enum.GetName(AdultTimeRequestType.SceneMetadata)!, response);
        }

        return null;
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var apiRequests = requests.Where(r => r.Url.StartsWith(site.Url + "/api/movie?name="));

        var movieRequest = apiRequests.SingleOrDefault(r => r.Url.StartsWith(site.Url + "/api/movie?name="));
        if (movieRequest == null)
        {
            throw new Exception("Could not read movie API response.");
        }

        var movieResponse = await movieRequest.ResponseAsync();
        if (movieResponse.Status == 404)
        {
            throw new Exception("Got 404 for scene: " + url);
        }

        var movieJsonContent = await movieResponse.TextAsync();
        var movieData = JsonSerializer.Deserialize<MetArtSceneData>(movieJsonContent)!;

        var commentsRequest = apiRequests.SingleOrDefault(r => r.Url.StartsWith(site.Url + "/api/comments?"));
        if (commentsRequest == null)
        {
            throw new Exception("Could not read comments API response.");
        }

        var commentsResponse = await commentsRequest.ResponseAsync();
        var commentsJsonContent = await commentsResponse.TextAsync();

        var releaseDate = movieData.publishedAt;
        var duration = TimeSpan.FromSeconds(movieData.runtime);
        var description = movieData.description;
        var name = movieData.name;
        
        var performers = movieData.models.Where(a => a.gender == "female").ToList()
            .Concat(movieData.models.Where(a => a.gender != "female").ToList())
            .Select(m => new SitePerformer(m.path.Substring(m.path.LastIndexOf("/") + 1), m.name, m.path))
            .ToList();

        var tags = movieData.tags
            .Select(t => new SiteTag(t.Replace(" ", "+"), t, "/tags/" + t.Replace(" ", "+")))
            .ToList();

        var downloads = movieData.files.sizes.videos
            .Select(d => new DownloadOption(
                d.id,
                -1,
                HumanParser.ParseResolutionHeight(d.id),
                HumanParser.ParseFileSizeMaybe(d.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1,
                -1,
                string.Empty,
                $"/api/download-media/{movieData.siteUUID}/film/{d.id}"))
            .OrderByDescending(d => d.ResolutionHeight)
            .ToList();

        return new Scene(
            null,
            site,
            null,
            DateOnly.FromDateTime(releaseDate),
            sceneShortName,
            name,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloads,
            @"{""movie"": " + movieJsonContent + @", ""comments"": " + commentsJsonContent + "}",
            DateTime.Now); ;
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var data = JsonSerializer.Deserialize<MetArtSceneData>(scene.JsonDocument)!;
        await _downloader.DownloadSceneImageAsync(scene, scene.Site.Url + data.splashImagePath);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = ">" }).ClickAsync();
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        if (!requests.Any())
        {
            throw new Exception("Could not read API response.");
        }

        var movieRequest = requests.SingleOrDefault(r => r.Url.StartsWith(scene.Site.Url + "/api/movie?"));
        var response = await movieRequest.ResponseAsync();
        var jsonContent = await response.TextAsync();
        var data = JsonSerializer.Deserialize<MetArtSceneData>(jsonContent)!;

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.FirstOrDefault(f => f.DownloadOption.ResolutionHeight == 360) ?? availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        IPage newPage = await page.Context.NewPageAsync();

        var genderSorted = data.models.Where(a => a.gender == "female").ToList().Concat(data.models.Where(a => a.gender != "female").ToList()).ToList().Select(a => a.name).ToList();
        var performersStr = genderSorted.Count() > 1
            ? string.Join(", ", genderSorted.SkipLast(1)) + " & " + genderSorted.Last()
            : genderSorted.FirstOrDefault();

        if (string.IsNullOrWhiteSpace(performersStr))
        {
            performersStr = "Unknown";
        }

        var nameWithoutSuffix =
            string.Concat(
                Regex.Replace(
                    $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}",
                    @"\s+",
                    " "
                ).Split(Path.GetInvalidFileNameChars()));

        var suffix = ".mp4";
        var name = (nameWithoutSuffix + suffix).Length > 244
            ? nameWithoutSuffix[..(244 - suffix.Length - "...".Length)] + "..." + suffix
            : nameWithoutSuffix + suffix;

        return await _downloader.DownloadSceneAsync(scene, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            await selectedDownload.ElementHandle.ClickAsync();
        }, name);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadMenuLocator = page.Locator("div svg.fa-film");
        if (!await downloadMenuLocator.IsVisibleAsync())
        {
            throw new DownloadException(false, $"Could not find download menu for {page.Url}. Skipping...");
        }

        await downloadMenuLocator.ClickAsync();

        var downloadLinks = await page.Locator("div.dropdown-menu a").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var description = await downloadLink.InnerTextAsync();
            var sizeElement = await downloadLink.QuerySelectorAsync("span.pull-right");
            var size = await sizeElement.TextContentAsync();
            var resolution = description.Replace(size, "");
            var url = await downloadLink.GetAttributeAsync("href");
            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        -1,
                        HumanParser.ParseResolutionHeight(resolution),
                        HumanParser.ParseFileSize(size),
                        -1,
                        string.Empty,
                        url),
                    downloadLink));
        }
        return availableDownloads;
    }

    public async Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/movies/{pageNumber}");
    }
}
