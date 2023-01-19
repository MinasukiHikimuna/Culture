using CultureExtractor.Interfaces;
using Serilog;

namespace CultureExtractor;

class PlaywrightExample
{
    public static async Task Main(string[] args)
    {
        try
        {
            if (System.Diagnostics.Debugger.IsAttached)
            {
                args = new string[] { "dorcelclub", "download-scenes" };
            }

            using var log = new LoggerConfiguration()
                .WriteTo.Console()
                    .MinimumLevel.Verbose()
                .CreateLogger();
            Log.Logger = log;

            Log.Information("Culture Extractor");

            string shortName = args[0];
            var browserSettings = new BrowserSettings(true);

            var jobType = args[1] switch
            {
                "scrape-scenes" => JobType.ScrapeScenes,
                "scrape-models" => JobType.ScrapeModels,
                "scrape-galleries" => JobType.ScrapeGalleries,
                "download-scenes" => JobType.DownloadScenes,
                "download-galleries" => JobType.DownloadGalleries,
                _ => throw new NotImplementedException($"Unknown job type {args[1]}")
            };

            var networkRipper = new NetworkRipper(new Repository(new SqliteContext()));
            await networkRipper.InitializeAsync(
                args[0],
                jobType,
                browserSettings,
                DownloadConditions.All(PreferredDownloadQuality.Phash));
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);
        }
    }
}
