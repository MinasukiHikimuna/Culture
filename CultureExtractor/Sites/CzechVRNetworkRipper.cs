using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[PornSite("czechvr")]
[PornSite("czechvrcasting")]
[PornSite("czechvrfetish")]
[PornSite("czechvrintimacy")]
public class CzechVRNetworkRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public CzechVRNetworkRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var memberLoginHeader = page.GetByRole(AriaRole.Heading, new() { NameString = "Member login" });

        // TODO: sometimes this requires captcha, how to handle reliably?
        if (await memberLoginHeader.IsVisibleAsync())
        {
            // Login requires CAPTCHA so we need to create a headful browser
            /*IPage loginPage = await PlaywrightFactory.CreatePageAsync(site, new BrowserSettings(false));
            await loginPage.WaitForLoadStateAsync();*/

            var loginPage = page;

            await loginPage.GetByPlaceholder("Username").TypeAsync(site.Username);
            await loginPage.GetByPlaceholder("Password").TypeAsync(site.Password);
            await loginPage.GetByRole(AriaRole.Button, new() { NameString = "CLICK HERE TO LOGIN" }).ClickAsync();
            await loginPage.GetByRole(AriaRole.Button, new() { NameString = "CLICK HERE TO LOGIN" }).WaitForAsync(new LocatorWaitForOptions()
            {
                State = WaitForSelectorState.Detached
            });
            await loginPage.WaitForLoadStateAsync();

            await Task.Delay(1000);

            Log.Information($"Logged in as {site.Username}.");
        }
        else
        {
            Log.Verbose("Login was not necessary.");
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GetByRole(AriaRole.Link, new() { NameString = "VIDEOS" }).ClickAsync();
        await page.WaitForLoadStateAsync();

        var siteName = site.ShortName switch
        {
            "czechvr" => "Czech VR",
            "czechvrfetish" => "CVR Fetish",
            "czechvrcasting" => "CVR Casting",
            "czechvrintimacy" => "VR Intimacy",
            _ => string.Empty
        };

        await page.Locator("#Filtrace").GetByRole(AriaRole.Link, new() { NameString = siteName }).ClickAsync();
        await page.WaitForLoadStateAsync();
        await Task.Delay(5000);

        var lastPageButton = await page.QuerySelectorAsync("div.strankovani > span:last-child > a.last");
        var lastPageUrl = await lastPageButton.GetAttributeAsync("href");

        string linkPattern = @"next=(\d+)";
        Match linkMatch = Regex.Match(lastPageUrl, linkPattern);
        if (!linkMatch.Success)
        {
            Log.Error($"Could not parse last page URL video count from URL {lastPageUrl} using pattern {linkPattern}.");
            return 0;
        }

        var totalVideoCount = int.Parse(linkMatch.Groups[1].Value);

        var videosOnCurrentPage = await page.Locator("div.foto").ElementHandlesAsync();

        return (int)Math.Ceiling((double)totalVideoCount / videosOnCurrentPage.Count());
    }

    public async Task<IReadOnlyList<IndexScene>> GetCurrentScenesAsync(Site site, IPage page, IReadOnlyList<IRequest> requests)
    {
        var sceneHandles = await page.Locator("div.tagyCenter > div.postTag").ElementHandlesAsync();

        var indexScenes = new List<IndexScene>();
        foreach (var sceneHandle in sceneHandles.Reverse())
        {
            var sceneIdAndUrl = await GetSceneIdAsync(site, sceneHandle);
            indexScenes.Add(new IndexScene(null, sceneIdAndUrl.Id, sceneIdAndUrl.Url, sceneHandle));
        }

        return indexScenes.AsReadOnly();
    }

    public async Task<SceneIdAndUrl> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var linkElement = await currentScene.QuerySelectorAsync("div.nazev > h2 > a");
        var relativeUrl = await linkElement.GetAttributeAsync("href");
        if (relativeUrl.StartsWith("./"))
        {
            relativeUrl = relativeUrl.Substring(2);
        }

        var titleElement = await currentScene.QuerySelectorAsync("div.nazev > h2");
        var title = await titleElement.TextContentAsync();

        string pattern = @" (?<id>\d+) - ";
        Match match = Regex.Match(title, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($@"Could not determine ID from ""{title}"" using pattern {pattern}. Skipping...");
        }

        var sceneShortName = match.Groups["id"].Value;

        return new SceneIdAndUrl(sceneShortName, relativeUrl);
    }   

    public async Task<Scene> ScrapeSceneAsync(Guid sceneUuid, Site site, SubSite subSite, string url, string sceneShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var releaseDate = await ScrapeReleaseDateAsync(page);
        var duration = await ScrapeDurationAsync(page);
        var description = await ScrapeDescriptionAsync(page);
        var title = await ScrapeTitleAsync(page);
        var performers = await ScrapePerformersAsync(page);
        var tags = await ScrapeTagsAsync(page);
        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        var scene = new Scene(
            UuidGenerator.Generate(),
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
        return scene;
    }

    public async Task DownloadAdditionalFilesAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene, IReadOnlyList<IRequest> requests)
    {
        if (!_downloader.SceneImageExists(scene))
        {
            var previewElement = await currentScene.QuerySelectorAsync("img");
            var originalUrl = await previewElement.GetAttributeAsync("src");
            await _downloader.DownloadSceneImageAsync(scene, originalUrl);
        }
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        await Task.Delay(3000);

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        return await _downloader.DownloadSceneAsync(scene, page, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            await page.EvaluateAsync(
                $"document.querySelector('a[href=\"{selectedDownload.DownloadOption.Url}\"')" +
                $".parentElement" +
                $".parentElement" +
                $".parentElement" +
                $".previousElementSibling" +
                $".click()");
            await page.Locator($"a[href=\"{selectedDownload.DownloadOption.Url}\"]").ClickAsync();
        });
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadOptions = new List<DownloadOptionElements>();
        var deviceElements = await page.Locator("ul.zalozky > li:not(.download)").ElementHandlesAsync();
        var downloadElements = await page.Locator("ul.zalozky > li.download").ElementHandlesAsync();

        for (var i = 0; i < deviceElements.Count; i++)
        {
            var deviceElement = deviceElements[i];
            var downloadElement = downloadElements[i];

            var downloadDescriptionElements = await downloadElement.QuerySelectorAllAsync("div.nazevpopis");
            var downloadLinkElements = await downloadElement.QuerySelectorAllAsync("div.dlnew > div.dlp > a");

            for (var j = 0; j < downloadDescriptionElements.Count; j++)
            {
                downloadOptions.Add(new DownloadOptionElements(downloadElement, downloadDescriptionElements[j], downloadLinkElements[j]));
            }
        }

        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadOption in downloadOptions)
        {
            var descriptionRaw = await downloadOption.Details.TextContentAsync();
            var description = descriptionRaw.Replace("\t", "").Replace("\n", "").Trim();

            var resolutionWidth = HumanParser.ParseResolutionWidth(descriptionRaw);
            var resolutionHeight = HumanParser.ParseResolutionHeight(descriptionRaw);

            var url = await downloadOption.Link.GetAttributeAsync("href");
            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        HumanParser.ParseFileSize(description),
                        HumanParser.ParseFps(description),
                        HumanParser.ParseCodec(description),
                        url),
                    null));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.FileSize).ToList();
    }

    private record DownloadOptionElements(IElementHandle Device, IElementHandle Details, IElementHandle Link);

    private async Task<DateOnly> ScrapeReleaseDateAsync(IPage page)
    {
        var releaseDateRaw = await page.Locator("div.nazev > div.desktop > div.datum").TextContentAsync();
        return DateOnly.Parse(releaseDateRaw);
    }

    private async Task<string> ScrapeTitleAsync(IPage page)
    {
        var title = await page.Locator("div.post > div.left > div.nazev > h2").TextContentAsync();
        string pattern = @"\w+ \d+ - (.*)";
        Match match = Regex.Match(title, pattern);
        if (!match.Success)
        {
            Log.Warning($@"Could not determine title from ""{title}"" using pattern {pattern}. Skipping...");
            throw new Exception();
        }

        return match.Groups[1].Value;
    }

    private async Task<IList<SitePerformer>> ScrapePerformersAsync(IPage page)
    {
        var castElements = await page.Locator("div.post > div.left > div.nazev > div.desktop > div.featuring > a").ElementHandlesAsync();
        var performers = new List<SitePerformer>();
        foreach (var castElement in castElements)
        {
            var castUrl = await castElement.GetAttributeAsync("href");
            if (castUrl.StartsWith("./"))
            {
                castUrl = castUrl.Substring(2);
            }

            var castId = castUrl.Replace("model-", "");
            var castName = await castElement.TextContentAsync();
            performers.Add(new SitePerformer(castId, castName, castUrl));
        }
        return performers.AsReadOnly();
    }

    private async Task<IList<SiteTag>> ScrapeTagsAsync(IPage page)
    {
        var tagElements = await page.Locator("div.post > div.left > div.tagy > div.tag > a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            if (tagUrl.StartsWith("./"))
            {
                tagUrl = tagUrl.Substring(2);
            }

            var tagId = tagUrl.Replace("tag-", "");
            var tagName = await tagElement.TextContentAsync();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }
        return tags;
    }

    private async Task<TimeSpan> ScrapeDurationAsync(IPage page)
    {
        var duration = await page.Locator("div.nazev > div.desktop > div.cas > span.desktop").TextContentAsync();
        var components = duration.Split(":");
        return TimeSpan.FromMinutes(int.Parse(components[0])).Add(TimeSpan.FromSeconds(int.Parse(components[1])));
    }

    private async Task<string> ScrapeDescriptionAsync(IPage page)
    {
        var content = await page.Locator("div.post > div.left > div.text").TextContentAsync();
        return content.Replace("\n", "").Replace("\t", "").Trim();
    }

    public Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        throw new NotImplementedException();
    }
}
