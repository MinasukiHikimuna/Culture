using System.Net;
using Microsoft.Playwright;
using CultureExtractor.Interfaces;
using CultureExtractor.Exceptions;
using System.Text.Json;
using System.Text.RegularExpressions;
using CultureExtractor.Sites.MetArtIndexModels;
using CultureExtractor.Sites.MetArtSceneModels;
using CultureExtractor.Models;
using Serilog;
using UUIDNext;
using Xabe.FFmpeg;

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
public class MetArtNetworkRipper : ISiteScraper, IYieldingScraper
{
    private readonly IDownloader _downloader;
    private readonly IPlaywrightFactory _playwrightFactory;

    private static readonly HttpClient client = new HttpClient();
    private IRepository _repository;

    public MetArtNetworkRipper(IDownloader downloader, IPlaywrightFactory playwrightFactory, IRepository repository)
    {
        _downloader = downloader;
        _playwrightFactory = playwrightFactory;
        _repository = repository;
    }
    
    private string GalleriesUrl(int pageNumber) => $"/galleries/{pageNumber}";

    public async IAsyncEnumerable<Release> ScrapeAsync(Site site, BrowserSettings browserSettings)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);

        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });
        
        await page.GotoAsync(GalleriesUrl(1));

        var galleriesRequest = requests.SingleOrDefault(r => r.Url.StartsWith(site.Url + "/api/galleries?"));

        client.DefaultRequestHeaders.Clear();
        // get headers from galleriesrequest
        foreach (var key in galleriesRequest.Headers.Keys)
        {
            client.DefaultRequestHeaders.Add(key, galleriesRequest.Headers[key]);
        }

        using var response = client.GetAsync(galleriesRequest.Url);
        var contentJson = await response.Result.Content.ReadAsStringAsync();
        var content = JsonSerializer.Deserialize<MetArtGalleriesRequest.RootObject>(contentJson);

        var pages = (int) Math.Ceiling((double) content.total / content.galleries.Length);
        for (var pageNumber = 1; pageNumber <= pages; pageNumber++)
        {
            Thread.Sleep(5000);
            
            var galleriesPageUrl = $"{site.Url}/api/galleries?first=60&galleryType=GALLERY&page={pageNumber}&order=DATE&direction=DESC";
            
            using var galleriesPageResponse = client.GetAsync(galleriesPageUrl);
            var galleriesPageJson = await galleriesPageResponse.Result.Content.ReadAsStringAsync();
            var galleriesPage = JsonSerializer.Deserialize<MetArtGalleriesRequest.RootObject>(galleriesPageJson);

            Log.Information($"Page {pageNumber}/{pages} contains {galleriesPage.galleries.Length} releases");


            // find all instances from galleriesPage.galleries which shortName is not in the database
            // create a dictionary with short name as key and the gallery as the value
            var galleries = galleriesPage.galleries
                .Select((element, index)=> new{ element, index } )
                .ToDictionary(ele =>
                {
                    var date = Regex.Match(ele.element.path, @"\/(\d{8})\/").Groups[1].Value;
                    var name = Regex.Match(ele.element.path, @"\/(\w+)$").Groups[1].Value;                    
                    return $"{date}/{name}";
                }, ele=> ele.element);

            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, galleries.Keys.ToList());
            
            var existingShortNames = existingReleases.Select(r => r.ShortName).ToList();
            
            // Assuming existingReleases is a list or set of string keys.
            var nonExistingGalleries = galleries
                .Where(g => !existingShortNames.Contains(g.Key)) // Check if the gallery key is not in the list of existingShortNames
                .Select(g => g.Value) // Select the gallery element itself
                .ToList(); // Convert the result to a List

            
            foreach (var gallery in nonExistingGalleries)
            {
                Thread.Sleep(5000);
                
                var date = Regex.Match(gallery.path, @"\/(\d{8})\/").Groups[1].Value;
                var name = Regex.Match(gallery.path, @"\/(\w+)$").Groups[1].Value;

                var shortName = $"{date}/{name}";
                
                var galleryUrl = $"{site.Url}/api/gallery?name={name}&date={date}&page=1&mediaFirst=42";
                
                using var galleryResponse = client.GetAsync(galleryUrl);
                var galleryJson = await galleryResponse.Result.Content.ReadAsStringAsync();
                var galleryDetails = JsonSerializer.Deserialize<MetArtGalleryRequest.RootObject>(galleryJson);
                
                var galleryDownloads = galleryDetails.files.sizes.zips
                    .Select(gallery => new AvailableGalleryZipFile(
                        "zip",
                        "gallery",
                        gallery.quality,
                        $"/api/download-media/{galleryDetails.siteUUID}/photos/{gallery.quality}",
                        -1,
                        -1,
                        HumanParser.ParseFileSizeMaybe(gallery.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
                    ))
                    .OrderByDescending(availableFile => availableFile.ResolutionHeight)
                    .ToList();
        
                var imageDownloads = galleryDetails.files.sizes.relatedPhotos
                    .Select(image => new AvailableImageFile(
                        "image",
                        image.id,
                        string.Empty,
                        $"https://cdn.metartnetwork.com/{galleryDetails.siteUUID}/media/{galleryDetails.UUID}/{image.id.Replace("-", "_")}_{galleryDetails.UUID}.jpg",
                        -1,
                        -1,
                        HumanParser.ParseFileSizeMaybe(image.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
                    ))
                    .ToList();
                
                var performers = galleryDetails.models.Where(a => a.gender == "female").ToList()
                    .Concat(galleryDetails.models.Where(a => a.gender != "female").ToList())
                    .Select(m => new SitePerformer(m.path.Substring(m.path.LastIndexOf("/") + 1), m.name, m.path))
                    .ToList();

                var tags = galleryDetails.tags
                    .Select(t => new SiteTag(t.Replace(" ", "+"), t, "/tags/" + t.Replace(" ", "+")))
                    .ToList();
                
                var scene = new Release(
                    /*existingRelease?.Uuid ??*/ UuidGenerator.Generate(),
                    site,
                    null,
                    DateOnly.FromDateTime(galleryDetails.publishedAt),
                    shortName,
                    galleryDetails.name,
                    $"{site.Url}{galleryDetails.path}",
                    galleryDetails.description,
                    -1,
                    performers,
                    tags,
                    new List<IAvailableFile>()
                        .Concat(galleryDownloads)
                        .Concat(imageDownloads),
                    @"{""gallery"": " + galleryJson + "}",
                    DateTime.Now);

                yield return scene;
            }
        }
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

        var sceneDownloads = movieData.files.sizes.videos
            .Select(video => new AvailableVideoFile(
                "video",
                "scene",
                video.id,
                $"/api/download-media/{movieData.siteUUID}/film/{video.id}",
                -1,
                HumanParser.ParseResolutionHeight(video.id),
                HumanParser.ParseFileSizeMaybe(video.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1,
                -1,
                string.Empty
            ))
            .OrderByDescending(availableFile => availableFile.ResolutionHeight)
            .ToList();

        var galleryDownloads = movieData.files.sizes.zips
            .Select(gallery => new AvailableGalleryZipFile(
                "zip",
                "gallery",
                gallery.quality,
                $"/api/download-media/{movieData.siteUUID}/photos/{gallery.quality}",
                -1,
                -1,
                HumanParser.ParseFileSizeMaybe(gallery.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
            ))
            .OrderByDescending(availableFile => availableFile.ResolutionHeight)
            .ToList();
        
        var imageDownloads = movieData.files.sizes.relatedPhotos
            .Select(image => new AvailableImageFile(
                "image",
                image.id,
                string.Empty,
                $"https://cdn.metartnetwork.com/{movieData.siteUUID}/media/{movieData.UUID}/{image.id.Replace("-", "_")}_{movieData.UUID}.jpg",
                -1,
                -1,
                HumanParser.ParseFileSizeMaybe(image.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
            ))
            .ToList();

        var trailerDownloads = new List<IAvailableFile>()
        {
            new AvailableVideoFile("video", "trailer", string.Empty,
                $"https://www.sexart.com/api/m3u8/{movieData.UUID}/720.m3u8", -1, 720, -1, -1, "h264"),
            new AvailableVideoFile("video", "trailer", string.Empty,
                $"https://www.sexart.com/api/m3u8/{movieData.UUID}/270.m3u8", -1, 270, -1, -1, "h264"),
        };
        
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
            new List<IAvailableFile>()
                .Concat(sceneDownloads)
                .Concat(galleryDownloads)
                .Concat(imageDownloads)
                .Concat(trailerDownloads),
            @"{""movie"": " + movieJsonContent + @", ""comments"": " + commentsJsonContent + "}",
            DateTime.Now);

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
            PreferredDownloadQuality.Phash => availableDownloads.FirstOrDefault(f => f.AvailableVideoFile.ResolutionHeight == 360) ?? availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        foreach (var image in release.DownloadOptions.OfType<AvailableImageFile>())
        {
            var imageSuffix = Path.GetExtension(image.Url);
            await _downloader.DownloadSceneImageAsync(release, image.Url, fileName: $"{image.ContentType}{imageSuffix}");            
        }
        
        var fileInfo = await _downloader.DownloadFileAsync(
            release,
            release.DownloadOptions.OfType<AvailableVideoFile>().First(d => d.ContentType == "trailer").Url, 
            "trailer.m3u8");
        
        var snippet = await FFmpeg.Conversions.New().Start($"-protocol_whitelist \"file,http,https,tcp,tls\" -i {fileInfo.FullName} -c copy {Path.Combine(fileInfo.DirectoryName, "trailer.mp4")}");
        
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

        return await _downloader.DownloadSceneAsync(release, page, selectedDownload.AvailableVideoFile, downloadConditions.PreferredDownloadQuality, async () =>
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
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        description,
                        url,
                        -1,
                        HumanParser.ParseResolutionHeight(resolution),
                        HumanParser.ParseFileSize(size),
                        -1,
                        string.Empty),
                    downloadLink));
        }
        return availableDownloads;
    }

    private static async Task GoToPageAsync(IPage page, int pageNumber)
    {
        await page.GotoAsync($"/movies/{pageNumber}");
    }
}

public interface IYieldingScraper
{
    IAsyncEnumerable<Release> ScrapeAsync(Site site, BrowserSettings browserSettings);
}
