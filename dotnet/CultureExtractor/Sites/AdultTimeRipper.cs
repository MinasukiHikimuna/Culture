using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[Site("adulttime")]
public class AdultTimeRipper : ISiteScraper
{
    private readonly ILegacyDownloader _legacyDownloader;

    public AdultTimeRipper(ILegacyDownloader legacyDownloader)
    {
        _legacyDownloader = legacyDownloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var usernameInput = page.GetByPlaceholder("Username or Email");
        if (await usernameInput.IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username or Email").ClickAsync();
            await page.GetByPlaceholder("Username or Email").FillAsync(site.Username);

            await page.GetByPlaceholder("password").ClickAsync();
            await page.GetByPlaceholder("password").FillAsync(site.Password);

            // TODO: let's see if we need to manually enable this at all
            // await page.GetByText("Remember me").ClickAsync();

            await page.GetByRole(AriaRole.Button, new() { NameString = "Click here to login" }).ClickAsync();

            await page.WaitForLoadStateAsync();
        }
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = "Videos" }).ClickAsync();
        await page.WaitForLoadStateAsync();

        await page.Locator("div.FilterPanelItem-Categories a").Filter(new() { HasTextString = "Adult Time Original" }).ClickAsync();
        await page.WaitForLoadStateAsync();

        var totalCount = await page.Locator("span.SearchListing-ResultCount-Text").TextContentAsync();
        Log.Information(totalCount);

        var lastPage = await page.Locator("a.Pagination-Page-Link:not(.Pagination-RightControl-Link)").Last.TextContentAsync();
        return int.Parse(lastPage);
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, site, subSite, pageNumber);
        
        var releaseHandles = await page.Locator("div.ListingGrid-ListingGridItem").ElementHandlesAsync();

        var listedReleases = new List<ListedRelease>();
        foreach (var releaseHandle in releaseHandles.Reverse())
        {
            var releaseIdAndUrl = await GetReleaseIdAsync(releaseHandle);
            listedReleases.Add(new ListedRelease(null, releaseIdAndUrl.Id, releaseIdAndUrl.Url, releaseHandle));
        }

        return listedReleases.AsReadOnly();
    }

    private Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        throw new NotImplementedException();
    }
    
    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle currentRelease)
    {
        var thumbLinkElement = await currentRelease.QuerySelectorAsync("a");
        var url = await thumbLinkElement.GetAttributeAsync("href");
        var id = url.Substring(url.LastIndexOf("/") + 1);
        return new ReleaseIdAndUrl(id, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        // TODO:
        /*
        if (response.Url.Contains("algolia.net"))
        {
            var bodyBuffer = await response.BodyAsync();
            var body = System.Text.Encoding.UTF8.GetString(bodyBuffer);

            if (body.Contains("clip_id%3A" + sceneShortName))
            {
                return new CapturedResponse(Enum.GetName(AdultTimeRequestType.SceneMetadata)!, response);
            }
        }
        */ 
        
        var request = requests[0];

        var response = await request.ResponseAsync();
        var body = await response.BodyAsync();
        var jsonContent = System.Text.Encoding.UTF8.GetString(body);

        var data = JsonSerializer.Deserialize<AdultTimeModels.Rootobject>(jsonContent)!;


        var sceneData = data.results[0].hits[0];


        var releaseDate = DateOnly.Parse(sceneData.release_date);
        var duration = TimeSpan.FromSeconds(sceneData.length);
        var title = sceneData.title;

        var performers = new List<SitePerformer>();
        foreach (var performer in sceneData.Actors)
        {
            var shortName = $"{performer.url_name}/{performer.actor_id}";
            var performerUrl = $"/en/pornstar/view/{shortName}";
            var name = performer.name;
            performers.Add(new SitePerformer(shortName, name, performerUrl, "{}"));
        }

        var tags = new List<SiteTag>();
        foreach (var tag in sceneData.categories)
        {
            var shortName = tag.category_id;
            var name = tag.name;
            tags.Add(new SiteTag(shortName, name, string.Empty));
        }

        string description = sceneData.description.Replace("</br>", Environment.NewLine);
        var downloadOptionsAndHandles = ParseAvailableDownloads(sceneData);

        var sceneDocument = new AdultTimeModels.AdultTimeSceneDocument(
            Guid.NewGuid(),
            site.Name,
            sceneData.mainChannel.name,
            releaseDate,
            releaseShortName,
            title,
            url,
            description,
            duration,
            performers,
            sceneData.Directors,
            tags,
            downloadOptionsAndHandles.Select(f => f.AvailableVideoFile).ToList(),
            sceneData.ActionTags != null ? sceneData.ActionTags : new List<AdultTimeModels.ActionTag>());

        Release release = new Release(
            releaseUuid,
            site,
            null,
            releaseDate,
            releaseShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.AvailableVideoFile).ToList(),
            JsonSerializer.Serialize(sceneDocument),
            DateTime.Now);

        if (sceneData.subtitles?.full?.en != null)
        {
            var subtitleFilename = ReleaseNamer.Name(release, ".vtt");
            await _legacyDownloader.DownloadSceneSubtitlesAsync(release, subtitleFilename, "https://subtitles.gammacdn.com/" + sceneData.subtitles.full.en, page.Url);
        }

        var sceneImageUrl = await page.GetAttributeAsync("img.ScenePlayerHeaderPlus-PosterImage", "src");

        string pattern = @"(width=)\d+";
        string replacement = "${1}1920";
        string output = Regex.Replace(sceneImageUrl, pattern, replacement);

        pattern = @"(format=)\w+";
        replacement = "${1}jpg";
        output = Regex.Replace(output, pattern, replacement);

        await _legacyDownloader.DownloadSceneImageAsync(release, output, release.Url);

        return release;
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        await page.GotoAsync(release.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var request = requests[0];
        var response = await request.ResponseAsync();

        var body = await response.TextAsync();
        var data = JsonSerializer.Deserialize<AdultTimeModels.Rootobject>(body)!;


        var sceneData = data.results[0].hits[0];

        var availableDownloads = ParseAvailableDownloads(sceneData);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        IPage newPage = await page.Context.NewPageAsync();

        var suffix = ".mp4";
        var name = ReleaseNamer.Name(release, suffix);

        // TODO: does download but Playwright won't detect when it finishes
        var download = await _legacyDownloader.DownloadSceneAsync(release, newPage, selectedDownload.AvailableVideoFile, downloadConditions.PreferredDownloadQuality, async () =>
        {
            try
            {
                await newPage.GotoAsync(selectedDownload.AvailableVideoFile.Url);
            }
            catch (PlaywrightException ex)
            {
                if (ex.Message.StartsWith("net::ERR_ABORTED"))
                {
                    // Ok. Thrown for some reason every time a file is downloaded using browser.
                }
                else
                {
                    throw;
                }
            }
        }, name);

        await newPage.CloseAsync();

        return download;
    }

    private static IList<DownloadDetailsAndElementHandle> ParseAvailableDownloads(AdultTimeModels.AdultTimeScene sceneData)
    {
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();

        if (sceneData.DownloadFileSizes == null)
        {
            foreach (var downloadSize in sceneData.DownloadSizes)
            {
                availableDownloads.Add(
                    new DownloadDetailsAndElementHandle(
                        new AvailableVideoFile(
                            "video",
                            "scene",
                            downloadSize,
                            $"/movieaction/download/{sceneData.clip_id}/{downloadSize}/mp4",
                            -1,
                            HumanParser.ParseResolutionHeight(downloadSize),
                            -1,
                            -1,
                            HumanParser.ParseCodec("H.264")
                        ),
                        null
                    )
                );
            }

            return availableDownloads.OrderByDescending(d => d.AvailableVideoFile.ResolutionHeight).ToList();
        }

        foreach (var downloadFileSize in sceneData.DownloadFileSizes.Keys)
        {
            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        downloadFileSize,
                        $"/movieaction/download/{sceneData.clip_id}/{downloadFileSize}/mp4",
                        -1,
                        HumanParser.ParseResolutionHeight(downloadFileSize),
                        sceneData.DownloadFileSizes[downloadFileSize],
                        -1,
                        HumanParser.ParseCodec("H.264")
                    ),
                    null
                )
            );
        }

        return availableDownloads.OrderByDescending(d => d.AvailableVideoFile.FileSize).ToList();
    }
}

public class StringOrNumberConverter : JsonConverter<string>
{
    public override string Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.String)
        {
            return reader.GetString();
        }
        else if (reader.TryGetInt64(out long value))
        {
            return value.ToString();
        }
        else if (reader.TryGetDouble(out double doubleValue))
        {
            return doubleValue.ToString();
        }
        else
        {
            throw new JsonException($"Unable to parse string or number from {reader.TokenType}");
        }
    }

    public override void Write(Utf8JsonWriter writer, string value, JsonSerializerOptions options)
    {
        writer.WriteStringValue(value);
    }
}
