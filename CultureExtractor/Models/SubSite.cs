namespace CultureExtractor.Models;

public record SubSite(
    Guid Uuid,
    string ShortName,
    string Name,
    Site Site);