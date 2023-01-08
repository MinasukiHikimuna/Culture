using Microsoft.Playwright;
using Serilog;
using System.Net;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites.WowNetwork
{
    public class CzechVRVideosPage
    {
        private readonly IPage _page;

        public CzechVRVideosPage(IPage page)
        {
            _page = page;
        }

        /// <summary>
        /// Expects to be on Home page
        /// </summary>
        public async Task OpenVideosPageAsync(string shortName)
        {
            await _page.GetByRole(AriaRole.Link, new() { NameString = "VIDEOS" }).ClickAsync();
            await _page.WaitForLoadStateAsync();

            var siteName = shortName switch
            {
                "czechvr" => "Czech VR",
                "czechvrfetish" => "CVR Fetish",
                "czechvrcasting" => "CVR Casting",
                "czechvrintimacy" => "VR Intimacy",
                _ => string.Empty
            };

            await _page.Locator("#Filtrace").GetByRole(AriaRole.Link, new() { NameString = siteName }).ClickAsync();
            await _page.WaitForLoadStateAsync();
            Thread.Sleep(5000);
        }

        public async Task<int> GetVideosPagesAsync()
        {
            var lastPageButton = await _page.QuerySelectorAsync("div.strankovani > span:last-child > a.last");
            var lastPageUrl = await lastPageButton.GetAttributeAsync("href");

            string linkPattern = @"next=(\d+)";
            Match linkMatch = Regex.Match(lastPageUrl, linkPattern);
            if (!linkMatch.Success)
            {
                Log.Error($"Could not parse last page URL video count from URL {lastPageUrl} using pattern {linkPattern}.");
                return 0;
            }

            var totalVideoCount = int.Parse(linkMatch.Groups[1].Value);

            var videosOnCurrentPage = await _page.Locator("div.foto").ElementHandlesAsync();

            return (int) Math.Ceiling(((double)totalVideoCount) / videosOnCurrentPage.Count());
        }

        public Task<IReadOnlyList<IElementHandle>> GetCurrentScenesAsync()
        {
            return _page.Locator("div.foto > div > a").ElementHandlesAsync();
        }

        public async Task GoToNextFilmsPageAsync()
        {
            await _page.Locator("div.strankovani > span > a.next").ClickAsync();
        }

        public async Task DownloadPreviewImageAsync(IElementHandle sceneHandle, Scene scene)
        {
            var downloader = new Downloader();

            if (!downloader.SceneImageExists(scene))
            {
                var previewElement = await sceneHandle.QuerySelectorAsync("img");
                var originalUrl = await previewElement.GetAttributeAsync("src");
                await downloader.DownloadSceneImageAsync(scene, originalUrl);
            }
        }
    }
}
