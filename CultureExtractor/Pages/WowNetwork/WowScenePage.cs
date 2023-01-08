using Microsoft.Playwright;

namespace RipperPlaywright.Pages.WowNetwork
{
    public class WowScenePage
    {
        private readonly IPage _page;

        public WowScenePage(IPage page)
        {
            _page = page;
        }

        public async Task<DateOnly> ScrapeReleaseDateAsync()
        {
            var releaseDateRaw = await _page.Locator("ul.details > li.date").TextContentAsync();
            return DateOnly.Parse(releaseDateRaw);
        }

        public async Task<string> ScrapeTitleAsync()
        {
            var title = await _page.Locator("section.content_header > div.content_info > div.title").TextContentAsync();
            return title;
        }

        public async Task<IList<SitePerformer>> ScrapePerformersAsync()
        {
            var castElements = await _page.Locator("section.content_header > div.content_info > ul.details > li.models > a").ElementHandlesAsync();
            var performers = new List<SitePerformer>();
            foreach (var castElement in castElements)
            {
                var castUrl = await castElement.GetAttributeAsync("href");
                var castId = castUrl.Substring(castUrl.LastIndexOf("/girl/") + "/girl/".Length);
                var castName = await castElement.TextContentAsync();
                performers.Add(new SitePerformer(castId, castName, castUrl));
            }
            return performers.AsReadOnly();
        }

        public async Task<IList<SiteTag>> ScrapeTagsAsync()
        {
            var tagElements = await _page.Locator("section.content_header > div.content_info > ul.genres > li > a").ElementHandlesAsync();
            var tags = new List<SiteTag>();
            foreach (var tagElement in tagElements)
            {
                var tagUrl = await tagElement.GetAttributeAsync("href");
                var tagId = await tagElement.TextContentAsync();
                var tagName = await tagElement.TextContentAsync();
                tags.Add(new SiteTag(tagId, tagName, tagUrl));
            }
            return tags;
        }

        /*public async Task<IList<SceneVersion>> ScrapeVersionsAsync()
        {
            var versionElements = await _page.Locator(".ct_dl_items > ul > li").ElementHandlesAsync();

            var versions = new List<SceneVersion>();
            foreach (var versionElement in versionElements)
            {
                var spans = await versionElement.QuerySelectorAllAsync("span");
                var resolution = (await spans[0].TextContentAsync()).Replace(" ", "");
                var codec = await spans[2].TextContentAsync();
                var fps = await spans[3].TextContentAsync();
                var size = await spans[4].TextContentAsync();
                versions.Add(new SceneVersion(resolution, size, fps, codec));
            }
            return versions;
        }*/

        public async Task<TimeSpan> ScrapeDurationAsync()
        {
            var duration = await _page.Locator("ul.details > li.duration").TextContentAsync();
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
