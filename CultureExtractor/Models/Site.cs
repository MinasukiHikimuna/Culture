namespace CultureExtractor.Models;

public record Site(
    int Id,
    string ShortName,
    string Name,
    string Url,
    string Username,
    string Password,
    string StorageState);