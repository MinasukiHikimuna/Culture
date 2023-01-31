using CultureExtractor.Exceptions;
using CultureExtractor.Interfaces;
using CultureExtractor.CaptchaBuster;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites;

[PornNetwork("dorcelclub")]
[PornSite("dorcelclub")]
public class DorcelClubRipper : ISceneScraper, ISceneDownloader
{
    private static readonly Random Random = new();

    private readonly IDownloader _downloader;
    private readonly ICaptchaSolver _captchaSolver;

    public DorcelClubRipper(IDownloader downloader, ICaptchaSolver captchaSolver)
    {
        _downloader = downloader;
        _captchaSolver = captchaSolver;
    }

    public async Task LoginAsync(Site site, IPage page)
    {
        var loginButton = page.Locator("a.login");
        if (await loginButton.IsVisibleAsync())
        {
            await loginButton.ClickAsync();

            await _captchaSolver.SolveCaptchaIfNeededAsync(page);

            await Task.Delay(5000);

            if (await page.GetByPlaceholder("Email address").IsVisibleAsync())
            {
                await page.GetByPlaceholder("Email address").ClickAsync();
                await page.GetByPlaceholder("Email address").FillAsync(site.Username);
                await page.GetByPlaceholder("Password").ClickAsync();
                await page.GetByPlaceholder("Password").FillAsync(site.Password);

                if (await page.Locator("div.captcha").IsVisibleAsync())
                {
                    Log.Error("CAPTCHA required!");
                }

                await page.GetByRole(AriaRole.Button, new() { NameString = "Confirm" }).ClickAsync();

                await page.GetByRole(AriaRole.Banner).GetByRole(AriaRole.Link, new() { NameString = "Videos" }).Filter(new() { HasTextString = "Videos" }).ClickAsync();
            }
        }

        if (!(await page.Locator("div.languages > .selected-item").TextContentAsync()).Contains("English"))
        {
            await page.Keyboard.DownAsync("End");
            await page.GetByRole(AriaRole.Img, new() { NameString = "close" }).ClickAsync();
            await page.GetByText("English").ClickAsync();
        }
    }

    public async Task<int> NavigateToScenesAndReturnPageCountAsync(Site site, IPage page)
    {
        await page.GetByRole(AriaRole.Banner).GetByRole(AriaRole.Link, new() { NameString = "Videos" }).Filter(new() { HasTextString = "Videos" }).ClickAsync();
        return int.MaxValue;
    }

    public async Task DownloadPreviewImageAsync(Scene scene, IPage scenePage, IPage scenesPage, IElementHandle currentScene)
    {
        return;
    }

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(Site site, IPage page)
    {
        var currentScenes = await page.Locator("div.items > div.scene").ElementHandlesAsync();
        return currentScenes;
    }

    public async Task<(string Url, string ShortName)> GetSceneIdAsync(Site site, IElementHandle currentScene)
    {
        var thumbLinkElement = await currentScene.QuerySelectorAsync("a.thumb");
        var url = await thumbLinkElement.GetAttributeAsync("href");
        var pattern = @"\/[a-z]+\/[a-z]+\/(\d+)\/";
        Match match = Regex.Match(url, pattern);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Could not parse numerical ID from {url} using pattern {pattern}.");
        }

        string shortName = match.Groups[1].Value;
        return (url, shortName);
    }

    public async Task GoToNextFilmsPageAsync(IPage page)
    {
        await page.EvaluateAsync("document.querySelectorAll(\"div.items > div.scene\").forEach(e => e.remove());");
        await page.GetByRole(AriaRole.Button).Filter(new() { HasTextString = "See more" }).ClickAsync();
    }

    public async Task<Scene> ScrapeSceneAsync(Site site, string url, string sceneShortName, IPage page)
    {
        var releaseDateRaw = await page.Locator("div.right > span.publish_date").TextContentAsync();
        var releaseDate = DateOnly.Parse(releaseDateRaw);

        var durationRaw = await page.Locator("div.right > span.duration").TextContentAsync();
        var duration = HumanParser.ParseDuration(durationRaw);

        var titleRaw = await page.Locator("h1.title").TextContentAsync();
        var title = titleRaw.Replace("\n", "").Trim();

        var performersRaw = await page.Locator("div.player > div.actress > a").ElementHandlesAsync();

        var performers = new List<SitePerformer>();
        foreach (var performerElement in performersRaw)
        {
            var performerUrl = await performerElement.GetAttributeAsync("href");
            var shortName = performerUrl.Replace("/en/pornstar/", "");
            var name = await performerElement.TextContentAsync();
            performers.Add(new SitePerformer(shortName, name, performerUrl));
        }

        var fullTextLocator = page.Locator("div.content-description > div.content-text > span.full");
        var briefDescriptionLocator = page.Locator("div.content-description > div.content-text");

        string description = string.Empty;
        if (await fullTextLocator.IsVisibleAsync())
        {
            description = await fullTextLocator.TextContentAsync();
        }
        else if (await briefDescriptionLocator.IsVisibleAsync())
        {
            description = await briefDescriptionLocator.TextContentAsync();
        }
        description = description.Replace("\n", "").Trim();

        var downloadOptionsAndHandles = await ParseAvailableDownloadsAsync(page);

        return new Scene(
            null,
            site,
            releaseDate,
            sceneShortName,
            title,
            url,
            description,
            duration.TotalSeconds,
            performers,
            new List<SiteTag>(),
            downloadOptionsAndHandles.Select(f => f.DownloadOption).ToList()
        );
    }

    public async Task<Download> DownloadSceneAsync(Scene scene, IPage page, DownloadConditions downloadConditions)
    {
        var availableDownloads = await ParseAvailableDownloadsAsync(page);
        
        // Prefer ov (original voice) or en language tracks.
        var filteredDownloads = availableDownloads
            .Where(f => f.DownloadOption.Url.Contains("lang=ov") || f.DownloadOption.Url.Contains("lang=en"));
        if (!filteredDownloads.Any())
        {
            filteredDownloads = availableDownloads;
        }

        DownloadDetailsAndElementHandle selectedDownload = downloadConditions.PreferredDownloadQuality switch
        {
            PreferredDownloadQuality.Phash => filteredDownloads.FirstOrDefault(f => f.DownloadOption.ResolutionHeight == 480) ?? availableDownloads.Last(),
            PreferredDownloadQuality.Best => filteredDownloads.First(),
            PreferredDownloadQuality.Worst => filteredDownloads.Last(),
            _ => throw new InvalidOperationException("Could not find a download candidate!")
        };

        IPage newPage = await page.Context.NewPageAsync();

        var download = await _downloader.DownloadSceneAsync(scene, newPage, selectedDownload.DownloadOption, downloadConditions.PreferredDownloadQuality, async () =>
        {
            try
            {
                await newPage.GotoAsync(selectedDownload.DownloadOption.Url);
                await _captchaSolver.SolveCaptchaIfNeededAsync(newPage);
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
        });

        await newPage.CloseAsync();
        return download;
    }

    private static async Task<IList<DownloadDetailsAndElementHandle>> ParseAvailableDownloadsAsync(IPage page)
    {
        var downloadLinks = await page.Locator("div.qualities.selectors div.filter").ElementHandlesAsync();
        var availableDownloads = new List<DownloadDetailsAndElementHandle>();
        foreach (var downloadLink in downloadLinks)
        {
            var language = await downloadLink.GetAttributeAsync("data-lang");

            var descriptionRaw = await downloadLink.InnerTextAsync();
            var description = descriptionRaw.Replace("\n", "").Trim() + $" (Language: {language})";

            var resolutionHeightRaw = await downloadLink.GetAttributeAsync("data-quality");
            var resolutionHeight = int.Parse(resolutionHeightRaw);

            var url = await downloadLink.GetAttributeAsync("data-slug");
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
        return availableDownloads;
    }
}
