using CommandLine;
using Serilog;

namespace CultureExtractor;

public class CultureExtractorConsoleApp
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

            if (opts.FullScrape && opts.FullScrapeLastUpdated == null)
            {
                // temporary, restore before commit
                // this needs a better option
                opts.FullScrapeLastUpdated = DateTime.Now.AddDays(0);
            }

            Log.Information("Culture Extractor");

            string shortName = opts.SiteShortName;
            var browserSettings = new BrowserSettings(opts.BrowserMode, opts.BrowserChannel);

            var site = await _repository.GetSiteAsync(shortName);
            await _networkRipper.ScrapeScenesAsync(site, browserSettings, opts);

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
            var browserSettings = new BrowserSettings(opts.BrowserMode, opts.BrowserChannel);

            var dateRange = new DateRange(
                string.IsNullOrEmpty(opts.FromDate) ? DateOnly.MinValue : DateOnly.Parse(opts.FromDate),
                string.IsNullOrEmpty(opts.ToDate) ? DateOnly.MaxValue : DateOnly.Parse(opts.ToDate));

            var downloadQuality = opts.BestQuality ? PreferredDownloadQuality.Best : PreferredDownloadQuality.Phash;

            var downloadConditions = DownloadConditions.All(downloadQuality) with
            {
                DateRange = dateRange,
                SceneIds = opts.SceneIds.ToList() ?? new List<string>(),
                PerformerNames = opts.Performers.ToList() ?? new List<string>(),
                DownloadedFileNames = opts.DownloadedFileNames.ToList() ?? new List<string>()
            };

            var site = await _repository.GetSiteAsync(shortName);
            await _networkRipper.DownloadScenesAsync(site, browserSettings, downloadConditions, opts);

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
