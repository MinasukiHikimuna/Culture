using System.Text.Json;
using CommandLine;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Serilog;

namespace CultureExtractor;

public class CultureExtractorConsoleApp
{
    private readonly INetworkRipper _networkRipper;
    private readonly IRepository _repository;
    private readonly ISqliteContext _sqliteContext;

    public CultureExtractorConsoleApp(IRepository repository, INetworkRipper networkRipper, ISqliteContext sqliteContext)
    {
        _networkRipper = networkRipper;
        _repository = repository;
        _sqliteContext = sqliteContext;
    }

    public void ExecuteConsoleApp(string[] args)
    {
        Parser.Default.ParseArguments<ScrapeOptions, DownloadOptions, MigrateOptions>(args)
          .MapResult(
            (ScrapeOptions opts) => RunScrapeAndReturnExitCode(opts).GetAwaiter().GetResult(),
            (DownloadOptions opts) => RunDownloadAndReturnExitCode(opts).GetAwaiter().GetResult(),
            (MigrateOptions opts) => RunMigrateAndReturnExitCode(opts).GetAwaiter().GetResult(),
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
            await _networkRipper.ScrapeReleasesAsync(site, browserSettings, opts);

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
                ReleaseUuids = opts.ReleaseUuids.ToList() ?? new List<string>(),
                PerformerNames = opts.Performers.ToList() ?? new List<string>(),
                DownloadedFileNames = opts.DownloadedFileNames.ToList() ?? new List<string>()
            };

            var site = await _repository.GetSiteAsync(shortName);
            await _networkRipper.DownloadReleasesAsync(site, browserSettings, downloadConditions, opts);

            return 0;
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);

            return -1;
        }
    }
    
    private async Task<int> RunMigrateAndReturnExitCode(MigrateOptions opts)
    {
        try
        {
            InitializeLogger(opts);

            Log.Information("Culture Extractor");

            var releases = await _sqliteContext.Releases.ToListAsync();
            int batchSize = 100;
            int totalBatches = (releases.Count + batchSize - 1) / batchSize;

            int successes = 0;
            int errors = 0;
            for (int batch = 0; batch < totalBatches; batch++)
            {
                var currentBatch = releases.Skip(batch * batchSize).Take(batchSize);

                foreach (var release in currentBatch)
                {
                    try
                    {
                        if (release.DownloadOptions == "")
                        {
                            release.DownloadOptions = "[]";
                        }
                    
                        var downloadOptions =
                            JsonSerializer.Deserialize<IEnumerable<DownloadOption>>(release.DownloadOptions);

                        IEnumerable<IAvailableFile> availableFiles = downloadOptions.Select(f => new AvailableVideoFile(
                            "video",
                            "scene",
                            f.Description,
                            f.Url,
                            f.ResolutionWidth,
                            f.ResolutionHeight,
                            f.FileSize,
                            f.Fps,
                            f.Codec));
                        release.DownloadOptions = JsonSerializer.Serialize(availableFiles);
                        successes++;
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine(ex);
                        Console.WriteLine(release.Uuid + " " + release.Name);
                        errors++;
                    }
                }

                await _sqliteContext.SaveChangesAsync();
                Console.WriteLine("Batch " + batch + " of " + totalBatches + " complete.");
            }

            Console.WriteLine($"Successes: {successes}");
            Console.WriteLine($"Errors: {errors}");

            return 0;
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);

            return -1;
        }
    }

    private record DownloadOption(
        string Description,
        int? ResolutionWidth,
        int? ResolutionHeight,
        double? FileSize,
        double? Fps,
        string? Codec,
        string Url);
    
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
