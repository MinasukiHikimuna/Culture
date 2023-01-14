using CultureExtractor.Interfaces;
using Serilog;
using System.Reflection;

namespace CultureExtractor;

class PlaywrightExample
{
    public static async Task Main(string[] args)
    {
        try
        {
            if (System.Diagnostics.Debugger.IsAttached)
            {
                args = new string[] { "sexart", "downloadscenes" };
            }

            using var log = new LoggerConfiguration()
                .WriteTo.Console()
                .MinimumLevel.Verbose()
                .CreateLogger();
            Log.Logger = log;

            Log.Information("Culture Extractor");

            string shortName = args[0];
            var browserSettings = new BrowserSettings(false);

            var jobType = args[1] switch
            {
                "scrapescenes" => JobType.ScrapeScenes,
                "scrapemodels" => JobType.ScrapeModels,
                "scrapegalleries" => JobType.ScrapeGalleries,
                "downloadscenes" => JobType.DownloadScenes,
                "downloadgalleries" => JobType.DownloadGalleries,
                _ => throw new NotImplementedException($"Unknown job type {args[1]}")
            };

            var networkRipper = new NetworkRipper(new Repository(new SqliteContext()));
            await networkRipper.InitializeAsync(args[0], jobType, browserSettings);
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);
        }
    }
}
