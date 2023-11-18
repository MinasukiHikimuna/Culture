using System.Net.Http.Headers;
using System.Text.Json;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;

namespace CultureExtractor.Sites;

[Site("tpdb")]
public class ThePornDatabaseRipper : IYieldingScraper
{
    private readonly IRepository _repository;

    public ThePornDatabaseRipper(IRepository repository)
    {
        _repository = repository;
    }

    public async IAsyncEnumerable<Release> ScrapeReleasesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions)
    {
        using HttpClient client = new();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", site.Password);
        
        var sitesResponse = await client.GetAsync($"{site.Url}/sites?q=slayed");
        var sitesJson = await sitesResponse.Content.ReadAsStringAsync();
        var sites = JsonSerializer.Deserialize<ThePornDatabaseSitesResponse.RootObject>(sitesJson);

        var siteObj = sites.data[0];
        
        var existingSubSites = await _repository.GetSubSitesAsync(site.Uuid);
        var existingSubSitesDictionary = existingSubSites.ToDictionary(s => s.ShortName, s => s);
        var subSite = new SubSite(
            existingSubSitesDictionary.TryGetValue(siteObj.uuid, out var existingSubSite)
                ? existingSubSite.Uuid
                : UuidGenerator.Generate(),
            siteObj.uuid,
            siteObj.name,
            site);

        await _repository.UpsertSubSite(subSite);

        int currentPage = 1;
        int totalPages = 0;
        do
        {
            await Task.Delay(5000);
            var scenesResponse = await client.GetAsync($"{site.Url}/scenes?site_id={siteObj.id}&page={currentPage}");
            var scenesJson = await scenesResponse.Content.ReadAsStringAsync();
            var scenes = JsonSerializer.Deserialize<ThePornDatabaseScenesResponse.RootObject>(scenesJson);

            if (scenes.meta != null)
            {
                totalPages = scenes.meta.last_page;
            }

            var existingReleases = await _repository
                .GetReleasesAsync(site.ShortName, scenes.data.Select(s => s.id).ToList());
            var existingReleasesDictionary = existingReleases.ToDictionary(r => r.ShortName, r => r);

            var toBeScraped = scenes.data
                .Where(g => !existingReleasesDictionary.ContainsKey(g.id))
                .ToList();

            foreach (var scene in toBeScraped)
            {
                var release = new Release(
                    existingReleasesDictionary.TryGetValue(scene.id, out var existingRelease)
                        ? existingRelease.Uuid
                        : UuidGenerator.Generate(),
                    site,
                    subSite,
                    DateOnly.ParseExact(scene.date, "yyyy-MM-dd"),
                    scene.id,
                    scene.title,
                    scene.url,
                    scene.description,
                    scene.duration ?? -1,
                    scene.performers.Select(p => new SitePerformer(p.id, p.name, $"{site.Url}/performers/{p.id}")),
                    scene.tags.Select(t => new SiteTag(t.id.ToString(), t.name, string.Empty)),
                    new List<IAvailableFile>(),
                    JsonSerializer.Serialize(scene),
                    DateTime.Now
                );
                    
                yield return release;
            }

            currentPage++;
        } while (currentPage <= totalPages);
    }

    public IAsyncEnumerable<Download> DownloadReleasesAsync(Site site, BrowserSettings browserSettings,
        DownloadConditions downloadConditions)
    {
        throw new NotImplementedException();
    }
}