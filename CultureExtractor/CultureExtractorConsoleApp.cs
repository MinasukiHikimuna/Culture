using System.Text.Json;
using System.Text.Json.Serialization;
using CommandLine;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Serilog;

namespace CultureExtractor;

public class CultureExtractorConsoleApp
{
    private readonly INetworkRipper _networkRipper;
    private readonly IRepository _repository;
    private readonly Interfaces.ICultureExtractorContext _cultureExtractorContext;

    public CultureExtractorConsoleApp(IRepository repository, INetworkRipper networkRipper, Interfaces.ICultureExtractorContext cultureExtractorContext)
    {
        _networkRipper = networkRipper;
        _repository = repository;
        _cultureExtractorContext = cultureExtractorContext;
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
                opts.FullScrapeLastUpdated = DateTime.Now.AddDays(-1);
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
                DownloadedFileNames = opts.DownloadedFileNames.ToList() ?? new List<string>(),
                DownloadOrder = opts.Order
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
        // return await MigrateReleases(opts);
        return await MigrateDownloads(opts);
    }

    private static async Task<int> MigrateDownloads(MigrateOptions opts)
    {
        try
        {
            InitializeLogger(opts);

            Log.Information("Culture Extractor");

            using var stream = File.OpenRead(@"C:\Github\CultureExtractor\CultureExtractor\downloads.json");
            using var context = new CultureExtractorContext();
            var options = new JsonSerializerOptions
            {
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
                PropertyNameCaseInsensitive = true
            };
            options.Converters.Add(new DateTimeConverter());

            // Create a dictionary of SiteEntity objects keyed by their ShortName
            var releases = await context.Releases.ToDictionaryAsync(s => s.Uuid);
            var downloads = new List<DownloadEntity>();
            
            try
            {
                await foreach (var download in JsonSerializer.DeserializeAsyncEnumerable<DownloadEntity>(stream, options))
                {
                    // Set the SiteEntity reference using the dictionary
                    if (releases.TryGetValue(download.ReleaseUuid, out var release))
                    {
                        download.Release = release;
                    }
                    else
                    {
                        Log.Error("Release not found: {Uuid} {ReleaseUuid}", download.Uuid, download.ReleaseUuid);
                        continue;
                    }

                    Log.Information("Release: {Uuid}, {ReleaseUuid}, {Release}", download.Uuid, download.ReleaseUuid, download.Release.Name);
                    
                    downloads.Add(download);
                    if (downloads.Count >= 1000) // Adjust batch size as needed
                    {
                        await context.Downloads.AddRangeAsync(downloads);
                        await context.SaveChangesAsync();
                        downloads.Clear();
                    }
                }
                
                // Save any remaining releases
                if (downloads.Count > 0)
                {
                    await context.Downloads.AddRangeAsync(downloads);
                    await context.SaveChangesAsync();
                }
            }
            catch (JsonException ex)
            {
                Log.Error("Failed to deserialize JSON: {Json}", ex.Path);
                throw;
            }

            return 0;
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);

            return -1;
        }
    }
    
    private static async Task<int> MigrateReleases(MigrateOptions opts)
    {
        try
        {
            InitializeLogger(opts);

            Log.Information("Culture Extractor");

            using var stream = File.OpenRead(@"C:\Github\CultureExtractor\CultureExtractor\releases_new.json");
            using var context = new CultureExtractorContext();
            var options = new JsonSerializerOptions
            {
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
                PropertyNameCaseInsensitive = true
            };
            options.Converters.Add(new DateTimeConverter());

            var sites = await context.Sites.ToDictionaryAsync(s => s.Uuid);
            var releases = new List<ReleaseEntity>();

            try
            {
                await foreach (var release in JsonSerializer.DeserializeAsyncEnumerable<ReleaseEntity>(stream, options))
                {
                    // Set the SiteEntity reference using the dictionary
                    if (sites.TryGetValue(release.SiteUuid, out var site))
                    {
                        release.Site = site;
                    }
                    else
                    {
                        Log.Error("");
                    }

                    Log.Information("Release: {Uuid} {Name}", release.Uuid, release.Name);

                    releases.Add(release);
                    if (releases.Count >= 1000) // Adjust batch size as needed
                    {
                        await context.Releases.AddRangeAsync(releases);
                        await context.SaveChangesAsync();
                        releases.Clear();
                    }
                }

                // Save any remaining releases
                if (releases.Count > 0)
                {
                    await context.Releases.AddRangeAsync(releases);
                    await context.SaveChangesAsync();
                }
            }
            catch (JsonException ex)
            {
                Log.Error("Failed to deserialize JSON: {Json}", ex.Path);
                throw;
            }

            return 0;
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);

            return -1;
        }
    }

    public class DateTimeConverter : JsonConverter<DateTime>
    {
        public override DateTime Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
        {
            if (DateTime.TryParse(reader.GetString(), out var date))
            {
                return date;
            }
            else
            {
                return DateTime.MinValue;
            }
        }

        public override void Write(Utf8JsonWriter writer, DateTime value, JsonSerializerOptions options)
        {
            writer.WriteStringValue(value.ToString("yyyy-MM-dd"));
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
