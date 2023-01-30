using CommandLine;
using CultureExtractor.Interfaces;
using CultureExtractor.Sites.WowNetwork;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System.Reflection;
using System;
using System.Net.WebSockets;

namespace CultureExtractor;

class Program
{
    static void Main(string[] args)
    {
        if (System.Diagnostics.Debugger.IsAttached)
        {
            var siteShortName = "dorcelclub";

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
                "--verbose",
                "--visible-browser",
            };
        }

        var options = (BaseOptions) Parser.Default.ParseArguments<ScrapeOptions, DownloadOptions>(args).Value;

        var host = Host.CreateDefaultBuilder(args)
            .ConfigureServices(services => {
                services.AddDbContext<ISqliteContext, SqliteContext>(options => options.UseSqlite());

                services.AddScoped<IRepository, Repository>();
                services.AddScoped<IDownloader, Downloader>();
                services.AddTransient<INetworkRipper, NetworkRipper>();
                services.AddTransient<CultureExtractorConsoleApp>();

                Type siteScraper = Program.GetSiteScraperType<ISiteScraper>(options.SiteShortName);
                IList<Type> types = new List<Type>() { typeof(ISceneScraper), typeof(ISceneDownloader) };
                foreach (var type in types)
                {
                    if (siteScraper.IsAssignableTo(type))
                    {
                        services.AddTransient(type, siteScraper);
                    }
                }
            })
            .Build();
        
        var cultureExtractor = host.Services.GetRequiredService<CultureExtractorConsoleApp>();
        cultureExtractor.ExecuteConsoleApp(args);
    }

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
