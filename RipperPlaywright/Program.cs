using RipperPlaywright;
using System.Reflection;

class PlaywrightExample
{
    public static async Task Main()
    {
        try
        {
            const string shortName = "wowgirls";
            ISiteRipper? siteRipper = GetSiteRipper(shortName);
            await siteRipper.ScrapeGalleriesAsync(shortName);

            /*await siteRipper.DownloadAsync(
                shortName,
                new DownloadConditions(
                    new DateRange(
                        new DateOnly(2022, 12, 27), new DateOnly(2022, 12, 31))));*/
        }
        catch (Exception ex)
        {
            Console.WriteLine(ex.ToString());
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
