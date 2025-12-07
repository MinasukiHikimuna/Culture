namespace CultureExtractor.Models;

public class PathsOptions
{
    public const string Paths = "Paths";

    public string DatabasePath { get; set; } = String.Empty;
    public string MetadataPath { get; set; } = String.Empty;
    public string DownloadPath { get; set; } = String.Empty;
}