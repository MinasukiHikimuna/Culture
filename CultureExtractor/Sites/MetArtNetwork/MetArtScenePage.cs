using Microsoft.Playwright;

namespace CultureExtractor.Sites.MetArtNetwork
{
    public class MetArtScenePage
    {
        private readonly IPage _page;

        public MetArtScenePage(IPage page)
        {
            _page = page;
        }

        public async Task<DateOnly> ScrapeReleaseDateAsync()
        {
            var releaseDateRaw = await _page.Locator("div.movie-details > div > div > div > ul > li:nth-child(3) > span:nth-child(2)").TextContentAsync();
            return DateOnly.Parse(releaseDateRaw);
        }

        public async Task<string> ScrapeTitleAsync()
        {
            var title = await _page.Locator("div.movie-details h3.headline").TextContentAsync();
            title = title.Substring(0, title.LastIndexOf("(") - 1);
            return title;
        }

        public async Task<IList<SitePerformer>> ScrapePerformersAsync(string baseUrl)
        {
            var castElements = await _page.Locator("div.movie-details > div > div > div > ul > li:nth-child(1) > span:nth-child(2) > a").ElementHandlesAsync();
            var performers = new List<SitePerformer>();
            foreach (var castElement in castElements)
            {
                var castUrl = await castElement.GetAttributeAsync("href");
                var castId = castUrl.Substring(castUrl.LastIndexOf("/") + 1);
                var castName = await castElement.TextContentAsync();
                performers.Add(new SitePerformer(castId, castName, castUrl));
            }
            return performers.AsReadOnly();
        }

        public async Task<TimeSpan> ScrapeDurationAsync()
        {
            var duration = await _page.Locator("div.movie-details > div > div > div > ul > li:nth-child(4) > span:nth-child(2)").TextContentAsync();
            if (TimeSpan.TryParse(duration, out TimeSpan timespan))
            {
                return timespan;
            }

            return TimeSpan.FromSeconds(0);
        }

        public async Task<string> ScrapeDescriptionAsync()
        {
            if (!await _page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).IsVisibleAsync())
            {
                return string.Empty;
            }

            await _page.Locator("div.movie-details a").Filter(new() { HasTextString = "Read More" }).ClickAsync();
            var elementHandles = await _page.Locator("div.movie-details div.info-container div p").ElementHandlesAsync();
            var descriptionParagraphs = new List<string>();
            foreach (var elementHandle in elementHandles)
            {
                var descriptionParagraph = await elementHandle.TextContentAsync();
                if (!string.IsNullOrWhiteSpace(descriptionParagraph))
                {
                    descriptionParagraphs.Add(descriptionParagraph);
                }
            }
            return string.Join("\r\n\r\n", descriptionParagraphs);
        }
    }
}
