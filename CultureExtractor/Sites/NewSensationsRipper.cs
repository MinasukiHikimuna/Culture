using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

[PornNetwork("newsensations")]
[PornSite("newsensations")]
public class NewSensationsRipper : ISiteScraper
{
    private readonly IDownloader _downloader;

    public NewSensationsRipper(IDownloader downloader)
    {
        _downloader = downloader;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var usernameInput = page.GetByPlaceholder("Username");
        if (await usernameInput.IsVisibleAsync())
        {
            await page.GetByPlaceholder("Username").ClickAsync();
            await page.GetByPlaceholder("Username").FillAsync(site.Username);

            await page.GetByPlaceholder("password").ClickAsync();
            await page.GetByPlaceholder("password").FillAsync(site.Password);

            await page.GetByText("remember me").ClickAsync();

            await page.GetByRole(AriaRole.Button, new() { NameString = "Login to Our Members Area" }).ClickAsync();
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.WaitForLoadStateAsync();

        await page.GetByRole(AriaRole.Navigation).GetByRole(AriaRole.Link, new() { NameString = "Network" }).ClickAsync();
        await page.Locator(".videothumb > a").First.ClickAsync();
        await page.GetByRole(AriaRole.Link, new() { NameString = "view all >" }).First.ClickAsync();

        await page.WaitForLoadStateAsync();

        var lastPage = await page.Locator("div.pagination > ul > li:not(.pagination_jump) > a").Last.TextContentAsync();
        return int.Parse(lastPage);
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        var url = await scenePage.GetAttributeAsync("img#default_poster", "src");
        await _downloader.DownloadSceneImageAsync(scene, url);
    }

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var currentScenes = await page.Locator("div.videoArea > div.videoBlock").ElementHandlesAsync();
        return currentScenes;
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        try
        {
            var thumbLinkElement = await currentScene.QuerySelectorAsync("a");
            var url = await thumbLinkElement.GetAttributeAsync("href");
            var pattern = @"id=(\d+)&";
            Match match = Regex.Match(url, pattern);
            if (!match.Success)
            {
                throw new InvalidOperationException($"Could not parse numerical ID from {url} using pattern {pattern}.");
            }

            string shortName = match.Groups[1].Value;
            return (url, shortName);

        }
        catch
        {

        }

        return (null, null);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        var url = await page.Locator("div.pagination > ul > li:last-child > a").GetAttributeAsync("href");

        for (int i = 0; i < 3;  i++)
        {
            try
            {
                await page.GotoAsync(url);
            }
            catch (TimeoutException)
            {
                // Let's try again. This happens so often with New Sensations that no sense to spam log with it.
            }
        }
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, SubSite subSite, string url, string sceneShortName, IPage page, IList<CapturedResponse> responses)
    {
        var releaseDateRaw = await page.Locator("div.datePhotos > span").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw);

        var datePhotosTextRaw = await page.Locator("div.datePhotos").TextContentAsync();
        string pattern = @"(?<minutes>[0-9]+) Minutes of Video";
        Match match = Regex.Match(datePhotosTextRaw, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Unable to parse date from {datePhotosTextRaw} using pattern {pattern}");
        }

        var duration = TimeSpan.FromMinutes(int.Parse(match.Groups["minutes"].Value));

        var titleRaw = await page.Locator("div.indRight > h2").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performersRaw = await page.Locator("p > span.update_models > a").ElementHandlesAsync();

        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersRaw)
        {
            var performerUrl = await performerElement.GetAttributeAsync("href");
            var shortName = performerUrl.Replace("sets.php?id=", "");
            var name = await performerElement.TextContentAsync();
            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        string descriptionRaw = await page.Locator("div.indLeft > div.description > p").TextContentAsync();
        string description = descriptionRaw.StartsWith("Description: ")
            ? descriptionRaw.Substring("Description: ".Length)
            : descriptionRaw;

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
            null,
            site,
            null,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            new List<SiteTag>(),
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList(),
            "{}"
        );
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions, IList<CapturedResponse> responses)
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
            await page.Locator("div#download_select > a").ClickAsync();
            await selectedDownload.ElementHandle.ClickAsync();
        });
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadLinks = await page.Locator("div#download_select > ul > li").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", "").Trim();

            var resolutionHeight = HumanParser.ParseResolutionHeight(description);

            var linkElement = await downloadLink.QuerySelectorAsync("a");
            var url = await linkElement.GetAttributeAsync("href");

            availableDownloads.Add(
                new DownloadDetailsAndElementHandle(
                    new DownloadOption(
                        description,
                        -1,
                        resolutionHeight,
                        HumanParser.ParseFileSize(description),
                        -1,
                        string.Empty,
                        url),
                    downloadLink));
        }
        return availableDownloads.OrderByDescending(d => d.DownloadOption.FileSize).ToList();
    }

    public Task GoToPageAsync(IPage page, Site site, SubSite subSite, int pageNumber)
    {
        throw new NotImplementedException();
    }
}
