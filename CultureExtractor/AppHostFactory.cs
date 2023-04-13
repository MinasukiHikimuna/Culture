using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.EntityFrameworkCore;
using CultureExtractor.Interfaces;
using System.Reflection;

namespace CultureExtractor;

public static class AppHostFactory
{
    public static IHost CreateHost(string[] args, string siteShortName)
    {
        return Host.CreateDefaultBuilder(args)
            .ConfigureServices(services =>
            {
                services.AddDbContext<ISqliteContext, SqliteContext>(options => options.UseSqlite(@"Data Source=B:\Ripping\ripping.db"));

                services.AddScoped<IPlaywrightFactory, PlaywrightFactory>();
                services.AddScoped<ICaptchaSolver, CaptchaSolver>();
                services.AddScoped<IRepository, Repository>();
                services.AddScoped<IDownloader, Downloader>();
                services.AddTransient<INetworkRipper, NetworkRipper>();
                services.AddTransient<CultureExtractorConsoleApp>();

                Type siteScraper = GetSiteScraperType<ISiteScraper>(siteShortName);
                IList<Type> types = new List<Type>() { typeof(ISiteScraper) };
                foreach (var type in types)
                {
                    if (siteScraper.IsAssignableTo(type))
                    {
                        services.AddTransient(type, siteScraper);
                    }
                }
            })
            .Build();
    }

    public static CultureExtractorConsoleApp CreateCultureExtractorConsoleApp(IHost host)
    {
        return host.Services.GetRequiredService<CultureExtractorConsoleApp>();
    }

    // The existing GetSiteScraperType method can be moved into this class
    private static Type GetSiteScraperType<T>(string shortName) where T : ISiteScraper
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

        return siteRipperTypes.Single();
    }
}
