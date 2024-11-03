using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Globalization;
using System.Net;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[Site("xevunleashed")]
public class XevUnleashedRipper : ISiteScraper
{
    private readonly ILegacyDownloader _legacyDownloader;

    public XevUnleashedRipper(ILegacyDownloader legacyDownloader)
    {
        _legacyDownloader = legacyDownloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        // ReSharper disable once StringLiteralTypo
        var cookieIAgreeLink = page.Locator("#cwarningpopup").GetByRole(AriaRole.Link, new() { NameString = "I AGREE - ENTER" });
        if (await cookieIAgreeLink.IsVisibleAsync())
        {
            await cookieIAgreeLink.ClickAsync();
        }

        // ReSharper disable once StringLiteralTypo
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

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        var moviesLink = page.GetByRole(AriaRole.Link, new() { NameString = "Movies" });
        if (await moviesLink.IsVisibleAsync())
        {
            await moviesLink.ClickAsync();
        }

        var lastPageLink = page.Locator("div.global_pagination > ul > li.hide_mobile").Nth(-1);
        var lastPageRaw = await lastPageLink.TextContentAsync();

        if (!int.TryParse(lastPageRaw, out var lastPage))
        {
            throw new InvalidOperationException($"Could not parse number of out of lastPageRaw={lastPageRaw}");
        }

        return lastPage;
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, pageNumber);
        
        var releaseHandles = await page.Locator("div.update_details").ElementHandlesAsync();

        var listedReleases = new List<ListedRelease>();
        foreach (var releaseHandle in releaseHandles.Reverse())
        {
            var releaseIdAndUrl = await GetReleaseIdAsync(releaseHandle);
            listedReleases.Add(new ListedRelease(null, releaseIdAndUrl.Id, releaseIdAndUrl.Url, releaseHandle));
        }

        return listedReleases.AsReadOnly();
    }

    private static async Task GoToPageAsync(IPage page, int pageNumber)
    {
        await page.GotoAsync($"/access/categories/movies_{pageNumber}_d.html");
        await Task.Delay(5000);
    }

    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle currentRelease)
    {
        var shortName = await currentRelease.GetAttributeAsync("data-setid");
        // Link in the image and in the title. Both have same URL.
        var links = await currentRelease.QuerySelectorAllAsync("a");
        var url = await links.First().GetAttributeAsync("href");
        return new ReleaseIdAndUrl(shortName, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
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

        var scene = new Release(
            releaseUuid,
            site,
            subSite,
            releaseDate,
            releaseShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            tags,
            downloadOptionsAndHandles.Select(f => f.AvailableVideoFile).ToList(),
            "{}",
            DateTime.Now);
        
        var ogImageMeta = await page.QuerySelectorAsync("meta[property='og:image']");
        string ogImageUrl = await ogImageMeta.GetAttributeAsync("content");

        await _legacyDownloader.DownloadSceneImageAsync(scene, ogImageUrl, scene.Url);

        var videoElement = await page.QuerySelectorAsync("video");
        string trailerUrl = await videoElement.GetAttributeAsync("src");
        await _legacyDownloader.DownloadTrailerAsync(scene, trailerUrl, scene.Url);
        
        return scene;
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
            else if (description.Contains("PDF"))
            {
                continue;
            }
            else
            {
                throw new InvalidOperationException($"Could not parse width and height from description: {description}");
            }

            var url = await downloadLink.GetAttributeAsync("value");

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        description,
                        url,
                        resolutionWidth,
                        resolutionHeight,
                        -1,
                        -1,
                        string.Empty),
                    downloadLink));
        }
        return availableDownloads.OrderByDescending(d => d.AvailableVideoFile.ResolutionHeight).ToList();
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
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

        var headers = new WebHeaderCollection()
        {
            { HttpRequestHeader.Referer, page.Url },
            { HttpRequestHeader.Accept, "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" },
            { HttpRequestHeader.UserAgent, userAgent },
            { HttpRequestHeader.Cookie, cookieString }
        };

        return await _legacyDownloader.DownloadSceneDirectAsync(release, selectedDownload.AvailableVideoFile, downloadConditions.PreferredDownloadQuality, headers, referer: page.Url);
    }
}
