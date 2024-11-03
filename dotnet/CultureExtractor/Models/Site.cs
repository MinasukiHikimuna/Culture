namespace CultureExtractor.Models;

public record Site(
    Guid Uuid,
    string ShortName,
    string Name,
    string Url,
    string Username,
    string Password,
    string StorageState);