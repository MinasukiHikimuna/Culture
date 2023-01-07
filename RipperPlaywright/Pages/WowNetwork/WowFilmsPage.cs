using Microsoft.Playwright;

namespace RipperPlaywright.Pages.WowNetwork
{
    public class WowFilmsPage
    {
        private readonly IPage _page;

        public WowFilmsPage(IPage page)
        {
            _page = page;
        }

        /// <summary>
        /// Expects to be on Home page
        /// </summary>
        public async Task OpenFilmsPageAsync(string shortName)
        {
            await _page.GetByRole(AriaRole.Link, new() { NameString = "Films" }).Nth(1).ClickAsync();
            await _page.WaitForLoadStateAsync();

            while ((await _page.Locator(".cf_s_site").ElementHandlesAsync()).Count() > 0)
            {
                var elementHandles = await _page.Locator(".cf_s_site").ElementHandlesAsync();
                var elementHandle = elementHandles[0];

                await elementHandle.ClickAsync();
                await elementHandle.IsHiddenAsync();
                await _page.WaitForLoadStateAsync();
                Thread.Sleep(5000);
            }

            var siteName = shortName switch
            {
                "allfinegirls" => "All Fine Girls",
                "wowgirls" => "Wow Girls",
                "wowporn" => "Wow Porn",
                _ => string.Empty
            };

            if (!string.IsNullOrWhiteSpace(siteName))
            {
                await _page.GetByRole(AriaRole.Complementary).GetByText(siteName).ClickAsync();
                await _page.WaitForSelectorAsync(".cf_s_site");
                await _page.WaitForLoadStateAsync();
            }
        }

        public async Task<int> GetFilmsPagesAsync()
        {
            var totalPagesStr = await _page.Locator("div.pages > span").Last.TextContentAsync();
            var totalPages = int.Parse(totalPagesStr);
            return totalPages;
        }

        public Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync()
        {
            return _page.Locator("section.cf_content > ul > li > div.content_item > a.title").ElementHandlesAsync();
        }

        public Task GoToNextFilmsPageAsync()
        {
            return _page.Locator("div.nav.next").ClickAsync();
        }
    }
}
