using System.Net;
using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.Json;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Xabe.FFmpeg;

namespace CultureExtractor.Sites;

[Site("brazzers")]
[Site("digitalplayground")]
[Site("realitykings")]
public class AyloRipper : IYieldingScraper
{
    private static readonly HttpClient Client = new();

    private readonly IDownloader _downloader;
    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly IRepository _repository;
    private readonly ICultureExtractorContext _context;

    private static string ScenesUrl(Site site, int pageNumber) =>
        $"{site.Url}/scenes?page={pageNumber}";

    private static string MoviesApiUrl(int pageNumber) =>
        $"https://site-api.project1service.com/v2/releases?blockId=4126598482&blockName=SceneListBlock&pageType=EXPLORE_SCENES&dateReleased=%3C2023-11-16&orderBy=-dateReleased&type=scene&limit=20&offset={(pageNumber - 1) * 20}";

    private static string MovieApiUrl(string shortName) =>
        $"https://site-api.project1service.com/v2/releases/{shortName}?pageType=PLAYER";

    public AyloRipper(IDownloader downloader, IPlaywrightFactory playwrightFactory, IRepository repository, ICultureExtractorContext context)
    {
        _downloader = downloader;
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _context = context;
    }

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);

        var requests = await CaptureRequestsAsync(site, page);

        SetHeadersFromActualRequest(requests);
        await foreach (var scene in ScrapeScenesAsync(site, scrapeOptions))
        {
            yield return scene;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, ScrapeOptions scrapeOptions)
    {
        var moviesInitialPage = await GetMoviesPageAsync(1);

        var pages = (int)Math.Ceiling((double)moviesInitialPage.meta.total / moviesInitialPage.meta.count);
        for (var pageNumber = 1; pageNumber <= pages; pageNumber++)
        {
            await Task.Delay(5000);

            var moviesPage = await GetMoviesPageAsync(pageNumber);

            Log.Information($"Page {pageNumber}/{pages} contains {moviesPage.result.Length} releases");

            var movies = moviesPage.result
                .ToDictionary(r => r.id.ToString(), r => r);

            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, movies.Keys.ToList());

            var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);
            
            var moviesToBeScraped = movies
                .Where(g => !existingReleasesDictionary.ContainsKey(g.Key) || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated)
                .Select(g => g.Value)
                .ToList();

            foreach (var movie in moviesToBeScraped)
            {
                await Task.Delay(1000);
                var shortName = movie.id.ToString();
                var scene = await ScrapeSceneAsync(site, shortName, existingReleasesDictionary);
                yield return scene;
            }
        }
    }

    private static async Task<Release> ScrapeSceneAsync(Site site, string shortName, Dictionary<string, Release> existingReleasesDictionary)
    {
        var movieUrl = MovieApiUrl(shortName);

        using var movieResponse = Client.GetAsync(movieUrl);
        if (movieResponse.Result.StatusCode != HttpStatusCode.OK)
        {
            throw new InvalidOperationException($"Could not read movie API response:{Environment.NewLine}Url={movieUrl}{Environment.NewLine}StatusCode={movieResponse.Result.StatusCode}{Environment.NewLine}ReasonPhrase={movieResponse.Result.ReasonPhrase}");
        }

        var movieJson = await movieResponse.Result.Content.ReadAsStringAsync();
        var movieDetailsContainer = JsonSerializer.Deserialize<AyloMovieRequest.RootObject>(movieJson);
        if (movieDetailsContainer == null)
        {
            throw new InvalidOperationException("Could not read movie API response: " + movieJson);
        }

        var movieDetails = movieDetailsContainer.result;
        if (movieDetails.videos.full == null)
        {
            throw new InvalidOperationException("Login required.");
        }
        
        var sceneDownloads = movieDetails.videos.full.files
            .Where(keyValuePair => keyValuePair.Key != "dash" && keyValuePair.Key != "hls")
            .Select(keyValuePair => new AvailableVideoFile(
                "video",
                "scene",
                keyValuePair.Key,
                keyValuePair.Value.urls.view,
                -1,
                HumanParser.ParseResolutionHeight(keyValuePair.Key),
                keyValuePair.Value.sizeBytes,
                -1,
                string.Empty
            ))
            .OrderByDescending(availableFile => availableFile.ResolutionHeight)
            .ToList();

        var imageDownloads = new List<AyloMoviesRequest.PosterSizes?>
            {
                movieDetails.images.poster._0,
                movieDetails.images.poster._1,
                movieDetails.images.poster._2,
                movieDetails.images.poster._3,
                movieDetails.images.poster._4,
                movieDetails.images.poster._5
            }
            .Where(posterSizes => posterSizes?.xx != null)
            .Select(posterSizes => posterSizes.xx)
            .Select((image, index) => new AvailableImageFile(
                "image",
                $"poster_xx_{index}",
                string.Empty,
                image.urls.default1,
                image.width,
                image.height,
                -1
            ))
            .ToList();

        var trailerDownloads = movieDetails.videos.mediabook.files
            .Select(keyValuePair =>
                new AvailableVideoFile("video", "trailer", keyValuePair.Key, keyValuePair.Value.urls.view, -1,
                    HumanParser.ParseResolutionHeight(keyValuePair.Value.format), keyValuePair.Value.sizeBytes, -1,
                    string.Empty)
            );

        var performers = movieDetails.actors.Where(a => a.gender == "female").ToList()
            .Concat(movieDetails.actors.Where(a => a.gender != "female").ToList())
            .Select(m => new SitePerformer(m.id.ToString(), m.name, string.Empty))
            .ToList();

        var tags = movieDetails.tags
            .Select(t => new SiteTag(t.id.ToString(), t.name, string.Empty))
            .ToList();

        var scene = new Release(
            existingReleasesDictionary.TryGetValue(shortName, out var existingRelease)
                ? existingRelease.Uuid
                : UuidGenerator.Generate(),
            site,
            null,
            DateOnly.FromDateTime(DateTime.Parse(movieDetails.dateReleased)),
            shortName,
            movieDetails.title,
            $"{site.Url}/scene/{movieDetails.id}",
            movieDetails.description ?? string.Empty,
            -1,
            performers,
            tags,
            new List<IAvailableFile>()
                .Concat(sceneDownloads)
                .Concat(imageDownloads)
                .Concat(trailerDownloads),
            movieJson,
            DateTime.Now);
        return scene;
    }

    private static async Task<AyloMoviesRequest.RootObject> GetMoviesPageAsync(int pageNumber)
    {
        var moviesApiUrl = MoviesApiUrl(pageNumber);

        using var response = await Client.GetAsync(moviesApiUrl);
        if (response.StatusCode != HttpStatusCode.OK)
        {
            throw new InvalidOperationException($"Could not read movies API response:{Environment.NewLine}Url={moviesApiUrl}{Environment.NewLine}StatusCode={response.StatusCode}{Environment.NewLine}ReasonPhrase={response.ReasonPhrase}");
        }
        
        var json = await response.Content.ReadAsStringAsync();
        var movies = JsonSerializer.Deserialize<AyloMoviesRequest.RootObject>(json);
        if (movies == null)
        {
            throw new InvalidOperationException("Could not read movies API response: " + json);
        }
        
        return movies;
    }

    private static Dictionary<string, string> SetHeadersFromActualRequest(IList<IRequest> requests)
    {
        var galleriesRequest = requests.SingleOrDefault(r => r.Url.StartsWith("https://site-api.project1service.com/v2/releases?"));
        if (galleriesRequest == null)
        {
            var requestUrls = requests.Select(r => r.Url + Environment.NewLine).ToList();
            throw new InvalidOperationException($"Could not read galleries API request from following requests:{Environment.NewLine}{string.Join("", requestUrls)}");
        }
        
        Client.DefaultRequestHeaders.Clear();
        foreach (var key in galleriesRequest.Headers.Keys)
        {
            Client.DefaultRequestHeaders.Add(key, galleriesRequest.Headers[key]);
        }
        
        return galleriesRequest.Headers;
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings,
        DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);
        var requests = await CaptureRequestsAsync(site, page);

        var headers = SetHeadersFromActualRequest(requests);
        var convertedHeaders = ConvertHeaders(headers);

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        foreach (var release in releases)
        {
            Log.Information("Downloading {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);

            // this is now done on every scene despite we might already have all files
            // the reason for updated scrape is that the links are timebombed and we need to refresh those
            Release? updatedScrape;
            try
            {
                updatedScrape = await ScrapeSceneAsync(site, release.ShortName,
                    new Dictionary<string, Release> { { release.ShortName, release } });
            }
            catch (Exception ex)
            {
                Log.Warning(ex, "Could not scrape {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                continue;
            }

            var existingDownloadEntities = await _context.Downloads.Where(d => d.ReleaseUuid == release.Uuid).ToListAsync();
            foreach (var videoDownload in await DownloadsVideosAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
            {
                yield return videoDownload;
            }
            await foreach (var trailerDownload in DownloadTrailersAsync(downloadConditions, updatedScrape, existingDownloadEntities))
            {
                yield return trailerDownload;
            }
            await foreach (var imageDownload in DownloadImagesAsync(updatedScrape, existingDownloadEntities, convertedHeaders))
            {
                yield return imageDownload;
            }
        }
    }

    private async Task<IList<Download>> DownloadsVideosAsync(DownloadConditions downloadConditions, Release release,
        List<DownloadEntity> existingDownloadEntities, WebHeaderCollection convertedHeaders)
    {
        var availableVideos = release.AvailableFiles.OfType<AvailableVideoFile>().Where(d => d is { FileType: "video", ContentType: "scene" });
        var selectedVideo = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableVideos.FirstOrDefault()
            : availableVideos.LastOrDefault();
        if (selectedVideo == null || !NotDownloadedYet(existingDownloadEntities, selectedVideo))
        {
            return new List<Download>();
        }

        var uri = new Uri(selectedVideo.Url);
        var suggestedFileName = Path.GetFileName(uri.LocalPath);
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.Variant);

        var fileInfo = await _downloader.TryDownloadAsync(release, selectedVideo, selectedVideo.Url, fileName, convertedHeaders);
        if (fileInfo == null)
        {
            return new List<Download>();
        }

        var videoHashes = Hasher.Phash(@"""" + fileInfo.FullName + @"""");
        return new List<Download>
        {
            new(release, suggestedFileName, fileInfo.Name, selectedVideo, videoHashes)
        };
    }
    
    private async IAsyncEnumerable<Download> DownloadTrailersAsync(DownloadConditions downloadConditions, Release release, List<DownloadEntity> existingDownloadEntities)
    {
        var availableTrailers = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "trailer" });
        var selectedTrailer = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableTrailers.FirstOrDefault()
            : availableTrailers.LastOrDefault();
        if (selectedTrailer == null  || !NotDownloadedYet(existingDownloadEntities, selectedTrailer))
        {
            yield break;
        }

        var trailerPlaylistFileName = $"trailer_{selectedTrailer.Variant}.m3u8";
        var trailerVideoFileName = $"trailer_{selectedTrailer.Variant}.mp4";

        // Note: we need to download the trailer without cookies because logged in users get the full scene
        // from the same URL.
        var fileInfo = await _downloader.TryDownloadAsync(release, selectedTrailer, selectedTrailer.Url, trailerPlaylistFileName, new WebHeaderCollection());
        if (fileInfo == null)
        {
            yield break;
        }
        
        var trailerVideoFullPath = Path.Combine(fileInfo.DirectoryName, trailerVideoFileName);

        var snippet = await FFmpeg.Conversions.New()
            .Start(
                $"-protocol_whitelist \"file,http,https,tcp,tls\" -i \"{fileInfo.FullName}\" -y -c copy \"{trailerVideoFullPath}\"");

        var videoHashes = Hasher.Phash(@"""" + trailerVideoFullPath + @"""");
        yield return new Download(release,
            trailerPlaylistFileName,
            trailerVideoFileName,
            selectedTrailer,
            videoHashes);
    }
    
    private async IAsyncEnumerable<Download> DownloadImagesAsync(Release release, List<DownloadEntity> existingDownloadEntities, WebHeaderCollection convertedHeaders)
    {
        var imageFiles = release.AvailableFiles.OfType<AvailableImageFile>();
        foreach (var imageFile in imageFiles)
        {
            if (!NotDownloadedYet(existingDownloadEntities, imageFile))
            {
                continue;
            }
            
            var fileName = $"{imageFile.ContentType}.jpg";
            var fileInfo = await _downloader.TryDownloadAsync(release, imageFile, imageFile.Url, fileName, convertedHeaders);
            if (fileInfo == null)
            {
                yield break;
            }
            
            var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
            var metadata = new ImageFileMetadata(sha256Sum);
            yield return new Download(release, $"{imageFile.ContentType}.jpg", fileInfo.Name, imageFile, metadata);
        }
    }
    
    private static bool NotDownloadedYet(List<DownloadEntity> existingDownloadEntities, IAvailableFile bestVideo)
    {
        return !existingDownloadEntities.Exists(d => d.FileType == bestVideo.FileType && d.ContentType == bestVideo.ContentType && d.Variant == bestVideo.Variant);
    }

    private async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var usernameInput = page.GetByPlaceholder("Username or Email");
        if (await usernameInput.IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username or Email").ClickAsync();
            await page.GetByPlaceholder("Username or Email").FillAsync(site.Username);

            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
            await page.WaitForLoadStateAsync();

            await Task.Delay(5000);

            if (await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).IsVisibleAsync())
            {
                await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
                await page.WaitForLoadStateAsync();
            }
        }
        
        if (page.Url.Contains("badlogin"))
        {
            Log.Warning("Could not log into {Site} due to badlogin error. Login manually!", site.Name);
            Console.ReadLine();
        }
        
        await Task.Delay(5000);

        await page.GotoAsync(site.Url);

        Log.Information($"Logged into {site.Name}.");
        
        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
    }

    private static async Task<List<IRequest>> CaptureRequestsAsync(Site site, IPage page)
    {
        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });

        await page.GotoAsync(ScenesUrl(site, 1));
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        await page.UnrouteAsync("**/*");
        return requests;
    }
    
    private static WebHeaderCollection ConvertHeaders(Dictionary<string, string> headers)
    {
        var convertedHeaders = new WebHeaderCollection();
        foreach (var header in headers)
        {
            convertedHeaders.Add(header.Key, header.Value);
        }
        return convertedHeaders;
    }
}
