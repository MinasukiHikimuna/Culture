using CommandLine;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Serilog;

namespace CultureExtractor;

class Program
{
    static void Main(string[] args)
    {
        if (System.Diagnostics.Debugger.IsAttached)
        {
            var siteShortName = "wowgirls";

            /*args = new string[] {
                "scrape",
                "--site-short-name", siteShortName,
                "--visible-browser",
                "--full"
            };*/
            args = new string[] {
                "download",
                "--site-short-name", siteShortName,
                /*"--scenes",
                    "464", "462", "530", "557", "555", "554", "551", "549", "548", "541", "531",
                    "533", "532", "482", "484", "490", "495", "503", "506", "457", "474", "475",
                    "477", "458",*/
                "--best",
                "--verbose"
            };
        }

        var host = Host.CreateDefaultBuilder(args)
            .ConfigureServices(services => {
                services.AddDbContext<ISqliteContext, SqliteContext>(options => options.UseSqlite());

                services.AddScoped<IRepository, Repository>();

                services.AddTransient<INetworkRipper, NetworkRipper>();

                services.AddTransient<CultureExtractorConsoleApp>();
            })
            .Build();
        
        var cultureExtractor = host.Services.GetRequiredService<CultureExtractorConsoleApp>();
        cultureExtractor.ExecuteConsoleApp(args);
    }
}

class CultureExtractorConsoleApp
{
    private readonly INetworkRipper _networkRipper;
    private readonly IRepository _repository;

    public CultureExtractorConsoleApp(IRepository repository, INetworkRipper networkRipper)
    {
        _networkRipper = networkRipper;
        _repository = repository;
    }

    public void ExecuteConsoleApp(string[] args)
    {
        Parser.Default.ParseArguments<ScrapeOptions, DownloadOptions>(args)
          .MapResult(
            (ScrapeOptions opts) => RunScrapeAndReturnExitCode(opts).GetAwaiter().GetResult(),
            (DownloadOptions opts) => RunDownloadAndReturnExitCode(opts).GetAwaiter().GetResult(),
            errs => 1);
    }

    private async Task<int> RunScrapeAndReturnExitCode(ScrapeOptions opts)
    {
        try
        {
            InitializeLogger(opts);

            Log.Information("Culture Extractor");

            string shortName = opts.SiteShortName;
            var browserSettings = new BrowserSettings(!opts.VisibleBrowser);

            var site = await _repository.GetSiteAsync(shortName);
            await _networkRipper.ScrapeScenesAsync(site, browserSettings, opts.FullScrape);

            return 0;
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);
            return -1;
        }
    }

    private async Task<int> RunDownloadAndReturnExitCode(DownloadOptions opts)
    {
        try
        {
            InitializeLogger(opts);

            Log.Information("Culture Extractor");

            string shortName = opts.SiteShortName;
            var browserSettings = new BrowserSettings(!opts.VisibleBrowser);

            var dateRange = new DateRange(
                string.IsNullOrEmpty(opts.FromDate) ? DateOnly.MinValue : DateOnly.Parse(opts.FromDate),
                string.IsNullOrEmpty(opts.ToDate) ? DateOnly.MaxValue : DateOnly.Parse(opts.ToDate));

            var downloadQuality = opts.BestQuality ? PreferredDownloadQuality.Best : PreferredDownloadQuality.Phash;

            var downloadOptions = DownloadConditions.All(downloadQuality) with
            {
                DateRange = dateRange,
                SceneIds = opts.SceneIds.ToList() ?? new List<string>(),
                PerformerShortNames = opts.Performers.ToList() ?? new List<string>()
            };

            var site = await _repository.GetSiteAsync(shortName);
            await _networkRipper.DownloadScenesAsync(site, browserSettings, downloadOptions);

            return 0;
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);

            return -1;
        }
    }

    private static void InitializeLogger(BaseOptions opts)
    {
        var minimumLogLevel = opts.Verbose
            ? Serilog.Events.LogEventLevel.Verbose
            : Serilog.Events.LogEventLevel.Information;

        var log = new LoggerConfiguration()
                        .WriteTo.Console().MinimumLevel.Is(minimumLogLevel)
                        .CreateLogger();
        Log.Logger = log;
    }
}

class BaseOptions
{
    [Option("site-short-name", Required = true, HelpText = "Site short name")]
    public string SiteShortName { get; set; }

    [Option("visible-browser",
      Default = false,
      HelpText = "Visible browser")]
    public bool VisibleBrowser { get; set; }

    [Option(
      Default = false,
      HelpText = "Prints all messages to standard output.")]
    public bool Verbose { get; set; }
}

[Verb("scrape", HelpText = "Scrape")]
class ScrapeOptions : BaseOptions
{
    [Option(
      "full",
      Default = false,
      HelpText = "Full scrape including update existing scenes")]
    public bool FullScrape { get; set; }
}

[Verb("download", HelpText = "Download")]
class DownloadOptions : BaseOptions
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
}
