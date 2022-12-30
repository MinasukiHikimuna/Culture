using Microsoft.EntityFrameworkCore;
using Microsoft.Playwright;
using RipperPlaywright;
using RipperPlaywright.Pages;

[PornNetwork("metart")]
[PornSite("metart")]
[PornSite("metartx")]
[PornSite("sexart")]
[PornSite("vivthomas")]
public class MetArtNetworkRipper : ISiteRipper
{
    private readonly SqliteContext _sqliteContext;
    private readonly Repository _repository;

    public MetArtNetworkRipper()
    {
        _sqliteContext = new SqliteContext();
        _repository = new Repository(_sqliteContext);
    }

    public Task DownloadAsync(string shortName, DownloadConditions conditions)
    {
        throw new NotImplementedException();
    }

    public async Task RipAsync(string shortName)
    {
        var site = await _repository.GetSiteAsync(shortName);

        IBrowserContext context = null;
        var rippingPath = $@"I:\Ripping\{site.Name}\";

        try
        {
            var playwright = await Playwright.CreateAsync();
            var browser = await playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
            {
                Headless = true,
            });

            context = await browser.NewContextAsync(new BrowserNewContextOptions()
            {
                BaseURL = site.Url,
                ViewportSize = new ViewportSize { Width = 1920, Height = 1080 },
                StorageState = site.StorageState
            });

            await context.Tracing.StartAsync(new()
            {
                Screenshots = true,
                Snapshots = true,
                Sources = true
            });

            var page = await context.NewPageAsync();

            await page.GotoAsync("/");
            await page.WaitForLoadStateAsync();
            Thread.Sleep(5000);

            if (!page.Url.EndsWith("/updates"))
            {
                if (await page.Locator("#onetrust-accept-btn-handler").IsVisibleAsync())
                {
                    await page.Locator("#onetrust-accept-btn-handler").ClickAsync();
                }

                await page.ClickAsync(".sign-in");
                await page.WaitForLoadStateAsync();

                await page.Locator("[name='email']").TypeAsync("thardas@protonmail.com");
                await page.Locator("[name='password']").TypeAsync("vXxKHg2CV8*7-gXN");
                await page.Locator("button[type='submit']").ClickAsync();
                await page.WaitForLoadStateAsync();
            }

            // Close the modal dialog if one is shown.
            try
            {
                await page.WaitForLoadStateAsync();
                await page.Locator(".close-btn").ClickAsync();
            }
            catch (Exception ex)
            {
            }

            await page.Locator("nav a[href='/movies']").ClickAsync();
            await page.WaitForLoadStateAsync();

            var totalPagesStr = await page.Locator("nav.pagination > a:nth-child(5)").TextContentAsync();
            var totalPages = int.Parse(totalPagesStr);

            for (int currentPage = 1; currentPage <= totalPages; currentPage++)
            {
                Thread.Sleep(10000);
                var currentScenes = await page.Locator("div.card-media a").ElementHandlesAsync();
                Console.WriteLine($"Page {currentPage}/{totalPages} contains {currentScenes.Count} scenes");

                foreach (var currentScene in currentScenes.Skip(currentPage == 1 ? 1 : 0))
                {
                    for (int retries = 0; retries < 3; retries++)
                    {
                        try
                        {
                            var foo = await currentScene.GetAttributeAsync("href");

                            var sceneShortName = foo.Substring(foo.LastIndexOf("/movie/") + "/movie/".Length + 1);
                            var existingSceneEntity = await _sqliteContext.Scenes.FirstOrDefaultAsync(s => s.ShortName == sceneShortName);
                            if (existingSceneEntity != null)
                            {
                                continue;
                            }

                            if (retries > 0)
                            {
                                Console.WriteLine($"Retrying {retries + 1} attempt for {foo}");
                            }

                            var newPage = await page.Context.RunAndWaitForPageAsync(async () =>
                            {
                                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
                            });

                            await newPage.WaitForLoadStateAsync();

                            var url = site.Url + foo;

                            var metArtScenePage = new MetArtScenePage(newPage);
                            var releaseDate = await metArtScenePage.ScrapeReleaseDateAsync();
                            var duration = await metArtScenePage.ScrapeDurationAsync();
                            var description = await metArtScenePage.ScrapeDescriptionAsync();
                            var name = await metArtScenePage.ScrapeTitleAsync();
                            var performers = await metArtScenePage.ScrapePerformersAsync(site.Url);

                            var wholeDetails = await newPage.Locator("div.movie-details > div > div > div > ul").TextContentAsync();


                            var tagElements = await newPage.Locator("div.tags-wrapper > div > a").ElementHandlesAsync();
                            foreach (var tagElement in tagElements)
                            {
                                var tagName = await tagElement.TextContentAsync();
                            }

                            var performerNames = performers.Select(p => p.Name).ToList();
                            var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

                            /* await newPage.Locator("div svg.fa-film").ClickAsync();

                            var downloadUrl = await newPage.Locator("div.dropdown-menu a").Filter(new() { HasTextString = "360p SD" }).GetAttributeAsync("href");

                            var waitForDownloadTask = newPage.WaitForDownloadAsync();
                            await newPage.Locator("div.dropdown-menu a").Filter(new() { HasTextString = "360p SD" }).ClickAsync();
                            var download = await waitForDownloadTask;
                            var suggestedFilename = download.SuggestedFilename;

                            var suffix = Path.GetExtension(suggestedFilename);
                            var name = $"{performersStr} - {siteEntity.Name} - {releaseDate.ToString("yyyy-MM-dd")} - {title}{suffix}";
                            name = string.Concat(name.Split(Path.GetInvalidFileNameChars()));

                            var path = Path.Join(rippingPath, name); ;
                            await download.SaveAsAsync(path);*/

                            await newPage.CloseAsync();

                            var scene = new Scene(
                                site,
                                releaseDate,
                                sceneShortName,
                                name,
                                url,
                                description,
                                duration.TotalSeconds,
                                performers,
                                new List<SiteTag>()
                            );
                            await _repository.SaveSceneAsync(scene);

                            // Console.WriteLine($"{DateTime.Now} Downloaded: {path}");

                            Thread.Sleep(15000);

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
                    await page.GetByRole(AriaRole.Link, new() { NameString = ">" }).ClickAsync();
                }
            }

            await page.ReloadAsync();
            await page.WaitForLoadStateAsync();
            Thread.Sleep(5000);

            var siteEntityFoo = await _sqliteContext.Sites.FirstOrDefaultAsync(s => s.ShortName == site.ShortName);
            if (siteEntityFoo != null)
            {
                await _repository.UpdateStorageStateAsync(site, await page.Context.StorageStateAsync());
            }
        }
        finally
        {
            if (context != null)
            {
                var path = Path.Combine(rippingPath, $"trace_{DateTime.Now.ToString("yyyyMMdd_HHmmss")}.zip");
                await context.Tracing.StopAsync(new() 
                {
                    Path = path
                });
            }
        }
    }
}
