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
                args = new string[] { "czechvr", "downloadscenes" };
            }

            using var log = new LoggerConfiguration()
                .WriteTo.Console()
                .MinimumLevel.Verbose()
                .CreateLogger();
            Log.Logger = log;

            Log.Information("Culture Extractor");

            string shortName = args[0];
            var browserSettings = new BrowserSettings(false);

            switch (args[1])
            {
                case "scenes":
                    ISiteRipper? siteRipper = GetRipper<ISiteRipper>(shortName);
                    log.Information($"Culture Extractor, using {siteRipper.GetType()}");
                    await siteRipper.ScrapeScenesAsync(shortName, browserSettings);
                    break;
                case "galleries":
                    ISiteRipper? siteRipper2 = GetRipper<ISiteRipper>(shortName);
                    log.Information($"Culture Extractor, using {siteRipper2.GetType()}");
                    await siteRipper2.ScrapeGalleriesAsync(shortName, browserSettings);
                    break;
                case "downloadscenes":
                    ISceneDownloader? sceneDownloader = GetRipper<ISceneDownloader>(shortName);
                    log.Information($"Culture Extractor, using {sceneDownloader.GetType()}");
                    await sceneDownloader.DownloadScenesAsync(shortName, new DownloadConditions(new DateRange(new DateOnly(2012, 06, 24), new DateOnly(2024, 01, 01)), null), browserSettings);
                    break;
                default:
                    throw new Exception($"Could not find with {args[0]} {args[1]}");
            }

            /*await siteRipper.DownloadAsync(
                shortName,
                new DownloadConditions(
                    new DateRange(
                        new DateOnly(2022, 12, 27), new DateOnly(2022, 12, 31))));*/
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);
        }
    }

    private static T GetRipper<T>(string shortName) where T : class
    {
        Type attributeType = typeof(PornSiteAttribute);

        var siteRipperTypes = Assembly
            .GetExecutingAssembly()
            .GetTypes()
            .Where(type => typeof(T).IsAssignableFrom(type))
            .Where(type =>
            {
                object[] attributes = type.GetCustomAttributes(attributeType, true);
                return attributes.Length > 0 && attributes.Any(attribute => (attribute as PornSiteAttribute)?.ShortName == shortName);
            });

        if (!siteRipperTypes.Any())
        {
            throw new ArgumentException($"Could not find any class with short name {shortName} with type {typeof(T)}");
        }
        if (siteRipperTypes.Count() > 2)
        {
            throw new ArgumentException($"Found more than one classes with short name {shortName} with type {typeof(T)}");
        }

        var siteRipperType = siteRipperTypes.First();
        T? siteRipper = Activator.CreateInstance(siteRipperType) as T;
        if (siteRipper == null)
        {
            throw new ArgumentException($"Could not instantiate a class with type {siteRipperType}");
        }

        return siteRipper;
    }
}
