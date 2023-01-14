using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;
using static System.Net.Mime.MediaTypeNames;

namespace CultureExtractor.Sites.DorcelClub;

[PornNetwork("dorcelclub")]
[PornSite("dorcelclub")]
public class DorcelClubRipper : ISceneScraper
{
    public async Task LoginAsync(Site site, IPage page)
    {
        var logoutButton = page.Locator("div.actions > a.logout");
        if (!await logoutButton.IsEnabledAsync())
        {
            await page.FrameLocator("iframe").GetByRole(AriaRole.Link, new() { NameString = "Enter and accept cookies" }).ClickAsync();

            await page.GetByRole(AriaRole.Link, new() { NameString = "Login Login" }).ClickAsync();

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

    public async Task DownloadPreviewImageAsync(Scene scene, IPage page, IElementHandle currentScene)
    {
        return;
    }

    public async Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync(IPage page)
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
        TimeSpan duration;
        if (durationRaw.EndsWith("m"))
        {
            duration = TimeSpan.FromMinutes(int.Parse(durationRaw.Replace("m", "")));
        }
        else
        {
            var durationComponents = durationRaw.Split("m");
            duration = TimeSpan.FromMinutes(int.Parse(durationComponents[0])).Add(TimeSpan.FromSeconds(int.Parse(durationComponents[1])));
        }

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
        string descriptionRaw = await fullTextLocator.IsVisibleAsync()
            ? await fullTextLocator.TextContentAsync()
            : await page.Locator("div.content-description > div.content-text").TextContentAsync();
        string description = descriptionRaw.Replace("\n", "").Trim();

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
            new List<SiteTag>()
        );
    }
}
