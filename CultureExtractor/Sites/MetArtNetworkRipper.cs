using System.Collections.Immutable;
using System.Net;
using Microsoft.Playwright;
using CultureExtractor.Interfaces;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Web;
using CultureExtractor.Exceptions;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Polly;
using Serilog;
using Xabe.FFmpeg;

namespace CultureExtractor.Sites;

/**
 * TODO:
 *
 * [11:56:58 INF]     [x] FileType=image ContentType=sprite Variant=
[11:56:58 INF] Downloading: SexArt - 2017-10-14 - Opita [018ba4a2-5cc3-72e4-b755-5475e63688a1]
[11:57:19 ERR] System.Net.Http.HttpRequestException: A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond. (www.sexart.com:443)
 ---> System.Net.Sockets.SocketException (10060): A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond.
   at System.Net.Sockets.Socket.AwaitableSocketAsyncEventArgs.ThrowException(SocketError error, CancellationToken cancellationToken)
   at System.Net.Sockets.Socket.AwaitableSocketAsyncEventArgs.System.Threading.Tasks.Sources.IValueTaskSource.GetResult(Int16 token)
   at System.Net.Sockets.Socket.<ConnectAsync>g__WaitForConnectWithCancellation|281_0(AwaitableSocketAsyncEventArgs saea, ValueTask connectTask, CancellationToken cancellationToken)
   at System.Net.Http.HttpConnectionPool.ConnectToTcpHostAsync(String host, Int32 port, HttpRequestMessage initialRequest, Boolean async, CancellationToken cancellationToken)
   --- End of inner exception stack trace ---
   at System.Net.Http.HttpConnectionPool.ConnectToTcpHostAsync(String host, Int32 port, HttpRequestMessage initialRequest, Boolean async, CancellationToken cancellationToken)
   at System.Net.Http.HttpConnectionPool.ConnectAsync(HttpRequestMessage request, Boolean async, CancellationToken cancellationToken)
   at System.Net.Http.HttpConnectionPool.CreateHttp11ConnectionAsync(HttpRequestMessage request, Boolean async, CancellationToken cancellationToken)
   at System.Net.Http.HttpConnectionPool.AddHttp11ConnectionAsync(QueueItem queueItem)
   at System.Threading.Tasks.TaskCompletionSourceWithCancellation`1.WaitWithCancellationAsync(CancellationToken cancellationToken)
   at System.Net.Http.HttpConnectionPool.HttpConnectionWaiter`1.WaitForConnectionAsync(Boolean async, CancellationToken requestCancellationToken)
   at System.Net.Http.HttpConnectionPool.SendWithVersionDetectionAndRetryAsync(HttpRequestMessage request, Boolean async, Boolean doRequestAuth, CancellationToken cancellationToken)
   at System.Net.Http.HttpClient.<SendAsync>g__Core|83_0(HttpRequestMessage request, HttpCompletionOption completionOption, CancellationTokenSource cts, Boolean disposeCts, CancellationTokenSource pendingRequestsCts, CancellationToken originalCancellationToken)
   at CultureExtractor.Sites.MetArtNetworkRipper.DownloadGalleriesAsync(DownloadConditions downloadConditions, Release release, List`1 existingDownloadEntities, IReadOnlyDictionary`2 headers, WebHeaderCollection convertedHeaders)+MoveNext() in C:\Github\CultureExtractor\CultureExtractor\Sites\MetArtNetworkRipper.cs:line 437
   at CultureExtractor.Sites.MetArtNetworkRipper.DownloadGalleriesAsync(DownloadConditions downloadConditions, Release release, List`1 existingDownloadEntities, IReadOnlyDictionary`2 headers, WebHeaderCollection convertedHeaders)+System.Threading.Tasks.Sources.IValueTaskSource<System.Boolean>.GetResult()
   at CultureExtractor.Sites.MetArtNetworkRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)+MoveNext() in C:\Github\CultureExtractor\CultureExtractor\Sites\MetArtNetworkRipper.cs:line 390
   at CultureExtractor.Sites.MetArtNetworkRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)+MoveNext() in C:\Github\CultureExtractor\CultureExtractor\Sites\MetArtNetworkRipper.cs:line 390
   at CultureExtractor.Sites.MetArtNetworkRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)+System.Threading.Tasks.Sources.IValueTaskSource<System.Boolean>.GetResult()
   at CultureExtractor.NetworkRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 257
   at CultureExtractor.NetworkRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 257
   at CultureExtractor.CultureExtractorConsoleApp.RunDownloadAndReturnExitCode(DownloadOptions opts) in C:\Github\CultureExtractor\CultureExtractor\CultureExtractorConsoleApp.cs:line 95
 */

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
[Site("domai")]
public class MetArtNetworkRipper : IYieldingScraper
{
    private static readonly HttpClient Client = new();
    
    private readonly IDownloader _downloader;
    private readonly IPlaywrightFactory _playwrightFactory;
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
    private static string GalleryApiUrl(Site site, ShortName shortName) =>
        $"{site.Url}/api/gallery?name={shortName.Name}&date={shortName.Date}&page=1&mediaFirst=42";
    private static string MoviesApiUrl(Site site, int pageNumber) =>
        $"{site.Url}/api/movies?galleryType=MOVIE&first=60&page={pageNumber}&showPinnedGallery=false&tabId=0&order=DATE&direction=DESC&type=MOVIE";
    private static string MovieApiUrl(Site site, ShortName shortName) =>
        $"{site.Url}/api/movie?name={shortName.Name}&date={shortName.Date}";
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
            if (scrapeOptions.FullScrapeLastUpdated != null)
            {
                // If FullScrape is true, take all galleries
                galleriesToBeScraped = galleries
                    .Where(g =>
                        !existingReleasesDictionary.ContainsKey(g.Key)
                        || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated
                    )
                    .Select(g => g.Value)
                    .ToList();
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

                var shortName = ShortName.FromReleaseUrl(gallery.path);
                var guid = existingReleasesDictionary.TryGetValue(shortName.Combined, out var existingRelease)
                    ? existingRelease.Uuid
                    : UuidGenerator.Generate();

                Release? release = null;
                try
                {
                    release = await ScrapeGalleryAsync(site, shortName, guid, CancellationToken.None);
                }
                catch (Exception ex)
                {
                    Log.Error(ex, "Error while scraping gallery {Gallery}", gallery.path);
                    continue;
                }

                if (release != null)
                {
                    yield return release;
                }
            }
        }
    }

    private record ShortName(string Date, string Name)
    {
        public string Combined => $"{Date}/{Name}";

        public static ShortName FromCombined(string combined)
        {
            var components = combined.Split('/');
            return new ShortName(components[0], components[1]);
        }

        public static ShortName FromReleaseUrl(string url)
        {
            var date = Regex.Match(url, @"\/(\d{8})\/").Groups[1].Value;
            var name = Regex.Match(url, @"\/(\w+)$").Groups[1].Value;
            return new ShortName(date, name);
        }
    }

    private static async Task<Release?> ScrapeGalleryAsync(Site site, ShortName shortName, Guid guid, CancellationToken cancellationToken)
    {
        var galleryUrl = GalleryApiUrl(site, shortName);
        using var galleryResponse = await GetApiResponseAsync(galleryUrl, cancellationToken);

        var galleryJson = await galleryResponse.Content.ReadAsStringAsync(cancellationToken);
        
        MetArtGalleryRequest.RootObject? galleryDetails;

        try
        {
            galleryDetails = JsonSerializer.Deserialize<MetArtGalleryRequest.RootObject>(galleryJson);
            if (galleryDetails == null)
            {
                throw new InvalidOperationException("Could not read gallery API response: " + galleryJson);
            }
        }
        catch (JsonException ex)
        {
            Log.Error($"Caught following exception while deserializing gallery API response:{Environment.NewLine}Gallery URL: {galleryUrl}{Environment.NewLine}{ex}{Environment.NewLine}JSON:{Environment.NewLine}{galleryJson}", ex);
            return null;
        }

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
            .Select(m =>
                new SitePerformer(m.path[(m.path.LastIndexOf("/", StringComparison.Ordinal) + 1)..], m.name, m.path))
            .ToList();

        var tags = galleryDetails.tags
            .Select(t => new SiteTag(t.Replace(" ", "+"), t, "/tags/" + t.Replace(" ", "+")))
            .ToList();

        var commentsJson = await GetCommentsAsync(site, galleryDetails.UUID, cancellationToken);
        var jsonDocument = $$"""{"gallery": """ + galleryJson + """, "comments": """ + commentsJson + "}";
        if (!IsValidJson(jsonDocument))
        {
            Log.Error("Invalid JSON document: {JsonDocument}", jsonDocument);
            jsonDocument = "{}";
        }

        var scene = new Release(
            guid,
            site,
            null,
            DateOnly.FromDateTime(galleryDetails.publishedAt),
            shortName.Combined,
            galleryDetails.name,
            $"{site.Url}{galleryDetails.path}",
            galleryDetails.description,
            -1,
            performers,
            tags,
            new List<IAvailableFile>()
                .Concat(galleryDownloads)
                .Concat(imageDownloads),
            jsonDocument,
            DateTime.Now);
        return scene;
    }

    private static async Task<string> GetCommentsAsync(Site site, string releaseUuid, CancellationToken cancellationToken)
    {
        for (var i = 0; i < 3; i++)
        {
            try
            {
                var commentsUrl = CommentsApiUrl(site, releaseUuid);

                using var commentResponse = await GetApiResponseAsync(commentsUrl, cancellationToken);
                return await commentResponse.Content.ReadAsStringAsync(cancellationToken);
            }
            catch (Exception ex)
            {
                Log.Error(ex, "Error while getting comments for release {ReleaseUuid}", releaseUuid);
            }
        }

        return string.Empty;
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, ScrapeOptions scrapeOptions)
    {
        var moviesInitialPage = await GetMoviesPageAsync(site, 1);

        var pages = (int)Math.Ceiling((double)moviesInitialPage.total / moviesInitialPage.galleries.Length);
        for (var pageNumber = 1; pageNumber <= pages; pageNumber++)
        {
            await Task.Delay(1000);

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

            var existingReleasesLookup = existingReleases.ToLookup(r => r.ShortName, r => r);
            var existingReleasesDictionary = new Dictionary<string, Release>();

            foreach (var group in existingReleasesLookup)
            {
                if (group.Count() > 1)
                {
                    // Log a warning
                    Log.Warning($"Duplicate keys found for {group.Key}");
                }

                existingReleasesDictionary[group.Key] = group.First();
            }

            List<MetArtMoviesRequest.Galleries> moviesToBeScraped;
            if (scrapeOptions.FullScrapeLastUpdated != null)
            {
                // If FullScrape is true, take all galleries
                moviesToBeScraped = movies
                    .Where(g =>
                        !existingReleasesDictionary.ContainsKey(g.Key)
                        || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated
                    )
                    .Select(g => g.Value)
                    .ToList();
            }
            else
            {
                // If FullScrape is false, filter out existing galleries
                moviesToBeScraped = movies
                    .Where(g => !existingReleasesDictionary.ContainsKey(g.Key))
                    .Select(g => g.Value)
                    .ToList();
            }

            foreach (var movie in moviesToBeScraped)
            {
                await Task.Delay(1000);

                var shortName = ShortName.FromReleaseUrl(movie.path);
                var guid = existingReleasesDictionary.TryGetValue(shortName.Combined, out var existingRelease)
                    ? existingRelease.Uuid
                    : UuidGenerator.Generate();

                Release? release = null;
                try
                {
                    release = await ScrapeSceneAsync(site, shortName, guid, CancellationToken.None);
                }
                catch (Exception ex)
                {
                    Log.Error(ex, "Error while scraping movie {Movie}", movie.path);
                    continue;
                }

                if (release != null)
                {
                    yield return release;
                }
            }
        }
    }

    private static async Task<Release?> ScrapeSceneAsync(Site site, ShortName shortName, Guid guid, CancellationToken cancellationToken)
    {
        var movieUrl = MovieApiUrl(site, shortName);
        using var movieResponse = await GetApiResponseAsync(movieUrl, cancellationToken);

        var movieJson = await movieResponse.Content.ReadAsStringAsync(cancellationToken);
        var movieDetails = JsonSerializer.Deserialize<MetArtMovieRequest.RootObject>(movieJson);
        if (movieDetails == null)
        {
            throw new InvalidOperationException("Could not read movie API response: " + movieJson);
        }

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

        IList<IAvailableFile> trailerDownloads = new List<IAvailableFile>();
        if (movieDetails.files.teasers.Contains("m3u8"))
        {
            trailerDownloads = new List<IAvailableFile>
            {
                new AvailableVideoFile("video", "trailer", "720",
                    $"https://www.sexart.com/api/m3u8/{movieDetails.UUID}/720.m3u8", -1, 720, -1, -1, "h264"),
                new AvailableVideoFile("video", "trailer", "270",
                    $"https://www.sexart.com/api/m3u8/{movieDetails.UUID}/270.m3u8", -1, 270, -1, -1, "h264")
            };
        }
        else if (movieDetails.files.teasers.Contains("mp4"))
        {
            trailerDownloads = new List<IAvailableFile>
            {
                new AvailableVideoFile("video", "trailer", "720",
                    $"https://cdn.metartnetwork.com/{movieDetails.siteUUID}/media/{movieDetails.UUID}/tease_{movieDetails.UUID}.mp4",
                    -1, 720, -1, -1, "h264"),
            };
        }

        var performers = movieDetails.models.Where(a => a.gender == "female").ToList()
            .Concat(movieDetails.models.Where(a => a.gender != "female").ToList())
            .Select(m =>
                new SitePerformer(m.path[(m.path.LastIndexOf("/", StringComparison.Ordinal) + 1)..], m.name, m.path))
            .ToList();

        var tags = movieDetails.tags
            .Select(t => new SiteTag(t.Replace(" ", "+"), t, "/tags/" + t.Replace(" ", "+")))
            .ToList();

        var commentsJson = await GetCommentsAsync(site, movieDetails.UUID, cancellationToken);
        var jsonDocument = $$"""{"gallery": """ + movieJson + """, "comments": """ + commentsJson + "}";
        if (!IsValidJson(jsonDocument))
        {
            Log.Error("Invalid JSON document: {JsonDocument}", jsonDocument);
            jsonDocument = "{}";
        }

        var scene = new Release(
            guid,
            site,
            null,
            DateOnly.FromDateTime(movieDetails.publishedAt),
            shortName.Combined,
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
                .Concat(trailerDownloads),
            jsonDocument,
            DateTime.Now);
        return scene;
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);
        var requests = await CaptureRequestsAsync(site, page);
        var headers = SetHeadersFromActualRequest(site, requests);
        var convertedHeaders = ConvertHeaders(headers);

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        foreach (var existingRelease in releases)
        {
            var currentRelease = existingRelease;

            // FUCKING KLUDGE
            if (!currentRelease.ShortName.StartsWith("2") && !currentRelease.ShortName.StartsWith("1999"))
            {
                currentRelease = currentRelease with
                {
                    ShortName = "2" + currentRelease.ShortName,
                };
            }
            // FUCKING KLUDGE


            var releaseDownloadPlan = PlanDownloads(currentRelease, downloadConditions);
            var releaseMissingDownloadsPlan = PlanMissingDownloads(releaseDownloadPlan);

            if (!releaseMissingDownloadsPlan.AvailableFiles.Any())
            {
                continue;
            }

            // Define a Polly policy that handles all exceptions.
            var policy = Policy.Handle<Exception>()
                .RetryAsync(3, (exception, retryCount) =>
                {
                    // This is the onRetry delegate, you can add logging here or other custom behavior.
                    Console.WriteLine($"An error occurred while downloading a release: {exception.Message}. Retry attempt: {retryCount}");
                });

            var isFilm = currentRelease.AvailableFiles.Any(f => f.ContentType == "scene");
            Release? updatedScrape;
            
            try
            {
                updatedScrape = isFilm
                    ? await ScrapeSceneAsync(site, ShortName.FromCombined(currentRelease.ShortName), currentRelease.Uuid, CancellationToken.None)
                    : await ScrapeGalleryAsync(site, ShortName.FromCombined(currentRelease.ShortName), currentRelease.Uuid, CancellationToken.None);
            }
            catch (Exception ex)
            {
                Log.Error(ex, "Error while scraping release {Release}", currentRelease.Uuid);
                continue;
            }
            
            var release = await _repository.UpsertRelease(updatedScrape);

            Log.Information("Downloading: {Site} - {ReleaseDate} - {Release} [{Uuid}]", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name, release.Uuid);



            // Execute the download operation using the Polly policy.
            var downloads = new List<Download>();
            await policy.ExecuteAsync(async () =>
            {
                // Load existingDownloadEntities inside the ExecuteAsync method
                var existingDownloadEntities = await _context.Downloads.Where(d => d.ReleaseUuid == release.Uuid).ToListAsync();

                await foreach (var galleryDownload in DownloadGalleriesAsync(downloadConditions, release, existingDownloadEntities, headers, convertedHeaders))
                {
                    downloads.Add(galleryDownload);
                }
                await foreach (var videoDownload in DownloadVideosAsync(downloadConditions, release, existingDownloadEntities, headers, convertedHeaders))
                {
                    downloads.Add(videoDownload);
                }
                await foreach (var trailerDownload in DownloadTrailersAsync(downloadConditions, release, existingDownloadEntities))
                {
                    downloads.Add(trailerDownload);
                }
                await foreach (var vttDownload in DownloadVttFilesAsync(release, existingDownloadEntities, convertedHeaders))
                {
                    downloads.Add(vttDownload);
                }
                await foreach (var imageDownload in DownloadImagesAsync(release, existingDownloadEntities, convertedHeaders))
                {
                    downloads.Add(imageDownload);
                }
            });

            foreach (var download in downloads)
            {
                yield return download;
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

        var url = selectedGallery.Url.StartsWith(release.Site.Url)
            ? selectedGallery.Url
            : release.Site.Url + selectedGallery.Url;

        var request = new HttpRequestMessage(HttpMethod.Head, url);
        var response = await client.SendAsync(request);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
        {
            throw new ExtractorException(ExtractorRetryMode.Abort, "Unauthorized to read URL. Please check your credentials.");
        }
        
        var actualMediaUrl = response.Headers.Location?.ToString();
        if (string.IsNullOrEmpty(actualMediaUrl))
        {
            // TODO: could be caused by having to login again
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

    private static ReleaseDownloadPlan PlanDownloads(Release release, DownloadConditions downloadConditions)
    {
        var sceneFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "scene").ToList();
        var galleryFiles = release.AvailableFiles.OfType<AvailableGalleryZipFile>().Where(f => f.ContentType == "gallery").ToList();
        var trailerFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "trailer").ToList();

        var selectedSceneFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? sceneFiles.Take(1)
            : sceneFiles.TakeLast(1);
        var selectedGalleryFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? galleryFiles.Take(1)
            : galleryFiles.TakeLast(1);
        var selectedTrailerFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? trailerFiles.Take(1)
            : trailerFiles.TakeLast(1);
        var otherFiles = release.AvailableFiles
            .Except(trailerFiles)
            .Except(sceneFiles)
            .Except(galleryFiles)
            .ToList();

        var availableFiles = new List<IAvailableFile>()
            .Concat(selectedSceneFiles)
            .Concat(selectedGalleryFiles)
            .Concat(selectedTrailerFiles)
            .Concat(otherFiles)
            .ToImmutableList();
        
        return new ReleaseDownloadPlan(release, availableFiles);
    }

    private ReleaseDownloadPlan PlanMissingDownloads(ReleaseDownloadPlan releaseDownloadPlan)
    {
        var existingDownloads = _context.Downloads.Where(d => d.ReleaseUuid == releaseDownloadPlan.Release.Uuid).ToList();
        var notYetDownloaded = releaseDownloadPlan.AvailableFiles
            .Where(f => !existingDownloads.Exists(d =>
                d.FileType == f.FileType && d.ContentType == f.ContentType && d.Variant == f.Variant))
            .ToImmutableList();

        return releaseDownloadPlan with { AvailableFiles = notYetDownloaded };
    }

    private async IAsyncEnumerable<Download> DownloadVideosAsync(DownloadConditions downloadConditions, Release release,
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

        var url = selectedVideo.Url.StartsWith(release.Site.Url)
            ? selectedVideo.Url
            : release.Site.Url + selectedVideo.Url;

        var request = new HttpRequestMessage(HttpMethod.Head, url);
        var response = await client.SendAsync(request);

        var actualMediaUrl = response.Headers.Location?.ToString();
        if (actualMediaUrl == null)
        {
            Log.Warning("actualMediaUrl is missing for release " + release.Uuid);
            yield break;
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

        if (selectedTrailer.Url.Contains("m3u8"))
        {
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
        else
        {
            Uri uri;
            try
            {
                uri = new Uri(selectedTrailer.Url);
            }
            catch (Exception ex)
            {
                Log.Error(ex, "Could not parse trailer URL: " + selectedTrailer.Url);
                yield break;
            }

            var query = HttpUtility.ParseQueryString(uri.Query);
            var suggestedFileName = query["filename"] ?? string.Empty;
            var suffix = Path.GetExtension(suggestedFileName);
            
            var fileInfo = await _downloader.TryDownloadAsync(release, selectedTrailer, selectedTrailer.Url, $"trailer_720{suffix}", new WebHeaderCollection());
            if (fileInfo == null)
            {
                yield break;
            }
            
            var videoHashes = Hasher.Phash(@"""" + fileInfo.FullName + @"""");
            yield return new Download(release, suggestedFileName, fileInfo.Name, selectedTrailer, videoHashes);
        }
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
        Exception? lastException = null;

        for (var i = 0; i < 3; i++)
        {
            try
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
            catch (Exception ex)
            {
                lastException = ex;
                Log.Warning(ex, "Failed to get galleries page {PageNumber} from {Site}", pageNumber, site.ShortName);
                continue;
            }
        }

        if (lastException == null)
        {
            throw new InvalidOperationException("Failed to get galleries page after 3 attempts.");
        }

        throw new InvalidOperationException("Failed to get galleries page after 3 attempts.", lastException);
    }

    private static async Task<MetArtMoviesRequest.RootObject> GetMoviesPageAsync(Site site, int pageNumber)
    {
        Exception? lastException = null;

        for (var i = 0; i < 3; i++)
        {
            try
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
            catch (Exception ex)
            {
                lastException = ex;
                Log.Warning(ex, "Failed to get movies page {PageNumber} from {Site}", pageNumber, site.ShortName);
                continue;
            }
        }

        if (lastException == null)
        {
            throw new InvalidOperationException("Failed to get movies page after 3 attempts.");
        }

        throw new InvalidOperationException("Failed to get movies page after 3 attempts.", lastException);
    }

    private async Task LoginAsync(Site site, IPage page)
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
        
        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
    }

    private static async Task<HttpResponseMessage> GetApiResponseAsync(string apiUrl, CancellationToken cancellationToken)
    {
        for (var i = 0; i < 3; i++)
        {
            var response = await Client.GetAsync(apiUrl, cancellationToken);
            if (response.IsSuccessStatusCode)
            {
                return response;
            }
            else
            {
                Log.Warning($"Failed to get API response from {apiUrl}{Environment.NewLine}Status code: {response.StatusCode}");
            }
        }

        throw new Exception($"Failed to get API response from {apiUrl} after 3 attempts.");
    }

    private static bool IsValidJson(string jsonString)
    {
        try
        {
            JsonDocument.Parse(jsonString);
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }
}
