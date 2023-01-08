using Microsoft.Playwright;

namespace CultureExtractor.Sites.WowNetwork;

public class WowGalleryPage
{
    private readonly IPage _page;

    public WowGalleryPage(IPage page)
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

    public async Task<int> ScrapePicturesAsync()
    {
        var duration = await _page.Locator("ul.details > li.images").TextContentAsync();
        if (int.TryParse(duration, out int pictures))
        {
            return pictures;
        }

        return 0;
    }
}
