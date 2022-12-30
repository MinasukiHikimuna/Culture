using Microsoft.Playwright;

record Site(string Id, string Name, Uri Uri);

record Performer(string Id, string Name, Uri Uri);

record Tag(string Id, string Name);

record Scene(
    Site Site,
    DateOnly ReleaseDate,
    string Title,
    Uri Uri,
    IEnumerable<Performer> Performers,
    IEnumerable<Tag> Tags);

class PlaywrightExample
{
    public static async Task Main()
    {
        using var playwright = await Playwright.CreateAsync();
        await using var browser = await playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
        {
            Headless = false,
        });

        var context = await browser.NewContextAsync(new BrowserNewContextOptions() { ViewportSize = new ViewportSize { Width = 1920, Height = 1080 } });

        var page = await context.NewPageAsync();

        var baseUrl = "https://www.sexart.com";

        await page.GotoAsync(baseUrl);

        await page.Locator("#onetrust-accept-btn-handler").ClickAsync();

        await page.ClickAsync(".sign-in");
        await page.Locator("[name='email']").FillAsync("thardas@protonmail.com");
        await page.Locator("[name='password']").FillAsync("vXxKHg2CV8*7-gXN");

        Thread.Sleep(1000);

        await page.Locator("button[type='submit']").ClickAsync();

        await page.Locator(".close-btn").ClickAsync();

        await page.Locator("nav a[href='/movies']").ClickAsync();

        Thread.Sleep(5000);

        var currentScenes = await page.Locator("div.card-media a").ElementHandlesAsync();

        context.Page += async (_, page) => {
            await page.WaitForLoadStateAsync();
            Console.WriteLine(await page.TitleAsync());
        };

        page.Popup += async (_, popup) => {
            await popup.WaitForLoadStateAsync();
            Console.WriteLine(await page.TitleAsync());
        };

        foreach (var currentScene in currentScenes.Skip(1))
        {
            var newPage = await page.Context.RunAndWaitForPageAsync(async () =>
            {
                await currentScene.ClickAsync(new ElementHandleClickOptions() { Button = MouseButton.Middle });
            });

            var url = newPage.Url;

            // await page.PauseAsync();

            await newPage.Locator("a").Filter(new() { HasTextString = "Read More" }).ClickAsync();
            await newPage.BringToFrontAsync();

            var description = await newPage.Locator("div.movie-details div.info-container div p").TextContentAsync();

            try
            {
                var title = await newPage.Locator("div.movie-details h3.headline").TextContentAsync();
                title = title.Substring(0, title.LastIndexOf("(") - 1);

                var castElements = await newPage.Locator("div.movie-details > div > div > div > ul > li:nth-child(1) > span:nth-child(2) > a").ElementHandlesAsync();
                var performers = new List<Performer>();
                foreach (var castElement in castElements)
                {
                    var castUrl = await castElement.GetAttributeAsync("href");
                    var castId = castUrl.Substring(castUrl.LastIndexOf("/") + 1);
                    var castName = await castElement.TextContentAsync();
                    performers.Add(new Performer(castId, castName, new Uri(baseUrl + castUrl)));
                }

                var duration = await newPage.Locator("div.movie-details > div > div > div > ul > li:nth-child(4) > span:nth-child(2)").TextContentAsync();

                var wholeDetails = await newPage.Locator("div.movie-details > div > div > div > ul").TextContentAsync();

                var releaseDateRaw = await newPage.Locator("div.movie-details > div > div > div > ul > li:nth-child(3) > span:nth-child(2)").TextContentAsync();
                var releaseDate = DateOnly.Parse(releaseDateRaw);

                var tagElements = await newPage.Locator("div.tags-wrapper > div > a").ElementHandlesAsync();
                foreach (var tagElement in tagElements)
                {
                    var tagName = await tagElement.TextContentAsync();
                }

                var performerNames = performers.Select(p => p.Name).ToList();
                var performersStr = performerNames.Count() > 1 ? string.Join(", ", performerNames.Take(performerNames.Count() - 1)) + " & " + performerNames.Last() : performerNames.FirstOrDefault();

                var name = $"{performersStr} - SexArt - {releaseDate.Year}-{releaseDate.Month}-{releaseDate.Day} - {title}.mp4";

                await newPage.Locator("div svg.fa-film").ClickAsync();
                var downloadUrl = await newPage.Locator("div.dropdown-menu a").Filter(new() { HasTextString = "360p SD" }).GetAttributeAsync("href");

                var waitForDownloadTask = newPage.WaitForDownloadAsync();
                await newPage.Locator("div.dropdown-menu a").Filter(new() { HasTextString = "360p SD" }).ClickAsync();
                var download = await waitForDownloadTask;
                var suggestFilename = download.SuggestedFilename;
                await download.SaveAsAsync($@"G:\{name}");

                await newPage.CloseAsync();

                Thread.Sleep(60000);
            }
            catch (Exception ex)
            {

            }
        }
    }

    private static void Context_Page(object? sender, IPage e)
    {
        throw new NotImplementedException();
    }
}
