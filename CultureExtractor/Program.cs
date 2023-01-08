using CultureExtractor;
using Serilog;
using System.Reflection;

class PlaywrightExample
{
    public static async Task Main(string[] args)
    {
        try
        {
            if (System.Diagnostics.Debugger.IsAttached)
            {
                args = new string[] { "czechvr", "scenes" };
            }

            using var log = new LoggerConfiguration()
                .WriteTo.Console()
                .MinimumLevel.Verbose()
                .CreateLogger();
            Log.Logger = log;

            string shortName = args[0];
            ISiteRipper? siteRipper = GetSiteRipper(shortName);

            log.Information($"Culture Extractor, using {siteRipper.GetType()}");

            var browserSettings = new BrowserSettings(true);

            switch (args[1])
            {
                case "scenes":
                    await siteRipper.ScrapeScenesAsync(shortName, browserSettings);
                    break;
                case "galleries":
                    await siteRipper.ScrapeGalleriesAsync(shortName, browserSettings);
                    break;
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

    private static ISiteRipper GetSiteRipper(string shortName)
    {
        Type attributeType = typeof(PornSiteAttribute);

        var siteRipperTypes = Assembly
            .GetExecutingAssembly()
            .GetTypes()
            .Where(type => typeof(ISiteRipper).IsAssignableFrom(type))
            .Where(type =>
            {
                object[] attributes = type.GetCustomAttributes(attributeType, true);
                return attributes.Length > 0 && attributes.Any(attribute => (attribute as PornSiteAttribute)?.ShortName == shortName);
            });

        if (!siteRipperTypes.Any())
        {
            throw new ArgumentException($"Could not any site ripper with short name {shortName}");
        }
        if (siteRipperTypes.Count() > 2)
        {
            throw new ArgumentException($"Could not any site ripper with short name {shortName}");
        }

        var siteRipperType = siteRipperTypes.First();
        ISiteRipper? siteRipper = Activator.CreateInstance(siteRipperType) as ISiteRipper;
        if (siteRipper == null)
        {
            throw new ArgumentException($"Could not instantiate a class with type {siteRipperType}");
        }

        return siteRipper;
    }
}
