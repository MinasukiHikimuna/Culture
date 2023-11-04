using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[PornSite("allfinegirls")]
[PornSite("wowgirls")]
[PornSite("wowporn")]
[PornSite("ultrafilms")]
public class WowNetworkRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public WowNetworkRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var signInButton = page.GetByRole(AriaRole.Link, new() { NameString = "Sign in" });
        var emailInput = page.GetByPlaceholder("E-Mail");
        var passwordInput = page.GetByPlaceholder("Password");
        var getInsideButton = page.GetByText("Get Inside");

        if (await signInButton.IsVisibleAsync())
        {
            await signInButton.ClickAsync();
            await page.WaitForLoadStateAsync();
        }

        if (await getInsideButton.IsVisibleAsync())
        {
            await emailInput.TypeAsync(site.Username);
            await passwordInput.TypeAsync(site.Password);
            await getInsideButton.ClickAsync();
            await page.WaitForLoadStateAsync();
        }
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = "Films" }).Nth(1).ClickAsync();
        await page.WaitForLoadStateAsync();

        while ((await page.Locator(".cf_s_site").ElementHandlesAsync()).Count() > 0)
        {
            var elementHandles = await page.Locator(".cf_s_site").ElementHandlesAsync();
            var elementHandle = elementHandles[0];

            await elementHandle.ClickAsync();
            await elementHandle.IsHiddenAsync();
            await page.WaitForLoadStateAsync();
            await Task.Delay(5000);
        }

        var siteName = site.ShortName switch
        {
            "allfinegirls" => "All Fine Girls",
            "wowgirls" => "Wow Girls",
            "wowporn" => "Wow Porn",
            _ => string.Empty
        };

        if (!string.IsNullOrWhiteSpace(siteName))
        {
            await page.GetByRole(AriaRole.Complementary).GetByText(siteName).ClickAsync();
            await page.WaitForSelectorAsync(".cf_s_site");
            await page.WaitForLoadStateAsync();
        }

        var totalPagesStr = await page.Locator("div.pages > span").Last.TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);
        return totalPages;
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, site, subSite, pageNumber);
        
        var sceneHandles = await page.Locator("section.cf_content > ul > li > div.content_item > a.icon").ElementHandlesAsync();

        var indexScenes = new List<ListedRelease>();
        foreach (var sceneHandle in sceneHandles.Reverse())
        {
            var sceneIdAndUrl = await GetSceneIdAsync(site, sceneHandle);
            indexScenes.Add(new ListedRelease(null, sceneIdAndUrl.Id, sceneIdAndUrl.Url, sceneHandle));
        }

        return indexScenes.AsReadOnly();
    }

    private Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        throw new NotImplementedException();
    }
    
    private static async Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var relativeUrl = await currentScene.GetAttributeAsync("href");
        var url = site.Url + relativeUrl;

        string pattern = @"/film/(?<id>\w+)/.*";
        Match match = Regex.Match(relativeUrl, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Could not parse ID from {url} using pattern {pattern}.");
        }

        return new SceneIdAndUrl(match.Groups["id"].Value, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid sceneUuid, Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        await page.WaitForLoadStateAsync();

        var releaseDate = await ScrapeReleaseDateAsync(page);
        var duration = await ScrapeDurationAsync(page);
        var description = await ScrapeDescriptionAsync(page);
        var title = await ScrapeTitleAsync(page);
        var performers = await ScrapePerformersAsync(page);
        var tags = await ScrapeTagsAsync(page);
        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        var scene = new Release(
            sceneUuid,
            site,
            null,
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
        
        if (_downloader.SceneImageExists(scene))
        {
            return scene;
        }

        // TODO: Fix this
        /*var previewElement = await currentScene.QuerySelectorAsync("span > img");
        var originalUrl = await previewElement.GetAttributeAsync("src");

        string regexPattern = "icon_\\d+x\\d+.jpg";

        // We can't be sure which are found so we need to cycle through them.
        var candidates = new List<string>()
            {
                "icon_3840x2160.jpg",
                "icon_1920x1080.jpg",
                "icon_1280x720.jpg",
            }
            .Select(fileName => Regex.Replace(originalUrl, regexPattern, fileName))
            .Concat(new List<string> { originalUrl });

        foreach (var candidate in candidates)
        {
            try
            {

                await _downloader.DownloadSceneImageAsync(scene, candidate);
                Log.Verbose($"Successfully downloaded preview from {candidate}.");
                break;
            }
            catch (WebException ex)
            {
                if (ex.Status == WebExceptionStatus.ProtocolError && (ex.Response as HttpWebResponse)?.StatusCode == HttpStatusCode.NotFound)
                {
                    Log.Verbose($"Got 404 for preview from {candidate}.");
                    continue;
                }

                throw;
            }
        }*/
        
        return scene;
    }

    private async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var releaseDateRaw = await page.Locator("ul.details > li.date").TextContentAsync();
        return DateOnly.Parse(releaseDateRaw);
    }

    private async Task<string> ScrapeTitleAsync(IPage page)
    {
        var title = await page.Locator("section.content_header > div.content_info > div.title").TextContentAsync();
        return title;
    }

    private async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page)
    {
        var castElements = await page.Locator("section.content_header > div.content_info > ul.details > li.models > a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");
            var castId = castUrl.Substring(castUrl.LastIndexOf("/girl/") + "/girl/".Length);
            var castName = await castElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl));
        }
        return performers.AsReadOnly();
    }

    private async Task<IList<SiteTag>> ScrapeTagsAsync(IPage page)
    {
        var tagElements = await page.Locator("section.content_header > div.content_info > ul.genres > li > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = await tagElement.TextContentAsync();
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }
        return tags;
    }

    private async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var duration = await page.Locator("ul.details > li.duration").TextContentAsync();
        if (TimeSpan.TryParse(duration, out TimeSpan timespan))
        {
            return timespan;
        }

        return TimeSpan.FromSeconds(0);
    }

    private async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        if (!await page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).IsVisibleAsync())
        {
            return string.Empty;
        }

        await page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).ClickAsync();
        var elementHandles = await page.Locator("div.movie-details div.info-container div p").ElementHandlesAsync();
        var descriptionParagraphs = new List<string>();
        foreach (var elementHandle in elementHandles)
        {
            var descriptionParagraph = await elementHandle.TextContentAsync();
            if (!string.IsNullOrWhiteSpace(descriptionParagraph))
            {
                descriptionParagraphs.Add(descriptionParagraph);
            }
        }
        return string.Join("\r\n\r\n", descriptionParagraphs);
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        await page.GotoAsync(release.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var performerNames = release.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        return await _downloader.DownloadSceneAsync(release, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
            await selectedDownload.ElementHandle.ClickAsync()
);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadItems = await page.Locator("div.ct_dl_items > ul > li").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadItem in downloadItems)
        {
            var downloadLinkElement = await downloadItem.QuerySelectorAsync("a");
            var downloadUrl = await downloadLinkElement.GetAttributeAsync("href");
            var resolutionRaw = await downloadLinkElement.TextContentAsync();
            resolutionRaw = resolutionRaw.Replace("\n", "").Trim();
            var resolutionWidth = HumanParser.ParseResolutionWidth(resolutionRaw);
            var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionRaw);
            var codecElement = await downloadItem.QuerySelectorAsync("span.format");
            var codecRaw = await codecElement.InnerTextAsync();
            var codec = HumanParser.ParseCodec(codecRaw);
            var fpsElement = await downloadItem.QuerySelectorAsync("span.fps");
            var fpsRaw = await fpsElement.InnerTextAsync();
            var sizeElement = await downloadItem.QuerySelectorAsync("span.size");
            var sizeRaw = await sizeElement.InnerTextAsync();
            var size = HumanParser.ParseFileSize(sizeRaw);

            var descriptionRaw = await downloadItem.TextContentAsync();
            var description = descriptionRaw.Replace("\n", "").Trim();

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        size,
                        double.Parse(fpsRaw.Replace("fps", "")),
                        codec,
                        downloadUrl),
                    downloadLinkElement));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.ResolutionWidth).ThenByDescending(d => d.DownloadOption.Fps).ToList();
    }
}
