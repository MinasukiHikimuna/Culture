using System.Collections.Immutable;
using System.Globalization;
using System.Net;
using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.Json;
using System.Text.Json.Serialization;
using CultureExtractor.Exceptions;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Polly;
using Polly.Fallback;
using Xabe.FFmpeg;

namespace CultureExtractor.Sites;

/**
 * TODO:
 * [16:08:32 ERR] System.Threading.Tasks.TaskCanceledException: The request was canceled due to the configured HttpClient.Timeout of 100 seconds elapsing.
 ---> System.TimeoutException: The operation was canceled.
 ---> System.Threading.Tasks.TaskCanceledException: The operation was canceled.
 ---> System.IO.IOException: Unable to read data from the transport connection: The I/O operation has been aborted because of either a thread exit or an application request..
 ---> System.Net.Sockets.SocketException (995): The I/O operation has been aborted because of either a thread exit or an application request.
   --- End of inner exception stack trace ---
   at System.Net.Sockets.Socket.AwaitableSocketAsyncEventArgs.ThrowException(SocketError error, CancellationToken cancellationToken)
   at System.Net.Sockets.Socket.AwaitableSocketAsyncEventArgs.System.Threading.Tasks.Sources.IValueTaskSource<System.Int32>.GetResult(Int16 token)
   at System.Net.Security.SslStream.EnsureFullTlsFrameAsync[TIOAdapter](CancellationToken cancellationToken)
   at System.Runtime.CompilerServices.PoolingAsyncValueTaskMethodBuilder`1.StateMachineBox`1.System.Threading.Tasks.Sources.IValueTaskSource<TResult>.GetResult(Int16 token)
   at System.Net.Security.SslStream.ReadAsyncInternal[TIOAdapter](Memory`1 buffer, CancellationToken cancellationToken)
   at System.Runtime.CompilerServices.PoolingAsyncValueTaskMethodBuilder`1.StateMachineBox`1.System.Threading.Tasks.Sources.IValueTaskSource<TResult>.GetResult(Int16 token)
   at System.Net.Http.HttpConnection.InitialFillAsync(Boolean async)
   at System.Net.Http.HttpConnection.SendAsyncCore(HttpRequestMessage request, Boolean async, CancellationToken cancellationToken)
   --- End of inner exception stack trace ---
   at System.Net.Http.HttpConnection.SendAsyncCore(HttpRequestMessage request, Boolean async, CancellationToken cancellationToken)
   at System.Net.Http.HttpConnectionPool.SendWithVersionDetectionAndRetryAsync(HttpRequestMessage request, Boolean async, Boolean doRequestAuth, CancellationToken cancellationToken)
   at System.Net.Http.RedirectHandler.SendAsync(HttpRequestMessage request, Boolean async, CancellationToken cancellationToken)
   at System.Net.Http.HttpClient.<SendAsync>g__Core|83_0(HttpRequestMessage request, HttpCompletionOption completionOption, CancellationTokenSource cts, Boolean disposeCts, CancellationTokenSource pendingRequestsCts, CancellationToken originalCancellationToken)
   --- End of inner exception stack trace ---
   --- End of inner exception stack trace ---
   at System.Net.Http.HttpClient.HandleFailure(Exception e, Boolean telemetryStarted, HttpResponseMessage response, CancellationTokenSource cts, CancellationToken cancellationToken, CancellationTokenSource pendingRequestsCts)
   at System.Net.Http.HttpClient.<SendAsync>g__Core|83_0(HttpRequestMessage request, HttpCompletionOption completionOption, CancellationTokenSource cts, Boolean disposeCts, CancellationTokenSource pendingRequestsCts, CancellationToken originalCancellationToken)
   at CultureExtractor.Downloader.DownloadFileAsync(Release release, String url, String fileName, WebHeaderCollection headers, String referer, CancellationToken cancellationToken) in C:\Github\CultureExtractor\CultureExtractor\Downloader.cs:line 84
   at CultureExtractor.Downloader.<>c__DisplayClass3_0.<<TryDownloadAsync>b__2>d.MoveNext() in C:\Github\CultureExtractor\CultureExtractor\Downloader.cs:line 47
--- End of stack trace from previous location ---
   at Polly.ResiliencePipeline.<>c__10`1.<<ExecuteAsync>b__10_0>d.MoveNext()
--- End of stack trace from previous location ---
   at Polly.Outcome`1.GetResultOrRethrow()
   at Polly.ResiliencePipeline.ExecuteAsync[TResult](Func`2 callback, CancellationToken cancellationToken)
   at CultureExtractor.Downloader.TryDownloadAsync(Release release, IAvailableFile availableFile, String url, String fileName, WebHeaderCollection convertedHeaders) in C:\Github\CultureExtractor\CultureExtractor\Downloader.cs:line 46
   at CultureExtractor.Sites.AyloRipper.DownloadVideosAsync(DownloadConditions downloadConditions, Release release, List`1 existingDownloadEntities, WebHeaderCollection convertedHeaders) in C:\Github\CultureExtractor\CultureExtractor\Sites\AyloRipper.cs:line 434
   at CultureExtractor.Sites.AyloRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)+MoveNext() in C:\Github\CultureExtractor\CultureExtractor\Sites\AyloRipper.cs:line 358
   at CultureExtractor.Sites.AyloRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions)+System.Threading.Tasks.Sources.IValueTaskSource<System.Boolean>.GetResult()
   at CultureExtractor.NetworkRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 257
   at CultureExtractor.NetworkRipper.DownloadReleasesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, DownloadOptions downloadOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 257
   at CultureExtractor.CultureExtractorConsoleApp.RunDownloadAndReturnExitCode(DownloadOptions opts) in C:\Github\CultureExtractor\CultureExtractor\CultureExtractorConsoleApp.cs:line 95
   */

[Site("babes")]
[Site("brazzers")]
[Site("digitalplayground")]
[Site("fakehub")]
[Site("milehighmedia")]
[Site("mofos")]
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
        $"https://site-api.project1service.com/v2/releases?blockId=4126598482&blockName=SceneListBlock&pageType=EXPLORE_SCENES&orderBy=-dateReleased&type=scene&limit=20&offset={(pageNumber - 1) * 20}";

    private static string MovieApiUrl(string shortName) =>
        $"https://site-api.project1service.com/v2/releases/{shortName}?pageType=PLAYER";

    public AyloRipper(IDownloader downloader, IPlaywrightFactory playwrightFactory, IRepository repository, ICultureExtractorContext context)
    {
        _downloader = downloader;
        _playwrightFactory = playwrightFactory;
        _repository = repository;
        _context = context;
    }

    private class TitleLinkPairs
    {
        [JsonPropertyName("title")]
        public string Title { get; set; }
        [JsonPropertyName("link")]
        public string Link { get; set; }
    }
    
    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);

        await page.GotoAsync("/sites");
        await Task.Delay(5000);

        var existingSubSites = await _repository.GetSubSitesAsync(site.Uuid);

        int scrollY = await page.EvaluateAsync<int>("() => window.scrollY");
        int previousScrollY = -1;
        do
        {
            await page.EvaluateAsync("window.scrollBy(0, 100);");
            previousScrollY = scrollY;
            scrollY = await page.EvaluateAsync<int>("() => window.scrollY");
            await Task.Delay(100);
        } while (scrollY != previousScrollY);

        var fakeHubJs = """
                         () => JSON.stringify(
                             Array.from(document.querySelectorAll('a[href^="/scenes?site="]'))
                                 .filter(link => link.target === '_self')
                                 .map(link => {
                                     const span = link.querySelector('span');
                                     return {
                                         "title": span ? span.textContent : '',
                                         "link": link.href
                                     };
                                 })
                                 .filter(pair => pair.title !== ''));
                         """;
        var babesJs = """
                      () => JSON.stringify(
                          Array.from(document.querySelectorAll('[id^="List-container"]'))
                              .map(section => {
                                  // Find the h2 element for the title within each section
                                  const titleElement = section.querySelector('h2');
                                  const title = titleElement ? titleElement.textContent : '';
                      
                                  // Find the first link within each section
                                  const linkElement = section.querySelector('a[href^="/scenes?site="]');
                                  const link = linkElement ? linkElement.href : '';
                      
                                  return { title, link };
                              })
                              .filter(pair => pair.title !== '' && pair.link !== '')
                      );
                      """;

        var js = site.ShortName switch
        {
            "babes" => babesJs,
            "fakehub" => fakeHubJs,
            "mofos" => null, // Mofos has subsites but their names can't be parsed
            "brazzers" => null, // Brazzers has subsites but their names can't be parsed
            _ => throw new ArgumentOutOfRangeException("No JS for site " + site.ShortName)
        };
            
        if (js != null) {
            var titleLinkPairsJson = await page.EvaluateAsync<string>(js);

            var pairs = JsonSerializer.Deserialize<List<TitleLinkPairs>>(titleLinkPairsJson);
            pairs = pairs.Select(p => new TitleLinkPairs { Title = p.Title.Replace(" - Fake Hub", ""), Link = p.Link }).ToList();
        
            TextInfo textInfo = new CultureInfo("en-US", false).TextInfo;
            List<SubSite> subSites = (
                from pair in pairs
                let id = pair.Link[(pair.Link.LastIndexOf('=') + 1)..]
                let name = textInfo.ToTitleCase(pair.Title.Trim().ToLowerInvariant().Replace(" scenes", ""))
                select new SubSite(
                    existingSubSites.FirstOrDefault(s => s.ShortName == id)?.Uuid ?? UuidGenerator.Generate(),
                    id,
                    name,
                    "{}",
                    site
                )
            ).ToList();

            var uniqueSubSites = subSites
                .GroupBy(s => s.Name)
                .Select(g => g.First())
                .OrderBy(s => s.Name)
                .ToList();
            foreach (var subSite in uniqueSubSites)
            {
                Log.Debug("Upserting sub site {ShortName} {Name} [{Uuid}]", subSite.ShortName, subSite.Name, subSite.Uuid);
                await _repository.UpsertSubSite(subSite);
            }
        }
        
        var requests = await CaptureRequestsAsync(site, page);
        SetHeadersFromActualRequest(requests);
        await foreach (var scene in ScrapeScenesAsync(site, page, scrapeOptions))
        {
            yield return scene;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, IPage page, ScrapeOptions scrapeOptions)
    {
        int pageNumber = 0;
        int pages = 0;

        do
        {
            pageNumber++;
            await Task.Delay(5000);

            AyloMoviesRequest.RootObject moviesPage;
            try
            {
                moviesPage = await GetMoviesPageAsync(pageNumber);                
            }
            catch (Exception ex)
            {
                Log.Error(ex, $"Error while fetching page {pageNumber}");
                continue;
            }

            // Only calculate the total number of pages after fetching the first page
            if (pages == 0)
            {
                if (moviesPage.meta.count == 0)
                {
                    throw new InvalidOperationException($"No movies found on page {pageNumber}.");
                }
                
                pages = (int)Math.Ceiling((double)moviesPage.meta.total / moviesPage.meta.count);
            }

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

                Release? scene = null;
                try
                {
                    var releaseGuid = existingReleasesDictionary.TryGetValue(shortName, out var existingRelease)
                        ? existingRelease.Uuid
                        : UuidGenerator.Generate();
                    scene = await ScrapeSceneAsync(site, shortName, releaseGuid);
                }
                catch (ExtractorException ex)
                {
                    switch (ex.ExtractorRetryMode)
                    {
                        case ExtractorRetryMode.RetryLogin:
                            await LoginAsync(site, page);
                            continue;
                        case ExtractorRetryMode.Retry:
                            continue;
                        case ExtractorRetryMode.Skip:
                            Log.Error(ex, $"Error while scraping scene, skipping: {shortName}");
                            continue;
                        default:
                        case ExtractorRetryMode.Abort:
                            throw;
                    }
                }

                if (scene != null)
                {
                    yield return scene;
                }
                else
                {
                    Log.Error("Unable to scrape {Site} scene {ShortName} on page {Page}", 
                        site.Name, shortName, pageNumber);   
                }
            }
        } while (pageNumber < pages); // Continue while the current page number is less than the total number of pages
    }

    private async Task<Release> ScrapeSceneAsync(Site site, string shortName, Guid releaseGuid)
    {
        try
        {
            var movieUrl = MovieApiUrl(shortName);

            using var movieResponse = Client.GetAsync(movieUrl);
            if (movieResponse.Result.StatusCode != HttpStatusCode.OK)
            {
                throw new ExtractorException(ExtractorRetryMode.Retry, $"Could not read movie API response:{Environment.NewLine}Url={movieUrl}{Environment.NewLine}StatusCode={movieResponse.Result.StatusCode}{Environment.NewLine}ReasonPhrase={movieResponse.Result.ReasonPhrase}");
            }

            var movieJson = await movieResponse.Result.Content.ReadAsStringAsync();
            AyloMovieRequest.RootObject? movieDetailsContainer;
            try
            {

                movieDetailsContainer = JsonSerializer.Deserialize<AyloMovieRequest.RootObject>(movieJson);
            }
            catch (JsonException ex)
            {
                throw new ExtractorException(ExtractorRetryMode.Skip, "Could not deserialize movie API response.", ex);
            }
            
            if (movieDetailsContainer == null)
            {
                throw new ExtractorException(ExtractorRetryMode.Retry, "Could not read movie API response: " + movieJson);
            }

            var movieDetails = movieDetailsContainer.result;
            if (movieDetails.videos == null)
            {
                throw new ExtractorException(ExtractorRetryMode.Skip, "Movie has no videos.");
            }
            if (movieDetails.videos.full == null)
            {
                throw new ExtractorException(ExtractorRetryMode.RetryLogin, "Login required.");
            }

            var movieCollection = movieDetails.collections.FirstOrDefault();
            var subSites = await _repository.GetSubSitesAsync(site.Uuid);
            SubSite? subSite = null;
            if (movieCollection != null)
            {
                subSite = subSites.FirstOrDefault(s => s.ShortName == movieCollection.id.ToString());
                if (subSite == null)
                {
                    subSite = new SubSite(UuidGenerator.Generate(), movieCollection.id.ToString(), movieCollection.name, "{}", site);
                    await _repository.UpsertSubSite(subSite);
                }                
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

            var imageDownloads = movieDetails.images != null
                ? new List<AyloMoviesRequest.PosterSizes?>
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
                    .ToList()
                : new List<AvailableImageFile>();

            var trailerDownloads = movieDetails.videos?.mediabook?.files != null
             ? movieDetails.videos.mediabook.files
                .Select(keyValuePair =>
                    new AvailableVideoFile("video", "trailer", keyValuePair.Key, keyValuePair.Value.urls.view, -1,
                        HumanParser.ParseResolutionHeight(keyValuePair.Value.format), keyValuePair.Value.sizeBytes, -1,
                        string.Empty)
                )
             : new List<AvailableVideoFile>();

            var performers = movieDetails.actors.Where(a => a.gender == "female").ToList()
                .Concat(movieDetails.actors.Where(a => a.gender != "female").ToList())
                .Select(m => new SitePerformer(m.id.ToString(), m.name, string.Empty))
                .ToList();

            var tags = movieDetails.tags
                .Select(t => new SiteTag(t.id.ToString(), t.name, string.Empty))
                .ToList();

            var scene = new Release(
                releaseGuid,
                site,
                subSite,
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
        catch (Exception ex)
        {
            if (ex is ExtractorException)
            {
                throw;
            }
            
            throw new ExtractorException(ExtractorRetryMode.Abort, "Unhandled exception while scraping scene.", ex);
        }
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
        // Aylo sites return empty array instead of object with size-specific images when data is not available.
        // This is bad for strict deserialization, so we replace empty array with null.
        json = json.Replace("\"images\":[]", "\"images\":null");
        json = json.Replace("\"videos\":[]", "\"videos\":null");
        
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

        var releases = await _repository.QueryReleasesAsync(site, downloadConditions);
        var downloadedReleases = 0;
        foreach (var release in releases)
        {
            var releaseDownloadPlan = PlanDownloads(release, downloadConditions);
            var releaseMissingDownloadsPlan = PlanMissingDownloads(releaseDownloadPlan);

            if (!releaseMissingDownloadsPlan.AvailableFiles.Any())
            {
                continue;
            }
            
            var convertedHeaders = new WebHeaderCollection();
            if (downloadedReleases % 30 == 0) {
                await LoginAsync(site, page);
                var requests = await CaptureRequestsAsync(site, page);

                var headers = SetHeadersFromActualRequest(requests);
                convertedHeaders = ConvertHeaders(headers);
            }
            
            // this is now done on every scene despite we might already have all files
            // the reason for updated scrape is that the links are timebombed and we need to refresh those
            Release? updatedScrape;
            try
            {
                updatedScrape = await ScrapeSceneAsync(site, release.ShortName, release.Uuid);
            }
            catch (ExtractorException ex) when (ex.ExtractorRetryMode == ExtractorRetryMode.Abort)
            {
                Log.Error(ex, "Aborting the whole scrape {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                break;
            }
            catch (Exception ex)
            {
                Log.Warning(ex, "Could not scrape {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
                continue;
            }

            await Task.Delay(10000);

            var existingDownloadEntities = await _context.Downloads.Where(d => d.ReleaseUuid == release.Uuid).ToListAsync();
            Log.Information("Downloading: {Site} - {ReleaseDate} - {Release} [{Uuid}]", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name, release.Uuid);
            foreach (var videoDownload in await DownloadVideosAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
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

            downloadedReleases++;
            Log.Information($"{downloadedReleases} releases downloaded in this session.");
        }
    }

    private static ReleaseDownloadPlan PlanDownloads(Release release, DownloadConditions downloadConditions)
    {
        var sceneFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "scene").ToList();
        var trailerFiles = release.AvailableFiles.OfType<AvailableVideoFile>().Where(f => f.ContentType == "trailer").ToList();

        var selectedSceneFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? sceneFiles.Take(1)
            : sceneFiles.TakeLast(1);
        var selectedTrailerFiles = downloadConditions.PreferredDownloadQuality == PreferredDownloadQuality.Best
            ? trailerFiles.Take(1)
            : trailerFiles.TakeLast(1);
        var otherFiles = release.AvailableFiles
            .Except(trailerFiles)
            .Except(sceneFiles)
            .ToList();

        var availableFiles = new List<IAvailableFile>()
            .Concat(selectedSceneFiles)
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
    
    private async Task<IList<Download>> DownloadVideosAsync(DownloadConditions downloadConditions, Release release,
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

        try
        {
            var conversionResult = await FFmpeg.Conversions.New()
                .Start(
                    $"-protocol_whitelist \"file,http,https,tcp,tls\" -i \"{fileInfo.FullName}\" -y -c copy \"{trailerVideoFullPath}\"");
        }
        catch (Exception ex)
        {
            Log.Warning(ex, "Could not convert trailer {Site} {ReleaseDate} {Release}", release.Site.Name, release.ReleaseDate.ToString("yyyy-MM-dd"), release.Name);
            yield break;
        }

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
        var strategy = new ResiliencePipelineBuilder<bool>()
            .AddRetry(new ()
            {
                MaxRetryAttempts = 3,
                Delay = TimeSpan.FromSeconds(5),
                ShouldHandle = new PredicateBuilder<bool>()
                    .Handle<Exception>()
                    .HandleResult(r => r == false),
                OnRetry = args =>
                {
                    var ex = args.Outcome.Exception;
                    Log.Error($"Caught following exception while logging into {site.Name}: " + ex, ex);
                    return default;
                }
            })
            .AddFallback(new ()
            {
                ShouldHandle = new PredicateBuilder<bool>()
                    .Handle<Exception>()
                    .HandleResult(r => r == false),
                FallbackAction = args =>
                {
                    Console.WriteLine($"Please login manually to {site.Name} and press Enter.");
                    Console.ReadLine();
                    return default;
                }
            })
            .Build();

        await strategy.ExecuteAsync(async cancellationToken =>
        {
            var accountLink = await page.EvaluateAsync<bool>("""document.querySelectorAll('a[href="/account"]').length > 0""");
            if (accountLink)
            {
                // Already logged in
                return true;
            }

            var loginUrl = site.Url + "/login";
            if (page.Url != loginUrl)
            {
                await page.GotoAsync(loginUrl);
                await Task.Delay(5000, cancellationToken);            
            }

            var usernameInput = page.GetByPlaceholder("Username or Email");
            if (await usernameInput.IsVisibleAsync())
            {
                var passwordInput = page.GetByPlaceholder("Password");
                var loginButton = page.GetByRole(AriaRole.Button, new() { NameString = "Login" });

                await HumanMime.TypeLikeHumanAsync(usernameInput, site.Username);
                await HumanMime.TypeLikeHumanAsync(passwordInput, site.Password);

                await loginButton.HoverAsync();
                await loginButton.ClickAsync();
                
                await page.WaitForLoadStateAsync();
                await HumanMime.DelayRandomlyAsync(2000, 5000, cancellationToken);
            }
        
            if (page.Url.Contains("badlogin"))
            {
                try
                {
                    await HumanMime.DelayRandomlyAsync(2000, 5000, cancellationToken);
                    await page.EvaluateAsync($"() => document.querySelectorAll('a[href=\"{site.Url}/login\"]')[0].click()");
                }
                catch (Exception ex)
                {
                    Log.Warning(ex, "Could not click login link.");
                }

                await page.WaitForLoadStateAsync();
                return false;
            }

            return true;
        });
        
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
