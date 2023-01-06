using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using RipperPlaywright;
using RipperPlaywright.Pages;
using System;
using System.Net;
using System.Security.Cryptography.X509Certificates;
using System.Text.RegularExpressions;

[PornNetwork("wow")]
[PornSite("ultrafilms")]
[PornSite("wowgirls")]
public class WowNetworkRipper : ISiteRipper
{
    private readonly SqliteContext _sqliteContext;
    private readonly Repository _repository;

    public WowNetworkRipper()
    {
        _sqliteContext = new SqliteContext();
        _repository = new Repository(_sqliteContext);
    }

    public async Task ScrapeScenesAsync(string shortName)
    {
        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, true);

        var rippingPath = $@"I:\Ripping\{site.Name}\";

        var loginPage = new WowLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);

        await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());

        await page.GetByRole(AriaRole.Link, new() { NameString = "Films" }).Nth(1).ClickAsync();
        await page.WaitForLoadStateAsync();
        await page.GetByRole(AriaRole.Complementary).GetByText("Wow Girls").ClickAsync();
        await page.WaitForLoadStateAsync();

        var totalPagesStr = await page.Locator("div.pages > span").Last.TextContentAsync();
        var totalPages = int.Parse(totalPagesStr);

        for (int currentPage = 1; currentPage <= totalPages; currentPage++)
        {
            Thread.Sleep(10000);
            var currentScenes = await page.Locator("section.cf_content > ul > li > div.content_item > a.title").ElementHandlesAsync();
            Console.WriteLine($"Page {currentPage}/{totalPages} contains {currentScenes.Count} scenes");

            foreach (var currentScene in currentScenes)
            {
                for (int retries = 0; retries < 3; retries++)
                {
                    try
                    {
                        var relativeUrl = await currentScene.GetAttributeAsync("href");
                        var url = site.Url + relativeUrl;

                        string pattern = @"/film/(?<id>\w+)/.*";
                        Match match = Regex.Match(relativeUrl, pattern);
                        if (!match.Success)
                        {
                            Console.WriteLine($@"Could not determine ID from ""{relativeUrl}"" using pattern {pattern}. Skipping...");
                            continue;
                        }

                        var sceneShortName = match.Groups["id"].Value;
                        var existingSceneEntity = await _sqliteContext.Scenes.FirstOrDefaultAsync(s => s.ShortName == sceneShortName);
                        if (existingSceneEntity != null)
                        {
                            continue;
                        }

                        if (retries > 0)
                        {
                            Console.WriteLine($"Retrying {retries + 1} attempt for {relativeUrl}");
                        }

                        var newPage = await page.Context.RunAndWaitForPageAsync(async () =>
                        {
                            await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                        });

                        await newPage.WaitForLoadStateAsync();

                        var wowScenePage = new WowScenePage(newPage);
                        var releaseDate = await wowScenePage.ScrapeReleaseDateAsync();
                        var duration = await wowScenePage.ScrapeDurationAsync();
                        var description = await wowScenePage.ScrapeDescriptionAsync();
                        var title = await wowScenePage.ScrapeTitleAsync();
                        var performers = await wowScenePage.ScrapePerformersAsync();
                        var tags = await wowScenePage.ScrapeTagsAsync();

                        var scene = new Scene(
                            site,
                            releaseDate,
                            sceneShortName,
                            title,
                            url,
                            description,
                            duration.TotalSeconds,
                            performers,
                            tags
                        );
                        var sceneId = await _repository.SaveSceneAsync(scene);

                        var previewElement = await newPage.Locator(".jw-preview").GetAttributeAsync("style");
                        var imageUrl = previewElement.Split(@"""")[1];
                        using (WebClient client = new WebClient())
                        {
                            await client.DownloadFileTaskAsync(new Uri(imageUrl), $@"I:\Ripping\{site.Name}\Images\{sceneId}.jpg");
                        }

                        await newPage.CloseAsync();

                        Console.WriteLine($"{DateTime.Now} Scraped: {url}");

                        Thread.Sleep(3000);

                        break;
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine(ex.ToString());
                    }
                }
            }

            if (currentPage != totalPages)
            {
                await page.Locator("div.nav.next").ClickAsync();
            }
        }
    }

    public async Task DownloadAsync(string shortName, DownloadConditions conditions)
    {
        var matchingScenes = await _sqliteContext.Scenes
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Include(s => s.Site)
            .Where(s => conditions.DateRange.Start <= s.ReleaseDate && s.ReleaseDate <= conditions.DateRange.End)
        .ToListAsync();

        var site = await _repository.GetSiteAsync(shortName);
        IPage page = await PlaywrightFactory.CreatePageAsync(site, true);

        var loginPage = new WowLoginPage(page);
        await loginPage.LoginIfNeededAsync(site);

        var rippingPath = $@"I:\Ripping\{site.Name}\";
        foreach (var scene in matchingScenes)
        {
            await page.GotoAsync(scene.Url);
            await page.WaitForLoadStateAsync();

            var performerNames = scene.Performers.Select(p => p.Name).ToList();
            var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

            // All scenes do not have 60 fps alternatives. In that case 30 fps button is not shown.
            /* var fps30Locator = newPage.Locator("span").Filter(new() { HasTextString = "30 fps" });
            if (await fps30Locator.IsVisibleAsync())
            {
                await newPage.Locator("span").Filter(new() { HasTextString = "30 fps" }).ClickAsync();
                await newPage.WaitForLoadStateAsync();
            }*/

            var downloadUrl = await page.GetByRole(AriaRole.Link, new() { NameString = "5568 x 3132" }).GetAttributeAsync("href");

            var waitForDownloadTask = page.WaitForDownloadAsync();
            await page.GetByRole(AriaRole.Link, new() { NameString = "5568 x 3132" }).ClickAsync();
            var download = await waitForDownloadTask;
            var suggestedFilename = download.SuggestedFilename;

            var suffix = Path.GetExtension(suggestedFilename);
            var name = $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}{suffix}";
            name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));

            var path = Path.Join(rippingPath, name);
            await download.SaveAsAsync(path);
        }
    }
}
