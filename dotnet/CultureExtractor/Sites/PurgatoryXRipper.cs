using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor.Sites;

[Site("purgatoryx")]
public class PurgatoryXRipper : ISiteScraper
{
    private readonly ILegacyDownloader _legacyDownloader;

    public PurgatoryXRipper(ILegacyDownloader legacyDownloader)
    {
        _legacyDownloader = legacyDownloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var enterButton = page.GetByRole(AriaRole.Link, new() { NameString = "Enter" });
        if (await enterButton.IsVisibleAsync())
        {
            await enterButton.ClickAsync();
        }

        var membersButton = page.Locator("#main-nav").GetByRole(AriaRole.Link, new() { NameString = "Members" });
        if (await membersButton.IsVisibleAsync())
        {
            await membersButton.ClickAsync();
        }

        if (await page.GetByPlaceholder("Username").IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username").ClickAsync();
            await page.GetByPlaceholder("Username").FillAsync(site.Username);
            await page.GetByPlaceholder("Password").ClickAsync();
            await page.GetByPlaceholder("Password").FillAsync(site.Password);

            await page.GetByRole(AriaRole.Button, new() { NameString = "Sign In" }).ClickAsync();
        }
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator("#main-nav").GetByRole(AriaRole.Link, new() { NameString = "Episodes " }).ClickAsync();
        var lastPageText = await page.Locator("ul.pagination > li").Nth(-2).TextContentAsync();
        return int.Parse(lastPageText);
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, site, subSite, pageNumber);
        
        var releaseHandles = await page.Locator("div.content-item").ElementHandlesAsync();

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
        var linkElement = await currentRelease.QuerySelectorAsync("div.container > div.row > a");
        var url = await linkElement.GetAttributeAsync("href");
        var idWithQueryStrings = url.Substring(url.LastIndexOf("/") + 1);
        var shortName = idWithQueryStrings.Contains("?")
            ? idWithQueryStrings.Substring(0, idWithQueryStrings.IndexOf("?"))
            : idWithQueryStrings;

        return new ReleaseIdAndUrl(shortName, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        await Task.Delay(5000);

        var releaseDateRaw = await page.Locator("p.content-meta > span.date").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw);

        var durationRaw = await page.Locator("p.content-meta > span.total-time").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("h1.title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performersRaw = await page.Locator("div.model-wrap > ul > li").ElementHandlesAsync();

        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersRaw)
        {
            var performerLink = await performerElement.QuerySelectorAsync("a");
            var performerUrl = await performerLink.GetAttributeAsync("href");
            var shortName = performerUrl.Substring(performerUrl.LastIndexOf("/") + 1);
            var performerNameElement = await performerElement.QuerySelectorAsync("h5");
            var nameRaw = await performerNameElement.TextContentAsync();
            var name = nameRaw.Replace("\n", "").Trim();
            performers.Add(new SitePerformer(shortName, name, performerUrl, "{}"));
        }

        var description = await page.Locator("div.description > p").TextContentAsync();
        description = description.Replace("\n", "").Trim();

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        var scene = new Release(
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
            new List<SiteTag>(),
            downloadOptionsAndHandles.Select(f => f.AvailableVideoFile).ToList(),
            "{}",
            DateTime.Now);
        
        var previewElement = await page.Locator(".jw-preview").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "").Replace(" background-size: cover;", "");
        await _legacyDownloader.DownloadSceneImageAsync(scene, backgroundImageUrl, "https://members.purgatoryx.com");
        
        return scene;
    }

    public async Task<Download> DownloadReleaseAsync(Release release, IPage page, DownloadConditions downloadConditions, IReadOnlyList<IRequest> requests)
    {
        await page.GotoAsync(release.Url);
        await page.WaitForLoadStateAsync();

        var performerNames = release.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        await page.GetByRole(AriaRole.Button).Filter(new() { HasTextString = "Download video" }).ClickAsync();

        var availableDownloads = await ParseAvailableDownloadsAsync(page);

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => availableDownloads.FirstOrDefault(f => f.AvailableVideoFile.ResolutionHeight == 360) ?? availableDownloads.Last(),
            PreferredDownloadQuality.Best => availableDownloads.First(),
            PreferredDownloadQuality.Worst => availableDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        return await _legacyDownloader.DownloadSceneAsync(release, page, selectedDownload.AvailableVideoFile, downloadConditions.PreferredDownloadQuality, async () =>
            await selectedDownload.ElementHandle.ClickAsync()
);
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadListItems = await page.Locator("div.download-video > ul.dropdown-menu > li").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();

        var firstElementText = await downloadListItems.First().TextContentAsync();
        var expectedTitle = "Choose Download Quality";
        if (!firstElementText.Contains(expectedTitle))
        {
            throw new InvalidOperationException($"First element in download list is expected to contain title {expectedTitle}.");
        }

        foreach (var downloadListItem in downloadListItems.Skip(1))
        {
            var titleElement = await downloadListItem.QuerySelectorAsync("span.download-title");
            var titleRaw = await titleElement.TextContentAsync();
            var title = titleRaw.Replace("\n", "").Trim();

            var sizeElement = await downloadListItem.QuerySelectorAsync("span.download-size");
            var sizeRaw = await sizeElement.TextContentAsync();
            var size = HumanParser.ParseFileSize(sizeRaw.Replace("\n", "").Trim());

            var resolutionElement = await downloadListItem.QuerySelectorAsync("span.download-dimension");
            var resolutionRaw = await resolutionElement.TextContentAsync();
            var resolutionWidth = HumanParser.ParseResolutionWidth(resolutionRaw.Replace("\n", "").Trim());
            var resolutionHeight = HumanParser.ParseResolutionHeight(resolutionRaw.Replace("\n", "").Trim());

            var codecElement = await downloadListItem.QuerySelectorAsync("span.download-codec");
            var codecRaw = await codecElement.TextContentAsync();
            var codec = HumanParser.ParseCodec(codecRaw.Replace("\n", "").Trim());

            var linkElement = await downloadListItem.QuerySelectorAsync("a");
            var url = await linkElement.GetAttributeAsync("href");

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        title,
                        url,
                        resolutionWidth,
                        resolutionHeight,
                        size,
                        -1,
                        codec),
                    downloadListItem));
        }
        return availableDownloads;
    }
}
