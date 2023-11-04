using Microsoft.Playwright;
using CultureExtractor.Interfaces;
using CultureExtractor.Exceptions;
using System.Text.Json;
using CultureExtractor.Sites.MetArtIndexModels;
using CultureExtractor.Sites.MetArtSceneModels;
using System.Text.RegularExpressions;
using System;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[PornSite("metart")]
[PornSite("metartx")]
[PornSite("sexart")]
[PornSite("lovehairy")]
[PornSite("vivthomas")]
[PornSite("alsscan")]
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

            await page.Locator("[name='email']").FillAsync(site.Username);
            await page.Locator("[name='password']").FillAsync(site.Password);
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

        await Task.Delay(5000);
        
        var element = page.GetByRole(AriaRole.Link, new() { Name = "Continue to SexArt" }).Nth(1);
        if (await element.IsVisibleAsync())
        {
            await element.ClickAsync();
        }
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await CloseModalsIfVisibleAsync(page);

        await page.Locator("nav a[href='/movies']").ClickAsync();
        await page.WaitForLoadStateAsync();

        await CloseModalsIfVisibleAsync(page);

        var totalPagesStr = await page.Locator("nav.pagination > a:nth-last-child(2)").TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);

        return totalPages;
    }

    private async Task CloseModalsIfVisibleAsync(IPage page)
    {
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
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, pageNumber);
        
        var moviesRequest = requests.SingleOrDefault(r => r.Url.StartsWith(site.Url + "/api/movies?"));
        var response = await moviesRequest.ResponseAsync();
        var content = await response.TextAsync();
        var data = JsonSerializer.Deserialize<MetArtMovies>(content);

        var currentPage = page.Url.Substring(page.Url.LastIndexOf("/") + 1);
        var skipAdScene = currentPage == "1" && site.ShortName != "hustler";

        return data.galleries.Skip(skipAdScene ? 1 : 0)
            .Select(g => new ListedRelease(null, g.path.Substring(g.path.LastIndexOf("/movie/") + "/movie/".Length + 1), g.path, null))
            .Reverse()
            .ToList()
            .AsReadOnly();
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        await CloseModalsIfVisibleAsync(page);

        var apiRequests = requests.Where(r => r.Url.StartsWith(site.Url + "/api/"));

        var movieRequest = apiRequests.SingleOrDefault(r => r.Url.StartsWith(site.Url + "/api/movie?name="));
        if (movieRequest == null)
        {
            throw new Exception("Could not read movie API response.");
        }

        var movieResponse = await movieRequest.ResponseAsync();
        if (movieResponse.Status == 404)
        {
            throw new ExtractorException(false, "Got 404 for scene: " + url);
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

        var scene = new Release(
            releaseUuid,
            site,
            null,
            DateOnly.FromDateTime(releaseDate),
            releaseShortName,
            name,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloads,
            @"{""movie"": " + movieJsonContent + @", ""comments"": " + commentsJsonContent + "}",
            DateTime.Now);

        await _downloader.DownloadSceneImageAsync(scene, scene.Site.Url + movieData.splashImagePath);

        return scene;
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        await CloseModalsIfVisibleAsync(page);

        if (!requests.Any())
        {
            throw new Exception("Could not read API response.");
        }

        var movieRequest = requests.SingleOrDefault(r => r.Url.StartsWith(release.Site.Url + "/api/movie?"));
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

        var females = data.models.Where(a => a.gender == "female").ToList();
        var nonFemales = data.models.Where(a => a.gender != "female").ToList();
        var genderSorted = females.Concat(nonFemales)
            .ToList()
            .Select(a => a.name)
            .ToList();
        var performersStr = genderSorted.Count > 1
            ? string.Join(", ", genderSorted.SkipLast(1)) + " & " + genderSorted.Last()
            : genderSorted.FirstOrDefault();

        if (string.IsNullOrWhiteSpace(performersStr))
        {
            performersStr = "Unknown";
        }

        const string suffix = ".mp4";
        var name = ReleaseNamer.Name(release, suffix, performersStr);

        return await _downloader.DownloadSceneAsync(release, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            await selectedDownload.ElementHandle.ClickAsync();
        }, name);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadMenuLocator = page.Locator("div svg.fa-film");
        if (!await downloadMenuLocator.IsVisibleAsync())
        {
            throw new ExtractorException(false, $"Could not find download menu for {page.Url}. Skipping...");
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

    private static async Task GoToPageAsync(IPage page, int pageNumber)
    {
        await page.GotoAsync($"/movies/{pageNumber}");
    }
}
