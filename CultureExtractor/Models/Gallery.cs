namespace CultureExtractor.Models;

public record Gallery(
    int? Id,
    Site Site,
    DateOnly ReleaseDate,
    string ShortName,
    string Name,
    string Url,
    string Description,
    int Pictures,
    IEnumerable<SitePerformer> Performers,
    IEnumerable<SiteTag> Tags);