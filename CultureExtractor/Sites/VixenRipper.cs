using System.Collections.Immutable;
using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Text;
using System.Text.Json;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor.Sites;

[Site("blacked")]
[Site("blackedraw")]
[Site("deeper")]
[Site("milfy")]
[Site("slayed")]
[Site("tushy")]
[Site("tushyraw")]
[Site("vixen")]
public class VixenRipper : IYieldingScraper
{
    private static readonly HttpClient Client = new();

    private static string VideosUrl(Site site, int pageNumber) =>
        $"{site.Url}/videos?page={pageNumber}";

    private readonly IPlaywrightFactory _playwrightFactory;
    private readonly ICaptchaSolver _captchaSolver;
    private readonly IRepository _repository;
    private readonly ICultureExtractorContext _context;
    private readonly IDownloader _downloader;

    public VixenRipper(IPlaywrightFactory playwrightFactory, ICaptchaSolver captchaSolver, IRepository repository, ICultureExtractorContext context, IDownloader downloader)
    {
        _playwrightFactory = playwrightFactory;
        _captchaSolver = captchaSolver;
        _repository = repository;
        _context = context;
        _downloader = downloader;
    }

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);

        await LoginAsync(site, page);
        var requests = await CaptureRequestsAsync(site, page);
        
        var graphQlRequest = SetHeadersFromActualRequest(site, requests);
        
        await foreach (var scene in ScrapeScenesAsync(site, scrapeOptions))
        {
            yield return scene;
        }
    }

    private async IAsyncEnumerable<Release> ScrapeScenesAsync(Site site, ScrapeOptions scrapeOptions)
    {
        var pageNumber = 1;
        var pages = -1;
        VixenFindVideosOnSitesResponse.FindVideosOnSites? findVideosOnSites = null;
        do
        {
            /*var cookie = Client.DefaultRequestHeaders.GetValues("cookie").FirstOrDefault();
            var accessToken = ExtractAccessTokenFromCookie(cookie);
            var expiryDate = DecodeTokenAndGetExpiry(accessToken);
            
            if (expiryDate != null && expiryDate.Value.AddMinutes(-2) < DateTime.Now.ToUniversalTime())
            {
                await RefreshAccessToken(site);
            }*/
            
            await Task.Delay(5123);

            var variables = new
            {
                site = site.ShortName.ToUpperInvariant(),
                skip = (pageNumber - 1) * 12,
                first = 12,
                order = new { field = "releaseDate", desc = true },
                filter = new object[]
                {
                    new { field = "unlisted", op = "NE", value = true },
                    new { field = "channelInfo.isThirdPartyChannel", op = "NE", value = true },
                    new { field = "channelInfo.isAvailable", op = "NE", value = false }
                }
            };
            var requestObj = new
            {
                operationName = "getFilteredVideos",
                query = GetFilteredVideosQuery,
                variables = variables
            };

            var requestJson = JsonSerializer.Serialize(requestObj);
            var requestContent = new StringContent(requestJson, Encoding.UTF8, "application/json");
            var request = new HttpRequestMessage(HttpMethod.Post, $"{site.Url}/graphql")
            {
                Content = requestContent
            };
            var response = await Client.SendAsync(request);
            var responseContent = await response.Content.ReadAsStringAsync();


            var videosResponse = JsonSerializer.Deserialize<VixenFindVideosOnSitesResponse.RootObject>(responseContent);
            findVideosOnSites = videosResponse.data.findVideosOnSites;
            if (pages == -1)
            {
                pages = (int)Math.Ceiling(findVideosOnSites.totalCount / 12.0);
            }

            Log.Information($"Page {pageNumber}/{pages} contains {findVideosOnSites.edges.Length} releases");

            pageNumber++;

            var movies = findVideosOnSites.edges
                .ToDictionary(
                    edge => edge.node.slug,
                    edge => edge.node);

            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, movies.Keys.ToList());

            var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);

            var moviesToBeScraped = movies
                .Where(g => !existingReleasesDictionary.ContainsKey(g.Key) || existingReleasesDictionary[g.Key].LastUpdated < scrapeOptions.FullScrapeLastUpdated)
                .Select(g => g.Value)
                .ToList();

            foreach (var movie in moviesToBeScraped)
            {
                var releaseGuid = existingReleasesDictionary.TryGetValue(movie.slug, out var existingRelease)
                    ? existingRelease.Uuid
                    : UuidGenerator.Generate();
                var scene = await ScrapeSceneAsync(site, movie.slug, releaseGuid);

                yield return scene;
            }
        } while (findVideosOnSites.pageInfo.hasNextPage);
    }

    private static async Task<Release> ScrapeSceneAsync(Site site, string shortName, Guid releaseGuid)
    {
        await Task.Delay(1211);

        var videoRequestObj = new
        {
            operationName = "getVideo",
            query = GetVideoQuery,
            variables = new
            {
                site = site.ShortName.ToUpperInvariant(),
                relatedCount = 6,
                videoSlug = shortName
            }
        };

        var videoRequestJson = JsonSerializer.Serialize(videoRequestObj);
        var videoRequestContent = new StringContent(videoRequestJson, Encoding.UTF8, "application/json");
        var videoRequest = new HttpRequestMessage(HttpMethod.Post, $"{site.Url}/graphql")
        {
            Content = videoRequestContent
        };
        var videoResponse = await Client.SendAsync(videoRequest);
        var videoResponseContent = await videoResponse.Content.ReadAsStringAsync();

        var videoResponseFoo = JsonSerializer.Deserialize<VixenFindOneVideoResponse.RootObject>(videoResponseContent);


        var dataFindOneVideo = videoResponseFoo.data.findOneVideo;
        var videoTokenResponseFoo = await GetSceneVideoToken(
            site,
            dataFindOneVideo.videoId);
        var trailerTokenResponseFoo = await GetTrailerVideoToken(
            site,
            dataFindOneVideo.videoId);

        var pictureSetRequestObj = new
        {
            operationName = "getPictureSet",
            query = GetPictureSetQuery,
            variables = new
            {
                site = site.ShortName.ToUpperInvariant(),
                videoSlug = shortName
            }
        };
        var pictureSetRequestJson = JsonSerializer.Serialize(pictureSetRequestObj);
        var pictureSetRequestContent = new StringContent(pictureSetRequestJson, Encoding.UTF8, "application/json");
        var pictureSetRequest = new HttpRequestMessage(HttpMethod.Post, $"{site.Url}/graphql")
        {
            Content = pictureSetRequestContent
        };
        var pictureSetResponse = await Client.SendAsync(pictureSetRequest);
        var pictureSetResponseContent = await pictureSetResponse.Content.ReadAsStringAsync();

        var pictureSetResponseFoo =
            JsonSerializer.Deserialize<VixenGetPictureSetResponse.RootObject>(pictureSetResponseContent);


        var videoTokens = GetAvailableVideos(videoTokenResponseFoo);

        var sceneDownloads = dataFindOneVideo.downloadResolutions
            .Select(video => new AvailableVideoFile(
                "video",
                "scene",
                video.label,
                videoTokens.First(t => t.token.Contains($"{video.width}P")).token,
                -1,
                // Note: This is an error on the API side. They report values such as 2160 and 1080 as width
                // while they are clearly height values.
                int.Parse(video.width.Replace("l", "")),
                HumanParser.ParseFileSizeMaybe(video.size).IsSome(out var fileSizeValue) ? fileSizeValue : -1,
                -1,
                "H.264"
            ))
            .OrderByDescending(availableFile => availableFile.ResolutionHeight)
            .ToList();

        var galleryDownloads = new List<IAvailableFile>()
        {
            new AvailableGalleryZipFile(
                "zip",
                "gallery",
                string.Empty,
                pictureSetResponseFoo.data.findOnePictureSet.zip,
                pictureSetResponseFoo.data.findOnePictureSet.images[0].main[0].width,
                pictureSetResponseFoo.data.findOnePictureSet.images[0].main[0].height,
                -1
            )
        };

        var carouselDownloads = dataFindOneVideo.carousel
            .Select((carousel, index) => new AvailableImageFile(
                "image",
                "carousel",
                (index + 1) + "",
                carousel.main[0].src,
                carousel.main[0].width,
                carousel.main[0].height,
                -1
            ))
            .ToList();

        var posterDownloads = dataFindOneVideo.images.poster
            .OrderByDescending(p => p.height)
            .Select(poster => new AvailableImageFile(
                "image",
                "poster",
                string.Empty,
                poster.src,
                poster.width,
                poster.height,
                -1
            ))
            .Take(1)
            .ToList();

        var imageDownloads = new List<IAvailableFile>()
            .Concat(carouselDownloads)
            .Concat(posterDownloads);

        var trailerTokens = GetAvailableVideos(trailerTokenResponseFoo);
        var trailerDownloads = trailerTokens
            .Select(video =>
            {
                var uri = new Uri(video.token);
                var suggestedFileName = Path.GetFileName(uri.LocalPath);
                var suffix = Path.GetExtension(suggestedFileName);

                var parts = suggestedFileName.Split("_");
                var resolutionPart = parts.FirstOrDefault(part => part.EndsWith("P.mp4"));
                if (resolutionPart == null)
                {
                    throw new FormatException($"Could not find resolution in filename {suggestedFileName}");
                }
                var width = int.Parse(resolutionPart.Replace(suffix, "").Replace("l", "").Replace("P", ""));

                return new AvailableVideoFile(
                    "video",
                    "trailer",
                    width + "",
                    video.token,
                    -1,
                    // Note: This is an error on the API side. They report values such as 2160 and 1080 as width
                    // while they are clearly height values.
                    width,
                    -1,
                    -1,
                    "H.264"
                );
            })
            .OrderByDescending(availableFile => availableFile.ResolutionHeight)
            .ToList();

        var performers = dataFindOneVideo.modelsSlugged
            .Select(m => new SitePerformer(m.slugged, m.name, $"{site.Url}/performers/{m.slugged}"))
            .ToList();

        var tags = dataFindOneVideo.categories
            .Select(t => new SiteTag(t.slug, t.name, $"{site.Url}/videos?search={t.slug}"))
            .ToList();

        var scene = new Release(
            releaseGuid,
            site,
            null,
            DateOnly.FromDateTime(DateTime.Parse(dataFindOneVideo.releaseDate)),
            shortName,
            dataFindOneVideo.title,
            $"{site.Url}/videos/{dataFindOneVideo.slug}",
            dataFindOneVideo.description,
            HumanParser.ParseDuration(dataFindOneVideo.runLengthFormatted).TotalSeconds,
            performers,
            tags,
            new List<IAvailableFile>()
                .Concat(sceneDownloads)
                .Concat(galleryDownloads)
                .Concat(imageDownloads)
                .Concat(trailerDownloads),
            videoResponseContent,
            DateTime.Now);
        return scene;
    }

    private static Task<VixenGetTokenResponse.RootObject?> GetSceneVideoToken(Site site, string videoId)
    {
        return GetVideoToken(site, videoId, "desktop");
    }
    
    private static Task<VixenGetTokenResponse.RootObject?> GetTrailerVideoToken(Site site, string videoId)
    {
        return GetVideoToken(site, videoId, "trailer");
    }
    
    private static async Task<VixenGetTokenResponse.RootObject?> GetVideoToken(Site site, string videoId, string device)
    {
        var requestObject = new
        {
            operationName = "getToken",
            query = GenerateVideoTokenQuery,
            variables = new
            {
                videoId, device
            }
        };
        var requestJson = JsonSerializer.Serialize(requestObject);
        var requestContent = new StringContent(requestJson, Encoding.UTF8, "application/json");
        var request = new HttpRequestMessage(HttpMethod.Post, $"{site.Url}/graphql")
        {
            Content = requestContent
        };
        var response = await Client.SendAsync(request);
        var responseContent = await response.Content.ReadAsStringAsync();

        var deserialized = JsonSerializer.Deserialize<VixenGetTokenResponse.RootObject>(responseContent);
        return deserialized;
    }

    private static List<VixenGetTokenResponse.VideoToken> GetAvailableVideos(VixenGetTokenResponse.RootObject? videoTokenResponseFoo)
    {
        var tokens = new List<VixenGetTokenResponse.VideoToken>();

        if (videoTokenResponseFoo.data.generateVideoToken.p2160 != null && !string.IsNullOrWhiteSpace(videoTokenResponseFoo.data.generateVideoToken.p2160.token))
        {
            tokens.Add(videoTokenResponseFoo.data.generateVideoToken.p2160);
        }

        if (videoTokenResponseFoo.data.generateVideoToken.p1080 != null && !string.IsNullOrWhiteSpace(videoTokenResponseFoo.data.generateVideoToken.p1080.token))
        {
            tokens.Add(videoTokenResponseFoo.data.generateVideoToken.p1080);
        }

        if (videoTokenResponseFoo.data.generateVideoToken.p720 != null && !string.IsNullOrWhiteSpace(videoTokenResponseFoo.data.generateVideoToken.p720.token))
        {
            tokens.Add(videoTokenResponseFoo.data.generateVideoToken.p720);
        }

        if (videoTokenResponseFoo.data.generateVideoToken.p480 != null && !string.IsNullOrWhiteSpace(videoTokenResponseFoo.data.generateVideoToken.p480.token))
        {
            tokens.Add(videoTokenResponseFoo.data.generateVideoToken.p480);
        }

        if (videoTokenResponseFoo.data.generateVideoToken.p480l != null && !string.IsNullOrWhiteSpace(videoTokenResponseFoo.data.generateVideoToken.p480l.token))
        {
            tokens.Add(videoTokenResponseFoo.data.generateVideoToken.p480l);
        }

        if (videoTokenResponseFoo.data.generateVideoToken.p360 != null && !string.IsNullOrWhiteSpace(videoTokenResponseFoo.data.generateVideoToken.p360.token))
        {
            tokens.Add(videoTokenResponseFoo.data.generateVideoToken.p360);
        }

        if (videoTokenResponseFoo.data.generateVideoToken.p270 != null && !string.IsNullOrWhiteSpace(videoTokenResponseFoo.data.generateVideoToken.p270.token))
        {
            tokens.Add(videoTokenResponseFoo.data.generateVideoToken.p270);
        }

        return tokens;
    }

    private static Dictionary<string, string> SetHeadersFromActualRequest(Site site, IList<IRequest> requests)
    {
        var videosRequest = requests.FirstOrDefault(r => r.Url.StartsWith(site.Url + "/graphql"));
        if (videosRequest == null)
        {
            var requestUrls = requests.Select(r => r.Url + Environment.NewLine).ToList();
            throw new InvalidOperationException($"Could not read GraphQL API request from following requests:{Environment.NewLine}{string.Join("", requestUrls)}");
        }
        
        Client.DefaultRequestHeaders.Clear();
        foreach (var key in videosRequest.Headers.Keys)
        {
            if (key != "content-type")
            {
                Client.DefaultRequestHeaders.Add(key, videosRequest.Headers[key]);
            }
        }
        
        return videosRequest.Headers;
    }

    private static string ExtractAccessTokenFromCookie(string cookieString)
    {
        // The cookie string format is usually "key=value; key2=value2"
        var cookies = cookieString.Split(';');
        foreach (var cookie in cookies)
        {
            var cookieParts = cookie.Trim().Split('=');
            if (cookieParts[0] == "access_token")
            {
                return cookieParts[1];
            }
        }
        return null;
    }

    private static DateTime? DecodeTokenAndGetExpiry(string token)
    {
        var handler = new JwtSecurityTokenHandler();
        var jsonToken = handler.ReadJwtToken(token);
        var expClaim = jsonToken.Claims.FirstOrDefault(claim => claim.Type == "exp");
        if (expClaim != null && long.TryParse(expClaim.Value, out var expValue))
        {
            // The exp claim is the number of seconds since epoch
            var expiryDate = DateTimeOffset.FromUnixTimeSeconds(expValue).DateTime;
            return expiryDate;
        }
        return null;
    }
    
    private static async Task RefreshAccessToken(Site site)
    {
        var refreshUrl = $"{site.Url}/api/refresh";
        var refreshRequest = new HttpRequestMessage(HttpMethod.Post, "https://members.tushy.com/api/refresh");
        var refreshResponse = await Client.SendAsync(refreshRequest);
        
        var newAccessToken = refreshResponse.Headers.GetValues("Set-Cookie")
            .Select(ExtractAccessTokenFromCookie)
            .FirstOrDefault(token => token != null);
    }
    
    private static async Task<List<IRequest>> CaptureRequestsAsync(Site site, IPage page)
    {
        var requests = new List<IRequest>();
        await page.RouteAsync("**/*", async route =>
        {
            requests.Add(route.Request);
            await route.ContinueAsync();
        });

        await page.GotoAsync(VideosUrl(site, 1));
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        await page.UnrouteAsync("**/*");
        return requests;
    }

    public async IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings,
        DownloadConditions downloadConditions)
    {
        IPage page = await _playwrightFactory.CreatePageAsync(site, browserSettings);
        await LoginAsync(site, page);

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
            
            // TODO: Refresh token when JWT token has expired
            var convertedHeaders = new WebHeaderCollection();
            if (downloadedReleases % 30 == 0) {
                var requests = await CaptureRequestsAsync(site, page);

                var headers = SetHeadersFromActualRequest(site, requests);
                convertedHeaders = ConvertHeaders(headers);
            }
            
            // this is now done on every scene despite we might already have all files
            // the reason for updated scrape is that the links are timebombed and we need to refresh those
            Release? updatedScrape;
            try
            {
                updatedScrape = await ScrapeSceneAsync(site, release.ShortName, release.Uuid);
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
            foreach (var trailerDownload in await DownloadTrailersAsync(downloadConditions, updatedScrape, existingDownloadEntities, convertedHeaders))
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
    
    private async Task<IList<Download>> DownloadVideosAsync(DownloadConditions downloadConditions, Release release,
        List<DownloadEntity> existingDownloadEntities, WebHeaderCollection convertedHeaders)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "scene" });
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

    private async Task<IList<Download>> DownloadTrailersAsync(DownloadConditions downloadConditions, Release release,
        List<DownloadEntity> existingDownloadEntities, WebHeaderCollection convertedHeaders)
    {
        var availableVideos = release.AvailableFiles
            .OfType<AvailableVideoFile>()
            .Where(d => d is { FileType: "video", ContentType: "trailer" });
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

        var fileName = $"trailer_{selectedVideo.Variant}{suffix}";

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
    
    private async IAsyncEnumerable<Download> DownloadImagesAsync(Release release, List<DownloadEntity> existingDownloadEntities, WebHeaderCollection convertedHeaders)
    {
        var imageFiles = release.AvailableFiles.OfType<AvailableImageFile>();
        foreach (var imageFile in imageFiles)
        {
            if (!NotDownloadedYet(existingDownloadEntities, imageFile))
            {
                continue;
            }
            
            var uri = new Uri(imageFile.Url);
            var suggestedFileName = Path.GetFileName(uri.LocalPath);
            var suffix = Path.GetExtension(suggestedFileName);
            
            
            var fileName = string.IsNullOrWhiteSpace(imageFile.Variant) ? $"{imageFile.ContentType}{suffix}" : $"{imageFile.ContentType}_{imageFile.Variant}{suffix}";
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
    
    private static WebHeaderCollection ConvertHeaders(Dictionary<string, string> headers)
    {
        var convertedHeaders = new WebHeaderCollection();
        foreach (var header in headers)
        {
            if (header.Key.ToLower() != "content-type")
            {
                convertedHeaders.Add(header.Key, header.Value);   
            }
        }
        return convertedHeaders;
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


    private async Task LoginAsync(Site site, IPage page)
    {
        var usernameInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Email" });
        if (await usernameInput.IsVisibleAsync())
        {
            await usernameInput.ClickAsync();
            await usernameInput.PressSequentiallyAsync(site.Username, new() { Delay = 100 });

            var passwordInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Password" });
            await passwordInput.ClickAsync();
            await passwordInput.PressSequentiallyAsync(site.Password, new() { Delay = 100 });

            await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
            await page.WaitForLoadStateAsync();

            await Task.Delay(5000);

            await _captchaSolver.SolveCaptchaIfNeededAsync(page);

            await page.WaitForLoadStateAsync();
        }
        
        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
    }

    private const string GetFilteredVideosQuery =
        """
        query getFilteredVideos($order: ListOrderInput!, $filter: [ListFilterInput!], $site: [Site!]!, $first: Int!, $skip: Int!) {
            findVideosOnSites(
                input: {filter: $filter, order: $order, first: $first, skip: $skip, site: $site}
            ) {
                edges {
                    node {
                        id: uuid
                        videoId
                        title
                        slug
                        site
                        rating
                        expertReview {
                            global
                            __typename
                        }
                        releaseDate
                        isExclusive
                        freeVideo
                        isFreeLimitedTrial
                        modelsSlugged: models {
                            name
                            slugged: slug
                            __typename
                        }
                        previews {
                            listing {
                                ...PreviewInfo
                                __typename
                            }
                            __typename
                        }
                        images {
                            listing {
                                ...ImageInfo
                                __typename
                            }
                            __typename
                        }
                        __typename
                    }
                    cursor
                    __typename
                }
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    __typename
                }
                totalCount
                __typename
            }
        }

        fragment ImageInfo on Image {
            src
            placeholder
            width
            height
            highdpi {
                double
                triple
                __typename
            }
            __typename
        }

        fragment PreviewInfo on Preview {
            src
            width
            height
            type
            __typename
        }
        """;

    private const string GetVideoQuery =
        """
        query getVideo($videoSlug: String, $site: Site, $relatedCount: Int!) {
          findOneVideo(input: {slug: $videoSlug, site: $site}) {
            id: uuid
            videoId
            newId: videoId
            uuid
            slug
            site
            title
            description
            descriptionHtml
            absoluteUrl
            denied: isDenied
            isUpcoming
            releaseDate
            runLength
            directors {
              name
              __typename
            }
            categories {
              slug
              name
              __typename
            }
            channel {
              channelId
              isThirdPartyChannel
              __typename
            }
            chapters {
              trailerThumbPattern
              videoThumbPattern
              video {
                title
                seconds
                _id: videoChapterId
                __typename
              }
              __typename
            }
            showcase {
              showcaseId
              title
              itsupId {
                mobile
                desktop
                __typename
              }
              __typename
            }
            tour {
              views
              __typename
            }
            modelsSlugged: models {
              name
              slugged: slug
              __typename
            }
            rating
            expertReview {
              global
              properties {
                name
                slug
                rating
                __typename
              }
              models {
                slug
                rating
                name
                __typename
              }
              __typename
            }
            runLengthFormatted: runLength
            releaseDate
            videoUrl1080P: videoTokenId
            trailerTokenId
            picturesInSet
            carousel {
              listing {
                ...PictureSetInfo
                __typename
              }
              main {
                ...PictureSetInfo
                __typename
              }
              __typename
            }
            images {
              poster {
                ...ImageInfo
                __typename
              }
              __typename
            }
            tags
            downloadResolutions {
              label
              size
              width
              res
              __typename
            }
            related(count: $relatedCount) {
              title
              uuid
              id: videoId
              slug
              absoluteUrl
              site
              freeVideo
              isFreeLimitedTrial
              models {
                absoluteUrl
                name
                slug
                __typename
              }
              releaseDate
              rating
              expertReview {
                global
                __typename
              }
              channel {
                channelId
                __typename
              }
              images {
                listing {
                  ...ImageInfo
                  __typename
                }
                __typename
              }
              previews {
                listing {
                  ...PreviewInfo
                  __typename
                }
                __typename
              }
              __typename
            }
            freeVideo
            isFreeLimitedTrial
            userVideoReview {
              slug
              rating
              __typename
            }
            __typename
          }
        }

        fragment PictureSetInfo on PictureSetImage {
          src
          width
          height
          name
          __typename
        }

        fragment ImageInfo on Image {
          src
          placeholder
          width
          height
          highdpi {
            double
            triple
            __typename
          }
          __typename
        }

        fragment PreviewInfo on Preview {
          src
          width
          height
          type
          __typename
        }
        """;

    private const string GenerateVideoTokenQuery =
        """
        query getToken($videoId: ID!, $device: Device!) {
          generateVideoToken(input: {videoId: $videoId, device: $device}) {
            p270 {
              token
              cdn
              __typename
            }
            p360 {
              token
              cdn
              __typename
            }
            p480 {
              token
              cdn
              __typename
            }
            p480l {
              token
              cdn
              __typename
            }
            p720 {
              token
              cdn
              __typename
            }
            p1080 {
              token
              cdn
              __typename
            }
            p2160 {
              token
              cdn
              __typename
            }
            hls {
              token
              cdn
              __typename
            }
            __typename
          }
        }
        """;

    private const string GetPictureSetQuery =
        """
        query getPictureSet($videoSlug: String, $site: Site!) {
          findOnePictureSet(input: {slug: $videoSlug, site: $site}) {
            pictureSetId
            zip
            video {
              id: uuid
              videoId
              freeVideo
              isFreeLimitedTrial
              site
              categories {
                slug
                name
                __typename
              }
              __typename
            }
            images {
              listing {
                src
                width
                height
                __typename
              }
              main {
                src
                width
                height
                __typename
              }
              __typename
            }
            __typename
          }
        }
        """;
}