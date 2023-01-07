using Microsoft.Playwright;
using System.Net;
using System.Text.RegularExpressions;

namespace RipperPlaywright.Pages.WowNetwork
{
    public class WowGalleriesPage
    {
        private readonly IPage _page;

        public WowGalleriesPage(IPage page)
        {
            _page = page;
        }

        /// <summary>
        /// Expects to be on Home page
        /// </summary>
        public async Task OpenGalleriesPageAsync(string shortName)
        {
            await _page.GetByRole(AriaRole.Link, new() { NameString = "Galleries" }).Nth(1).ClickAsync();
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

        public async Task<int> GetGalleriesPagesAsync()
        {
            var totalPagesStr = await _page.Locator("div.pages > span").Last.TextContentAsync();
            var totalPages = int.Parse(totalPagesStr);
            return totalPages;
        }

        public Task<IReadOnlyList<IElementHandle>> GetCurrentGalleriesAsync()
        {
            return _page.Locator("section.cf_content > ul > li > div.content_item > a.icon").ElementHandlesAsync();
        }

        public Task GoToNextPageAsync()
        {
            return _page.Locator("div.nav.next").ClickAsync();
        }

        public async Task DownloadPreviewImageAsync(IElementHandle sceneHandle, Gallery gallery)
        {
            var previewElement = await sceneHandle.QuerySelectorAsync("span > img");
            var imageUrl = await previewElement.GetAttributeAsync("src");
            string pattern2 = "icon_\\d+x\\d+.jpg";
            string replacement = "icon_3840x2160.jpg";
            string highQualityImageUrl = Regex.Replace(imageUrl, pattern2, replacement);
            try
            {
                await new Downloader().DownloadGalleryImage(gallery, highQualityImageUrl, (int)gallery.Id);
            }
            catch (WebException ex)
            {
                if (ex.Status == WebExceptionStatus.ProtocolError && (ex.Response as HttpWebResponse)?.StatusCode == HttpStatusCode.NotFound)
                {
                    await new Downloader().DownloadGalleryImage(gallery, imageUrl, (int)gallery.Id);
                }
            }
        }
    }
}
