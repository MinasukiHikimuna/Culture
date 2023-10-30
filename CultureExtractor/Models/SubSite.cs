namespace CultureExtractor.Models;

public record SubSite(
    int? Id,
    string ShortName,
    string Name,
    Site Site);