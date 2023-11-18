using CultureExtractor.Models;

namespace CultureExtractor.Tests;



public record Filter(string FileType, string ContentType, string Variant)
{
    
}

public class DownloadPlanner
{
    public async Task<IReadOnlyList<ReleaseDownloadPlan>> PlanDownloadsAsync(IReadOnlyList<Release> releases, DownloadConditions downloadConditions)
    {
        return new List<ReleaseDownloadPlan>().AsReadOnly();
    }
}

public record ReleaseDownloadPlan(Release Release, IReadOnlyList<IAvailableFile> AvailableFiles);

[TestFixture]
public class DownloadPlannerTests
{
    private Site site = new Site(UuidGenerator.Generate(), "assntits", "Ass & Tits", "https://assntits.com", "ass", "tits", "{}");

    [Test]
    public async Task Foobar()
    {
        var release = new Release(UuidGenerator.Generate(), site, null, DateOnly.Parse("2023-11-18"), "firstanal", "First Anal", "https://assntits.com/releases/firstanal", "Hot MILF has her first anal experience.", 0.0,
            new SitePerformer[] { new SitePerformer("toriblack", "Tori Black", "https://assntits.com/models/tori-black") },
            new SiteTag[] { new SiteTag("anal", "Anal", "https://assntits.com/tags/anal") },
            new IAvailableFile[]
            {
                new AvailableVideoFile("video", "scene", "1080p", "https://assntits.com/releases/firstanal/1080p", -1, 1080, 131831123, 24.0, "h264"),
                new AvailableVideoFile("video", "scene", "1080p", "https://assntits.com/releases/firstanal/720p", -1, 720, 47113122, 24.0, "h264")
            },
            "{}",
            new DateTime(2023, 11, 18, 12, 34, 56)
        );
            
    }
}