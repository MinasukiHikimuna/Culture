using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites.DorcelClub;

[PornNetwork("dorcelclub")]
[PornSite("dorcelclub")]
public class DorcelClubRipper : ISceneScraper, ISceneDownloader
{
    public async Task LoginAsync(Site site, IPage page)
    {
        var loginButton = page.Locator("a.login");
        if (await loginButton.IsVisibleAsync())
        {
            await loginButton.ClickAsync();

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

    public async Task DownloadSceneAsync(SceneEntity scene, IPage page, string rippingPath)
    {
        await page.GotoAsync(scene.Url);
        await page.WaitForLoadStateAsync();

        var performerNames = scene.Performers.Select(p => p.Name).ToList();
        var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

        await page.GetByRole(AriaRole.Link).Filter(new() { HasTextString = "Download the video" }).ClickAsync();
        await page.Locator("#download-pop-in").GetByText("English").ClickAsync();
        await page.Locator("div[data-quality=\"360\"][data-lang=\"en\"]").ClickAsync();

        var waitForDownloadTask = page.WaitForDownloadAsync();

        await page.GetByRole(AriaRole.Button, new() { NameString = "Download" }).ClickAsync();

        var download = await waitForDownloadTask;
        var suggestedFilename = download.SuggestedFilename;

        var suffix = Path.GetExtension(suggestedFilename);
        var name = $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}{suffix}";
        name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));

        var path = Path.Join(rippingPath, name);


        Log.Verbose($"Downloading\r\n    Path: {path}");

        await download.SaveAsAsync(path);
    }
}
