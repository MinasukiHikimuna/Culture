using System.Net;
using Microsoft.Playwright;
using CultureExtractor.Interfaces;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Web;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Serilog;
using Xabe.FFmpeg;

namespace CultureExtractor.Sites;

[Site("metart")]
[Site("metartx")]
[Site("sexart")]
[Site("lovehairy")]
[Site("vivthomas")]
[Site("alsscan")]
[Site("thelifeerotic")]
[Site("eternaldesire")]
[Site("straplez")]
[Site("hustler")]
public class MetArtNetworkRipper : IYieldingScraper
{
    private readonly IDownloader _downloader;
    private readonly IPlaywrightFactory _playwrightFactory;

    private static readonly HttpClient Client = new();
    private readonly IRepository _repository;
    private readonly ICultureExtractorContext _context;

    public MetArtNetworkRipper(IDownloader downloader, IPlaywrightFactory playwrightFactory, IRepository repository, ICultureExtractorContext context)
    {
        _downloader = downloader;
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _context = context;
    }
    
    private static string GalleriesUrl(Site site, int pageNumber) =>
        $"{site.Url}/galleries/{pageNumber}";
    private static string GalleriesApiUrl(Site site, int pageNumber) =>
        $"{site.Url}/api/galleries?first=60&galleryType=GALLERY&page={pageNumber}&order=DATE&direction=DESC";
    private static string GalleryApiUrl(Site site, string date, string name) =>
        $"{site.Url}/api/gallery?name={name}&date={date}&page=1&mediaFirst=42";
    private static string MoviesApiUrl(Site site, int pageNumber) =>
        $"{site.Url}/api/movies?galleryType=MOVIE&first=60&page={pageNumber}&showPinnedGallery=false&tabId=0&order=DATE&direction=DESC&type=MOVIE";
    private static string MovieApiUrl(Site site, string date, string name) =>
        $"{site.Url}/api/movie?name={name}&date={date}";
    private static string CommentsApiUrl(Site site, string releaseUuid) =>
        $"{site.Url}/api/comments?objectUUID={releaseUuid}&order=TIMESTAMP&direction=DESC";
    private static string GalleryCdnImageUrl(MetArtGalleryRequest.RootObject gallery, MetArtGalleryRequest.RelatedPhotos image) =>
        $"https://cdn.metartnetwork.com/{gallery.siteUUID}/media/{gallery.UUID}/{image.id.Replace("-", "_")}_{gallery.UUID}.jpg";
    private static string MovieCdnImageUrl(MetArtMovieRequest.RootObject gallery, MetArtMovieRequest.RelatedPhotos image) =>
        $"https://cdn.metartnetwork.com/{gallery.siteUUID}/media/{gallery.UUID}/{image.id.Replace("-", "_")}_{gallery.UUID}.jpg";

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);
        var requests = await CaptureRequestsAsync(site, page);
        
        SetHeadersFromActualRequest(site, requests);

        await foreach (var gallery in ScrapeGalleriesAsync(site, scrapeOptions))
        {
            yield return gallery;
        }
        await foreach (var scene in ScrapeScenesAsync(site, scrapeOptions))
        {
            yield return scene;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeGalleriesAsync(Site site, ScrapeOptions scrapeOptions)
    {
        var galleriesInitialPage = await GetGalleriesPageAsync(site, 1);

        var pages = (int)Math.Ceiling((double)galleriesInitialPage.total / galleriesInitialPage.galleries.Length);
        for (var pageNumber = 1; pageNumber <= pages; pageNumber++)
        {
            await Task.Delay(5000);

            var galleriesPage = await GetGalleriesPageAsync(site, pageNumber);

            Log.Information($"Page {pageNumber}/{pages} contains {galleriesPage.galleries.Length} releases");

            var galleries = galleriesPage.galleries
                .Select((element, index) => new { element, index })
                .ToDictionary(ele =>
                {
                    var date = Regex.Match(ele.element.path, @"\/(\d{8})\/").Groups[1].Value;
                    var name = Regex.Match(ele.element.path, @"\/(\w+)$").Groups[1].Value;
                    return $"{date}/{name}";
                }, ele => ele.element);

            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, galleries.Keys.ToList());

            var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);

            List<MetArtGalleriesRequest.Galleries> galleriesToBeScraped;
            if (scrapeOptions.FullScrape)
            {
                // If FullScrape is true, take all galleries
                galleriesToBeScraped = galleries.Values.ToList();
            }
            else
            {
                // If FullScrape is false, filter out existing galleries
                galleriesToBeScraped = galleries
                    .Where(g => !existingReleasesDictionary.ContainsKey(g.Key))
                    .Select(g => g.Value)
                    .ToList();
            }

            foreach (var gallery in galleriesToBeScraped)
            {
                await Task.Delay(1000);

                var date = Regex.Match(gallery.path, @"\/(\d{8})\/").Groups[1].Value;
                var name = Regex.Match(gallery.path, @"\/(\w+)$").Groups[1].Value;

                var shortName = $"{date}/{name}";

                var galleryUrl = GalleryApiUrl(site, date, name);

                using var galleryResponse = Client.GetAsync(galleryUrl);
                var galleryJson = await galleryResponse.Result.Content.ReadAsStringAsync();
                var galleryDetails = JsonSerializer.Deserialize<MetArtGalleryRequest.RootObject>(galleryJson);
                if (galleryDetails == null)
                {
                    throw new InvalidOperationException("Could not read gallery API response: " + galleryJson);
                }
                
                var commentsUrl = CommentsApiUrl(site, galleryDetails.UUID);

                using var commentResponse = Client.GetAsync(commentsUrl);
                var commentsJson = await commentResponse.Result.Content.ReadAsStringAsync();

                var galleryDownloads = galleryDetails.files.sizes.zips
                    .Select(g => new AvailableGalleryZipFile(
                        "zip",
                        "gallery",
                        g.quality,
                        $"{site.Url}/api/download-media/{galleryDetails.UUID}/photos/{g.quality}",
                        -1,
                        -1,
                        HumanParser.ParseFileSizeMaybe(g.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
                    ))
                    .OrderByDescending(availableFile => availableFile.ResolutionHeight)
                    .ToList();

                var imageDownloads = galleryDetails.files.sizes.relatedPhotos
                    .Select(image => new AvailableImageFile(
                        "image",
                        image.id,
                        string.Empty,
                        GalleryCdnImageUrl(galleryDetails, image),
                        -1,
                        -1,
                        HumanParser.ParseFileSizeMaybe(image.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
                    ))
                    .ToList();

                var performers = galleryDetails.models.Where(a => a.gender == "female").ToList()
                    .Concat(galleryDetails.models.Where(a => a.gender != "female").ToList())
                    .Select(m => new SitePerformer(m.path[(m.path.LastIndexOf("/", StringComparison.Ordinal) + 1)..], m.name, m.path))
                    .ToList();

                var tags = galleryDetails.tags
                    .Select(t => new SiteTag(t.Replace(" ", "+"), t, "/tags/" + t.Replace(" ", "+")))
                    .ToList();

                var scene = new Release(
                    existingReleasesDictionary.TryGetValue(shortName, out var existingRelease)
                        ? existingRelease.Uuid
                        : UuidGenerator.Generate(),
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
                    $$"""{"gallery": """ + galleryJson + """, "comments": """ + commentsJson + "}",
                    DateTime.Now);

                yield return scene;
            }
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, ScrapeOptions scrapeOptions)
    {
        var moviesInitialPage = await GetMoviesPageAsync(site, 1);

        var pages = (int)Math.Ceiling((double)moviesInitialPage.total / moviesInitialPage.galleries.Length);
        for (var pageNumber = 1; pageNumber <= pages; pageNumber++)
        {
            await Task.Delay(5000);

            var moviesPage = await GetMoviesPageAsync(site, pageNumber);

            Log.Information($"Page {pageNumber}/{pages} contains {moviesPage.galleries.Length} releases");

            var movies = moviesPage.galleries
                .Select((element, index) => new { element, index })
                .ToDictionary(ele =>
                {
                    var date = Regex.Match(ele.element.path, @"\/(\d{8})\/").Groups[1].Value;
                    var name = Regex.Match(ele.element.path, @"\/(\w+)$").Groups[1].Value;
                    return $"{date}/{name}";
                }, ele => ele.element);

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

                var date = Regex.Match(movie.path, @"\/(\d{8})\/").Groups[1].Value;
                var name = Regex.Match(movie.path, @"\/(\w+)$").Groups[1].Value;

                var shortName = $"{date}/{name}";

                var movieUrl = MovieApiUrl(site, date, name);

                using var movieResponse = Client.GetAsync(movieUrl);
                var movieJson = await movieResponse.Result.Content.ReadAsStringAsync();
                var movieDetails = JsonSerializer.Deserialize<MetArtMovieRequest.RootObject>(movieJson);
                if (movieDetails == null)
                {
                    throw new InvalidOperationException("Could not read movie API response: " + movieJson);
                }

                var commentsUrl = CommentsApiUrl(site, movieDetails.UUID);

                using var commentResponse = Client.GetAsync(commentsUrl);
                var commentsJson = await commentResponse.Result.Content.ReadAsStringAsync();

                var sceneDownloads = movieDetails.files.sizes.videos
                    .Select(video => new AvailableVideoFile(
                        "video",
                        "scene",
                        video.id,
                        $"{site.Url}/api/download-media/{movieDetails.UUID}/film/{video.id}",
                        -1,
                        HumanParser.ParseResolutionHeight(video.id),
                        HumanParser.ParseFileSizeMaybe(video.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1,
                        -1,
                        string.Empty
                    ))
                    .OrderByDescending(availableFile => availableFile.ResolutionHeight)
                    .ToList();
                
                var galleryDownloads = movieDetails.files.sizes.zips
                    .Select(gallery => new AvailableGalleryZipFile(
                        "zip",
                        "gallery",
                        gallery.quality,
                        $"{site.Url}/api/download-media/{movieDetails.UUID}/photos/{gallery.quality}",
                        -1,
                        -1,
                        HumanParser.ParseFileSizeMaybe(gallery.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
                    ))
                    .OrderByDescending(availableFile => availableFile.ResolutionHeight)
                    .ToList();

                var imageDownloads = movieDetails.files.sizes.relatedPhotos
                    .Select(image => new AvailableImageFile(
                        "image",
                        image.id,
                        string.Empty,
                        MovieCdnImageUrl(movieDetails, image),
                        -1,
                        -1,
                        HumanParser.ParseFileSizeMaybe(image.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1
                    ))
                    .ToList();

                var trailerDownloads = movieDetails.files.teasers.Length > 0 
                    ? new List<IAvailableFile>
                    {
                        new AvailableVideoFile("video", "trailer", "720",
                            $"https://www.sexart.com/api/m3u8/{movieDetails.UUID}/720.m3u8", -1, 720, -1, -1, "h264"),
                        new AvailableVideoFile("video", "trailer", "270",
                            $"https://www.sexart.com/api/m3u8/{movieDetails.UUID}/270.m3u8", -1, 270, -1, -1, "h264"),
                    }
                    : new List<IAvailableFile>();

                var spriteDownloads = new List<IAvailableFile>
                {
                    new AvailableImageFile("image", "sprite", string.Empty,
                        $"https://cdn.metartnetwork.com/{movieDetails.siteUUID}/media/{movieDetails.UUID}/sprite_{movieDetails.UUID}-48.jpg",
                        -1, -1, -1),
                    new AvailableVttFile("vtt", "sprite", string.Empty,
                        $"https://cdn.metartnetwork.com/{movieDetails.siteUUID}/media/{movieDetails.UUID}/member_{movieDetails.UUID}.vtt")
                };
                
                var performers = movieDetails.models.Where(a => a.gender == "female").ToList()
                    .Concat(movieDetails.models.Where(a => a.gender != "female").ToList())
                    .Select(m => new SitePerformer(m.path[(m.path.LastIndexOf("/", StringComparison.Ordinal) + 1)..], m.name, m.path))
                    .ToList();

                var tags = movieDetails.tags
                    .Select(t => new SiteTag(t.Replace(" ", "+"), t, "/tags/" + t.Replace(" ", "+")))
                    .ToList();

                var scene = new Release(
                    existingReleasesDictionary.TryGetValue(shortName, out var existingRelease)
                        ? existingRelease.Uuid
                        : UuidGenerator.Generate(),
                    site,
                    null,
                    DateOnly.FromDateTime(movieDetails.publishedAt),
                    shortName,
                    movieDetails.name,
                    $"{site.Url}{movieDetails.path}",
                    movieDetails.description,
                    -1,
                    performers,
                    tags,
                    new List<IAvailableFile>()
                        .Concat(sceneDownloads)
                        .Concat(galleryDownloads)
                        .Concat(imageDownloads)
                        .Concat(trailerDownloads)
                        .Concat(spriteDownloads),
                    $$"""{"gallery": """ + movieJson + """, "comments": """ + commentsJson + "}",
                    DateTime.Now);

                yield return scene;
            }
        }
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);
        var requests = await CaptureRequestsAsync(site, page);

        var headers = SetHeadersFromActualRequest(site, requests);
        var convertedHeaders = ConvertHeaders(headers);

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        foreach (var release in releases)
        {
            Log.Information("Downloading {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
            var existingDownloadEntities = await _context.Downloads.Where(d => d.ReleaseUuid == release.Uuid).ToListAsync();
            await foreach (var galleryDownload in DownloadGalleriesAsync(downloadConditions, release, existingDownloadEntities, headers, convertedHeaders))
            {
                yield return galleryDownload;
            }
            await foreach (var videoDownload in DownloadsVideosAsync(downloadConditions, release, existingDownloadEntities, headers, convertedHeaders))
            {
                yield return videoDownload;
            }
            await foreach (var trailerDownload in DownloadTrailersAsync(downloadConditions, release, existingDownloadEntities))
            {
                yield return trailerDownload;
            }
            await foreach (var vttDownload in DownloadVttFilesAsync(release, existingDownloadEntities, convertedHeaders))
            {
                yield return vttDownload;
            }
            await foreach (var imageDownload in DownloadImagesAsync(release, existingDownloadEntities, convertedHeaders))
            {
                yield return imageDownload;
            }
        }
    }

    private async IAsyncEnumerable<Download> DownloadGalleriesAsync(DownloadConditions downloadConditions, Release release,
        List<DownloadEntity> existingDownloadEntities, IReadOnlyDictionary<string, string> headers, WebHeaderCollection convertedHeaders)
    {
        var availableGalleries = release.AvailableFiles
            .OfType<AvailableGalleryZipFile>()
            .Where(d => d is { FileType: "zip", ContentType: "gallery" });
        var selectedGallery = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableGalleries.FirstOrDefault()
            : availableGalleries.LastOrDefault();
        if (selectedGallery == null || !NotDownloadedYet(existingDownloadEntities, selectedGallery))
        {
            yield break;
        }
        
        var handler = new HttpClientHandler
        {
            AllowAutoRedirect = false
        };
        var client = new HttpClient(handler);
        client.DefaultRequestHeaders.Clear();
        client.DefaultRequestHeaders.Add("cookie", headers["cookie"]);
        client.DefaultRequestHeaders.Add("user-agent", headers["user-agent"]);

        var request = new HttpRequestMessage(HttpMethod.Head, selectedGallery.Url);
        var response = await client.SendAsync(request);

        var actualMediaUrl = response.Headers.Location?.ToString();
        if (string.IsNullOrEmpty(actualMediaUrl))
        {
            throw new InvalidOperationException("actualMediaUrl is missing.");
        }

        var uri = new Uri(actualMediaUrl);
        var query = HttpUtility.ParseQueryString(uri.Query);
        var suggestedFileName = query["filename"] ?? string.Empty;
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedGallery.Variant);

        var fileInfo = await _downloader.TryDownloadAsync(release, selectedGallery, actualMediaUrl, fileName, convertedHeaders);
        if (fileInfo == null)
        {
            yield break;
        }

        var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
        var metadata = new GalleryZipFileMetadata(sha256Sum);
        yield return new Download(release, suggestedFileName, fileInfo.Name, selectedGallery, metadata);
    }

    private async IAsyncEnumerable<Download> DownloadsVideosAsync(DownloadConditions downloadConditions, Release release,
        List<DownloadEntity> existingDownloadEntities, IReadOnlyDictionary<string, string> headers, WebHeaderCollection convertedHeaders)
    {
        var availableVideos = release.AvailableFiles.OfType<AvailableVideoFile>().Where(d => d is { FileType: "video", ContentType: "scene" });
        var selectedVideo = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? availableVideos.FirstOrDefault()
            : availableVideos.LastOrDefault();
        if (selectedVideo == null || !NotDownloadedYet(existingDownloadEntities, selectedVideo))
        {
            yield break;
        }
        
        var handler = new HttpClientHandler()
        {
            AllowAutoRedirect = false
        };
        var client = new HttpClient(handler);
        client.DefaultRequestHeaders.Clear();
        client.DefaultRequestHeaders.Add("cookie", headers["cookie"]);
        client.DefaultRequestHeaders.Add("user-agent", headers["user-agent"]);

        var request = new HttpRequestMessage(HttpMethod.Head, selectedVideo.Url);
        var response = await client.SendAsync(request);

        var actualMediaUrl = response.Headers.Location?.ToString();
        if (actualMediaUrl == null)
        {
            throw new InvalidOperationException("actualMediaUrl is missing for release " + release.Uuid);
        }
        
        var uri = new Uri(actualMediaUrl);
        var query = HttpUtility.ParseQueryString(uri.Query);
        var suggestedFileName = query["filename"] ?? string.Empty;
        var suffix = Path.GetExtension(suggestedFileName);

        var performersStr = release.Performers.Count() > 1
            ? string.Join(", ", release.Performers.Take(release.Performers.Count() - 1).Select(p => p.Name)) + " & " +
              release.Performers.Last().Name
            : release.Performers.FirstOrDefault()?.Name ?? "Unknown";
        var fileName = ReleaseNamer.Name(release, suffix, performersStr, selectedVideo.Variant);

        var fileInfo = await _downloader.TryDownloadAsync(release, selectedVideo, actualMediaUrl, fileName, convertedHeaders);
        if (fileInfo == null)
        {
            yield break;
        }

        var videoHashes = Hasher.Phash(@"""" + fileInfo.FullName + @"""");
        yield return new Download(release, suggestedFileName, fileInfo.Name, selectedVideo, videoHashes);
    }

    private async IAsyncEnumerable<Download> DownloadVttFilesAsync(Release release, List<DownloadEntity> existingDownloadEntities,
        WebHeaderCollection convertedHeaders)
    {
        var vtt = release.AvailableFiles
            .OfType<AvailableVttFile>()
            .FirstOrDefault(d => d is { FileType: "vtt", ContentType: "sprite" });
        if (vtt == null || !NotDownloadedYet(existingDownloadEntities, vtt))
        {
            yield break;
        }
        
        const string fileName = "sprite.vtt";
        var fileInfo = await _downloader.TryDownloadAsync(release, vtt, vtt.Url, fileName, convertedHeaders);
        if (fileInfo == null)
        {
            yield break;
        }
            
        var sha256Sum = LegacyDownloader.CalculateSHA256(fileInfo.FullName);
        var metadata = new VttFileMetadata(sha256Sum);
        yield return new Download(release, fileName, fileInfo.Name, vtt, metadata);
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
                $"-protocol_whitelist \"file,http,https,tcp,tls\" -i {fileInfo.FullName} -y -c copy {trailerVideoFullPath}");

        var videoHashes = Hasher.Phash(@"""" + trailerVideoFullPath + @"""");
        yield return new Download(release,
            "trailer.m3u8",
            trailerVideoFileName,
            selectedTrailer,
            videoHashes);
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

    private static bool NotDownloadedYet(List<DownloadEntity> existingDownloadEntities, IAvailableFile bestVideo)
    {
        return !existingDownloadEntities.Exists(d => d.FileType == bestVideo.FileType && d.ContentType == bestVideo.ContentType && d.Variant == bestVideo.Variant);
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

    private static Dictionary<string, string> SetHeadersFromActualRequest(Site site, IList<IRequest> requests)
    {
        var galleriesRequest = requests.SingleOrDefault(r => r.Url.StartsWith(site.Url + "/api/galleries?"));
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
    
    private static async Task<MetArtGalleriesRequest.RootObject> GetGalleriesPageAsync(Site site, int pageNumber)
    {
        var galleriesPageUrl = GalleriesApiUrl(site, pageNumber);

        using var response = await Client.GetAsync(galleriesPageUrl);
        if (response.StatusCode != HttpStatusCode.OK)
        {
            throw new InvalidOperationException($"Could not read galleries API response:{Environment.NewLine}Url={galleriesPageUrl}{Environment.NewLine}StatusCode={response.StatusCode}{Environment.NewLine}ReasonPhrase={response.ReasonPhrase}");
        }
        
        var json = await response.Content.ReadAsStringAsync();
        var galleries = JsonSerializer.Deserialize<MetArtGalleriesRequest.RootObject>(json);
        if (galleries == null)
        {
            throw new InvalidOperationException("Could not read galleries API response: " + json);
        }
        
        return galleries;
    }

    private static async Task<MetArtMoviesRequest.RootObject> GetMoviesPageAsync(Site site, int pageNumber)
    {
        var moviesApiUrl = MoviesApiUrl(site, pageNumber);

        using var response = await Client.GetAsync(moviesApiUrl);
        if (response.StatusCode != HttpStatusCode.OK)
        {
            throw new InvalidOperationException($"Could not read movies API response:{Environment.NewLine}Url={moviesApiUrl}{Environment.NewLine}StatusCode={response.StatusCode}{Environment.NewLine}ReasonPhrase={response.ReasonPhrase}");
        }
        
        var json = await response.Content.ReadAsStringAsync();
        var movies = JsonSerializer.Deserialize<MetArtMoviesRequest.RootObject>(json);
        if (movies == null)
        {
            throw new InvalidOperationException("Could not read movies API response: " + json);
        }
        
        return movies;
    }

    private static async Task LoginAsync(Site site, IPage page)
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
    }
}
