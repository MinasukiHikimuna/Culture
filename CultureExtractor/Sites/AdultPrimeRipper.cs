using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Globalization;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[Site("adultprime")]
public class AdultPrimeRipper : ISiteScraper, ISubSiteScraper
{
    private readonly ILegacyDownloader _legacyDownloader;
    private readonly IRepository _repository;

    public AdultPrimeRipper(ILegacyDownloader legacyDownloader, IRepository repository)
    {
        _legacyDownloader = legacyDownloader;
        _repository = repository;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        await Task.Delay(5000);

        var enterAdultPrimeLink = page.GetByRole(AriaRole.Link, new() { NameString = "Enter AdultPrime" });
        if (await enterAdultPrimeLink.IsVisibleAsync())
        {
            await enterAdultPrimeLink.ClickAsync();
            await Task.Delay(5000);
        }

        var loginLink = page.GetByRole(AriaRole.Link, new() { NameString = "LOG IN" });
        if (await loginLink.IsVisibleAsync())
        {
            await loginLink.ClickAsync();

            var usernameInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Email" });
            if (await usernameInput.IsVisibleAsync())
            {
                await usernameInput.ClickAsync();
                await usernameInput.FillAsync(site.Username);

                var passwordInput = page.GetByRole(AriaRole.Textbox, new() { NameString = "Password" });
                await passwordInput.ClickAsync();
                await passwordInput.FillAsync(site.Password);

                Log.Warning("CAPTCHA required! Enter manually!");
                Console.ReadLine();

                await page.GetByRole(AriaRole.Button, new() { NameString = "Login" }).ClickAsync();
                await page.WaitForLoadStateAsync();

                await Task.Delay(5000);
            }
        }
    }

    public async Task<int> NavigateToReleasesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.Locator("ul.navbar-nav > li.nav-item > a.nav-link").Nth(0).ClickAsync();
        await page.WaitForLoadStateAsync();

        var lastPageElement = await page.QuerySelectorAsync("ul.pagination li.page-item div.dropdown div.dropdown-menu a:last-of-type");
        var lastPage = await lastPageElement.TextContentAsync();

        return int.Parse(lastPage);
    }

    public async Task<IReadOnlyList<ListedRelease>> GetCurrentReleasesAsync(Site site, SubSite subSite, IPage page, IReadOnlyList<IRequest> requests, int pageNumber)
    {
        await GoToPageAsync(page, subSite, pageNumber);
        
        var releaseHandles = await page.Locator("div.row.portal-grid div.portal-video-wrapper").ElementHandlesAsync();

        var listedReleases = new List<ListedRelease>();
        foreach (var releaseHandle in releaseHandles.Reverse())
        {
            var releaseIdAndUrl = await GetReleaseIdAsync(releaseHandle);
            listedReleases.Add(new ListedRelease(null, releaseIdAndUrl.Id, releaseIdAndUrl.Url, releaseHandle));
        }

        return listedReleases.AsReadOnly();
    }

    private static async Task GoToPageAsync(IPage page, SubSite subSite, int pageNumber)
    {
        await page.GotoAsync($"/studios/videos?website={subSite.Name}&page={pageNumber}");
        await Task.Delay(1000);
    }

    private static async Task<ReleaseIdAndUrl> GetReleaseIdAsync(IElementHandle currentRelease)
    {
        var overlayElement = await currentRelease.QuerySelectorAsync("div.overlay");
        var aElement = await overlayElement.QuerySelectorAsync("a");
        var url = await aElement.GetAttributeAsync("href");

        var shortName = await overlayElement.GetAttributeAsync("data-id");

        return new ReleaseIdAndUrl(shortName, url);
    }

    public async Task<Release> ScrapeReleaseAsync(Guid releaseUuid, Site site, SubSite subSite, string url, string releaseShortName, IPage page, IReadOnlyList<IRequest> requests)
    {
        var releaseDateElement = await page.QuerySelectorAsync("p.update-info-line:nth-of-type(1) i.fa-calendar + b");
        string releaseDateRaw = await releaseDateElement.TextContentAsync();
        DateOnly releaseDate = DateOnly.ParseExact(releaseDateRaw, "dd.MM.yyyy", CultureInfo.InvariantCulture);

        var durationElement = await page.QuerySelectorAsync("p.update-info-line:nth-of-type(1) i.fa-clock-o + b");
        var durationRaw = await durationElement.TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("h2.update-info-title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        IElementHandle performerContainer = null;
        ILocator performerContainerLocator = page.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Performer:" });
        ILocator performersContainerLocator = page.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Performers:" });
        if (await performerContainerLocator.IsVisibleAsync())
        {
            performerContainer = await performerContainerLocator.ElementHandleAsync();
        }
        else if (await performersContainerLocator.IsVisibleAsync())
        {
            performerContainer = await performersContainerLocator.ElementHandleAsync();
        }

        var performers = new List<SitePerformer>();
        if (performerContainer != null)
        {
            var performersRaw = await performerContainer.QuerySelectorAllAsync("a");

            foreach (var performerElement in performersRaw)
            {
                var performerUrl = await performerElement.GetAttributeAsync("href");
                var nameRaw = await performerElement.TextContentAsync();
                var name = nameRaw.Trim();
                var shortName = name.Replace(" ", "+");
                performers.Add(new SitePerformer(shortName, name, performerUrl));
            }
        }

        var descriptionRaw = await page.Locator("p.ap-limited-description-text").TextContentAsync();
        string description = descriptionRaw.Trim();

        var tagsContainer = await page.Locator("p.update-info-line").Filter(new LocatorFilterOptions() { HasText = "Niches:" }).ElementHandleAsync();
        var tagElements = await tagsContainer.QuerySelectorAllAsync("a");
        var tags = new List<SiteTag>();
        foreach (var tagElement in tagElements)
        {
            var tagUrl = await tagElement.GetAttributeAsync("href");
            var tagId = tagUrl.Replace("/studios/videos?niche=", "");
            var tagNameRaw = await tagElement.TextContentAsync();
            var tagName = tagNameRaw.Replace("\n", "").Trim();
            tags.Add(new SiteTag(tagId, tagName, tagUrl));
        }

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        var release = new Release(
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
        
        var previewElement = await page.Locator("div.vjs-poster").ElementHandleAsync();
        var style = await previewElement.GetAttributeAsync("style");
        var backgroundImageUrl = style.Replace("background-image: url(\"", "").Replace("\");", "");

        await _legacyDownloader.DownloadSceneImageAsync(release, backgroundImageUrl, release.Url);

        return release;
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

        return await _legacyDownloader.DownloadSceneAsync(release, page, selectedDownload.AvailableVideoFile, downloadConditions.PreferredDownloadQuality, async () =>
        {
            await selectedDownload.ElementHandle.ClickAsync();
        });
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadIcon = await page.Locator("i.fa-download").ElementHandleAsync();
        var downloadContainer = await downloadIcon.EvaluateHandleAsync("element => element.parentNode");
        var downloadLinks = await downloadContainer.AsElement().QuerySelectorAllAsync("a");
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", " ").Trim();

            var resolutionHeight = HumanParser.ParseResolutionHeight(description);

            var url = await downloadLink.GetAttributeAsync("href");

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new AvailableVideoFile(
                        "video",
                        "scene",
                        description,
                        url,
                        -1,
                        resolutionHeight,
                        -1,
                        -1,
                        string.Empty),
                    downloadLink));
        }
        return availableDownloads.OrderByDescending(d => d.AvailableVideoFile.ResolutionHeight).ToList();
    }

    public async Task<IReadOnlyList<SubSite>> GetSubSitesAsync(Site site, IPage page)
    {
        await page.GotoAsync("/studios");
        await Task.Delay(5000);

        var existingSubSites = await _repository.GetSubSitesAsync(site.Uuid);
        
        var studioHandles = await page.Locator("div.studio-item-container").ElementHandlesAsync();
        List<SubSite> subSites = new List<SubSite>();
        foreach (var studioHandle in studioHandles)
        {
            // get the <a> element inside the current studio container
            var aElementHandle = await studioHandle.QuerySelectorAsync("a");
            if (aElementHandle == null)
            {
                continue;
            }

            var imgElementHandle = await studioHandle.QuerySelectorAsync(":scope > img");
            if (imgElementHandle != null)
            {
                continue;
            }

            // get the href attribute of the <a> element
            var hrefProperty = await aElementHandle.GetPropertyAsync("href");
            var hrefValue = await hrefProperty.JsonValueAsync<string>();

            // extract the subsite URL and site name from the href value
            var subsiteUrl = hrefValue;
            if (subsiteUrl.StartsWith(site.Url))
            {
                subsiteUrl = subsiteUrl.Substring(site.Url.Length);
            }

            var siteName = subsiteUrl.Replace("/studios/studio/", "");

            var uuid = existingSubSites.FirstOrDefault(s => s.ShortName == siteName)?.Uuid ?? UuidGenerator.Generate();
            subSites.Add(new SubSite(uuid, siteName, siteName, "{}", site));
        }

        var uniqueSubSites = subSites
            .GroupBy(s => s.Name)
            .Select(g => g.First())
            .OrderBy(s => s.Name)
            .ToList();

        return uniqueSubSites.AsReadOnly();
    }

    public async Task<int> NavigateToSubSiteAndReturnPageCountAsync(Site site, SubSite subSite, IPage page)
    {
        await page.GotoAsync($"/studios/videos?website={subSite.Name}");

        var pageLinkHandles = await page.QuerySelectorAllAsync("div#api-pagination ul li:not(.disabled) a.page-link:not(.next)");
        if (pageLinkHandles.Count == 0)
        {
            throw new InvalidOperationException($"Could not find page links for subsite {subSite.Name}.");
        }

        var lastPageLinkHandle = pageLinkHandles.Last();
        var lastPageLinkText = await lastPageLinkHandle.TextContentAsync();
        return int.Parse(lastPageLinkText);
    }
}
