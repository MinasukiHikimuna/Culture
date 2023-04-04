using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Globalization;
using System.Net;

namespace CultureExtractor.Sites;

[PornNetwork("xevunleashed")]
[PornSite("xevunleashed")]
public class XevUnleashedRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public XevUnleashedRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var cookieIAgreeLink = page.Locator("#cwarningpopup").GetByRole(AriaRole.Link, new() { NameString = "I AGREE - ENTER" });
        if (await cookieIAgreeLink.IsVisibleAsync())
        {
            await cookieIAgreeLink.ClickAsync();
        }

        var adultIAgreeLink = page.Locator("#warningpopup").GetByRole(AriaRole.Link, new() { NameString = "I AGREE - ENTER" });
        if (await adultIAgreeLink.IsVisibleAsync())
        {
            await adultIAgreeLink.ClickAsync();
        }

        var signInLink = page.GetByRole(AriaRole.Link).Filter(new LocatorFilterOptions() { HasText = "Sign in " });
        if (await signInLink.IsVisibleAsync())
        {
            await signInLink.ClickAsync();
        }

        await page.Locator("[name='Login']").FillAsync(site.Username);
        await page.Locator("[name='Pass']").FillAsync(site.Password);
        await page.Locator("[name='Submit']").ClickAsync();

        Log.Warning("CAPTCHA required! Enter manually!");
        Console.ReadLine();

        await Task.Delay(5000);
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        var moviesLink = page.GetByRole(AriaRole.Link, new() { NameString = "Movies" });
        if (await moviesLink.IsVisibleAsync())
        {
            await moviesLink.ClickAsync();
        }

        var lastPageLink = page.Locator("div.global_pagination > ul > li.hide_mobile").Nth(-1);
        var lastPageRaw = await lastPageLink.TextContentAsync();
        return int.Parse(lastPageRaw);
    }

    public async Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/access/categories/movies_{pageNumber}_d.html");
        await Task.Delay(5000);
    }

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var currentScenes = await page.Locator("div.update_details").ElementHandlesAsync();
        return currentScenes
            .Reverse()
            .ToList()
            .AsReadOnly();
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var shortName = await currentScene.GetAttributeAsync("data-setid");
        // Link in the image and in the title. Both have same URL.
        var links = await currentScene.QuerySelectorAllAsync("a");
        var url = await links.First().GetAttributeAsync("href");
        return (url, shortName);
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
    {
        var releaseDateElement = await page.QuerySelectorAsync("div.cell.update_date");
        string releaseDateRaw = await releaseDateElement.TextContentAsync();
        releaseDateRaw = releaseDateRaw.Trim();
        DateOnly releaseDate = DateOnly.ParseExact(releaseDateRaw, "MM/dd/yyyy", CultureInfo.InvariantCulture);

        await page.GetByRole(AriaRole.Button, new() { NameString = "Play" }).Nth(1).ClickAsync();
        await page.GetByRole(AriaRole.Button, new() { NameString = "Pause" }).ClickAsync();
        var durationRaw = await page.Locator("span.mejs__duration").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("div.title_bar span").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performers = new List<SitePerformer>() { new SitePerformer("xev", "Xev Bellringer", "")};

        var descriptionRaw = await page.Locator("span.update_description").TextContentAsync();
        string description = descriptionRaw.Trim();

        var tagElements = await page.Locator("span.update_tags a").ElementHandlesAsync();
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Replace(site.Url + "/access/categories/", "").Replace(".html", "");
            var tagNameRaw = await tagElement.TextContentAsync();
            var tagName = tagNameRaw.Replace("\n", "").Trim();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
            null,
            site,
            subSite,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            "{}"
        );
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadLinksRaw = await page.Locator("select#download_select option").ElementHandlesAsync();
        var downloadLinks = downloadLinksRaw.Skip(1).ToList();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", " ").Trim();

            var resolutionWidth = -1;
            var resolutionHeight = -1;
            if (description.Contains("MP4 SD"))
            {
                resolutionWidth = 1280;
                resolutionHeight = 720;
            }
            else if (description.Contains("MP4 HD"))
            {
                resolutionWidth = 1920;
                resolutionHeight = 1080;
            }
            else if (description.Contains("MP4 4K"))
            {
                resolutionWidth = 3840;
                resolutionHeight = 2160;
            }
            else
            {
                throw new InvalidOperationException($"Could not parse width and height from description: {description}");
            }

            var url = await downloadLink.GetAttributeAsync("value");

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        resolutionWidth,
                        resolutionHeight,
                        -1,
                        -1,
                        string.Empty,
                        url),
                    downloadLink));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.ResolutionHeight).ToList();
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var previewElement = await scenePage.Locator("div.mejs__poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\"); width: 100%; height: 100%; display: none;", "");

        await _downloader.DownloadSceneImageAsync(scene, scene.Site.Url + backgroundImageUrl, scene.Url);
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IList<CapturedResponse> responses)
    {
        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        var userAgent = await page.EvaluateAsync<string>("() => navigator.userAgent");
        var cookieString = await page.EvaluateAsync<string>("() => document.cookie");

        var headers = new Dictionary<HttpRequestHeader, string>
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };

        return await _downloader.DownloadSceneDirectAsync(scene, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        throw new NotImplementedException();
    }
}
