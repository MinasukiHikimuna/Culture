using Microsoft.Playwright;
using Serilog;
using System.Text.RegularExpressions;

namespace CultureExtractor.Sites.WowNetwork
{
    public class CzechVRScenePage
    {
        private readonly IPage _page;

        public CzechVRScenePage(IPage page)
        {
            _page = page;
        }

        public async Task<DateOnly> ScrapeReleaseDateAsync()
        {
            var releaseDateRaw = await _page.Locator("div.nazev > div.desktop > div.datum").TextContentAsync();
            return DateOnly.Parse(releaseDateRaw);
        }

        public async Task<string> ScrapeTitleAsync()
        {
            var title = await _page.Locator("div.post > div.left > div.nazev > h2").TextContentAsync();
            string pattern = @"\w+ \d+ - (.*)";
            Match match = Regex.Match(title, pattern);
            if (!match.Success)
            {
                Log.Warning($@"Could not determine title from ""{title}"" using pattern {pattern}. Skipping...");
                throw new Exception();
            }

            return match.Groups[1].Value;
        }

        public async Task<IList<SitePerformer>> ScrapePerformersAsync()
        {
            var castElements = await _page.Locator("div.post > div.left > div.nazev > div.desktop > div.featuring > a").ElementHandlesAsync();
            var performers = new List<SitePerformer>();
            foreach (var castElement in castElements)
            {
                var castUrl = await castElement.GetAttributeAsync("href");
                if (castUrl.StartsWith("./"))
                {
                    castUrl = castUrl.Substring(2);
                }

                var castId = castUrl.Replace("model-", "");
                var castName = await castElement.TextContentAsync();
                performers.Add(new SitePerformer(castId, castName, castUrl));
            }
            return performers.AsReadOnly();
        }

        public async Task<IList<SiteTag>> ScrapeTagsAsync()
        {
            var tagElements = await _page.Locator("div.post > div.left > div.tagy > div.tag > a").ElementHandlesAsync();
            var tags = new List<SiteTag>();
            foreach (var tagElement in tagElements)
            {
                var tagUrl = await tagElement.GetAttributeAsync("href");
                if (tagUrl.StartsWith("./"))
                {
                    tagUrl = tagUrl.Substring(2);
                }

                var tagId = tagUrl.Replace("tag-", "");
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
            var duration = await _page.Locator("div.nazev > div.desktop > div.cas > span.desktop").TextContentAsync();
            var components = duration.Split(":");
            return TimeSpan.FromMinutes(int.Parse(components[0])).Add(TimeSpan.FromSeconds(int.Parse(components[1])));
        }

        public async Task<string> ScrapeDescriptionAsync()
        {
            var content = await _page.Locator("div.post > div.left > div.text").TextContentAsync();
            return content.Replace("\n\t", "");
        }
    }
}
