using CommandLine;

namespace CultureExtractor;

class Program
{
    static void Main(string[] args)
    {
        if (System.Diagnostics.Debugger.IsAttached)
        {
            var siteShortName = "kink";

            /*args = new string[] {
                "scrape",
                "--site-short-name", siteShortName,
                "--visible-browser",
                "--full"
            };*/
            args = new string[] {
                /*"scrape",
                "--site-short-name", siteShortName,
                "--sub-site-short-name", "sex-and-submission",
                // "--full",
                // "--guest-mode",
                // "--reverse-order",
                "--browser-mode", "Headless",
                // "--max-scenes", "1000",
                // "--from", "2020-01-01",
                // "--to", "2020-12-31",
                "--verbose",*/
                /*"download",
                "--site-short-name", siteShortName,
                "--sub-site-short-name", "bound-gang-bangs",
                // "--scenes", "464", "462", "530",
                // "--reverse-order",
                "--visible-browser",
                // "--max-scenes", "1000"
                // "--best",
                "--downloaded-file-names", "Kink - Bound Gang Bangs - 2011-05-03 - #13389 - Public Gangbang 2 - Princess Donna Dolore & Devaun.mp4",
                // "--from", "2020-01-01",
                // "--to", "2020-12-31",
                "--verbose",
                "--best",*/
            };
        }

        var options = (BaseOptions) Parser.Default.ParseArguments<ScrapeOptions, DownloadOptions>(args).Value;

        var host = AppHostFactory.CreateHost(args, options.SiteShortName);
        var cultureExtractor = AppHostFactory.CreateCultureExtractorConsoleApp(host);
        cultureExtractor.ExecuteConsoleApp(args);
    }
}

public class BaseOptions
{
    [Option("site-short-name", Required = true, HelpText = "Site short name")]
    public string SiteShortName { get; set; }

    [Option("sub-site-short-name", Required = false, HelpText = "Sub site short name")]
    public string SubSite { get; set; }

    [Option("browser-mode",
      Default = BrowserMode.Headless,
      HelpText = "Browser mode (Headless, ClassicHeadless, Visible)")]
    public BrowserMode BrowserMode { get; set; }

    [Option(
      Default = false,
      HelpText = "Prints all messages to standard output.")]
    public bool Verbose { get; set; }

    [Option("browser-channel", Required = false, HelpText = "Browser channel")]
    public string? BrowserChannel { get; set; }

    [Option("max-scenes", Default = int.MaxValue, HelpText = "How many scenes to process")]
    public int MaxScenes { get; set; }

    [Option("reverse-order", Required = false, HelpText = "Scrape/download scenes in reverse order (i.e. from latest to oldest)")]
    public bool ReverseOrder { get; set; }
}

[Verb("scrape", HelpText = "Scrape")]
public class ScrapeOptions : BaseOptions
{
    [Option(
      "full",
      Default = false,
      HelpText = "Full scrape including update existing scenes")]
    public bool FullScrape { get; set; }

    [Option(
      "guest-mode",
      Default = false,
      HelpText = "Uses guest mode for scraping (i.e. doesn't require subscription)")]
    public bool GuestMode { get; set; }

    [Option(
      "full-scrape-last-updated",
      Default = null,
      HelpText = "Full scrape including update existing scenes")]
    public DateTime? FullScrapeLastUpdated { get; set; }

    [Option("reverse-order", Required = false, HelpText = "Scrape scenes in reverse order (i.e. from latest to oldest)")]
    public bool ReverseOrder { get; set; }
}

[Verb("download", HelpText = "Download")]
public class DownloadOptions : BaseOptions
{
    [Option("from", Required = false, HelpText = "From date")]
    public string FromDate { get; set; }

    [Option("to", Required = false, HelpText = "To date")]
    public string ToDate { get; set; }

    [Option("best", Required = false, HelpText = "Use best quality")]
    public bool BestQuality { get; set; }

    [Option("scenes", Required = false, HelpText = "One or more scene IDs to download")]
    public IEnumerable<string> SceneIds { get; set; }

    [Option("performers", Required = false, HelpText = "One or more performers to download")]
    public IEnumerable<string> Performers { get; set; }

    [Option("downloaded-file-names", Required = false, HelpText = "Downloaded file names which should be re-downloaded with best quality")]
    public IEnumerable<string> DownloadedFileNames { get; set; }
}
