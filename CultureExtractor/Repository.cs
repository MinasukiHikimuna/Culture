using Microsoft.EntityFrameworkCore;
using Serilog;
using System.Text.Json;
using CultureExtractor.Models;

namespace CultureExtractor;

public class Repository : IRepository
{
    private readonly ISqliteContext _sqliteContext;

    public Repository(ISqliteContext sqliteContext)
    {
        _sqliteContext = sqliteContext;
    }

    public async Task<IEnumerable<Site>> GetSitesAsync()
    {
        var siteEntities = await _sqliteContext.Sites
            .Include(s => s.StorageState)
            .OrderBy(s => s.Name)
            .ToListAsync();

        return siteEntities.Select(Convert).AsEnumerable();
    }

    public async Task<IEnumerable<SubSite?>> GetSubSitesAsync(Guid siteUuid)
    {
        var subSites = await _sqliteContext.SubSites
            .Where(s => s.SiteUuid == siteUuid.ToString())
            .OrderBy(s => s.Name)
            .ToListAsync();

        return subSites.Select(Convert).AsEnumerable();
    }
    
    public async Task<Site> GetSiteAsync(string shortName)
    {
        var siteEntity = await _sqliteContext.Sites
            .Include(s => s.StorageState)
            .FirstAsync(site => site.ShortName == shortName);

        return Convert(siteEntity);
    }

    public async Task<IEnumerable<Scene>> GetScenesAsync()
    {
        var siteEntities = await _sqliteContext.Releases
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .OrderBy(s => s.Site.Name)
            .ThenByDescending(s => s.ReleaseDate)
            .ToListAsync();

        return siteEntities.Select(Convert).AsEnumerable();
    }

    public async Task<IEnumerable<Scene>> QueryScenesAsync(Site site, DownloadConditions downloadConditions)
    {
        var siteEntities = await _sqliteContext.Releases
            .Include(s => s.Site)
            .Include(s => s.SubSite)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Where(s => s.SiteUuid == site.Uuid.ToString())
            .Where(s => !downloadConditions.DownloadedFileNames.Any() || s.Downloads.Any(d => downloadConditions.DownloadedFileNames.Contains(d.SavedFilename)))
            .Where(s => !s.Downloads.Any(d => d.DownloadQuality == Enum.GetName(downloadConditions.PreferredDownloadQuality)))
            .OrderBy(s => s.Site.Name)
            .ThenByDescending(s => s.ReleaseDate)
            .ToListAsync();

        return siteEntities.Select(Convert).AsEnumerable();
    }

    public async Task<Scene?> GetSceneAsync(string siteShortName, string sceneShortName)
    {
        var sceneEntity = await _sqliteContext.Releases
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .FirstOrDefaultAsync(s => s.Site.ShortName == siteShortName && s.ShortName == sceneShortName);

        return sceneEntity != null
            ? Convert(sceneEntity)
            : null;
    }

    public async Task<IReadOnlyList<Scene>> GetScenesAsync(string siteShortName, IList<string> sceneShortNames)
    {
        var sceneEntities = await _sqliteContext.Releases
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Where(s => s.Site.ShortName == siteShortName && sceneShortNames.Contains(s.ShortName))
            .ToListAsync();

        return sceneEntities
            .Select(Convert)
            .ToList()
            .AsReadOnly();
    }

    public async Task<SubSite> UpsertSubSite(SubSite subSite)
    {
        var existingSubSiteEntity = await _sqliteContext.SubSites
            .Include(s => s.Site)
            .FirstOrDefaultAsync(s =>
                s.Site.ShortName == subSite.Site.ShortName &&
                s.ShortName == subSite.ShortName);

        if (existingSubSiteEntity != null)
        {
            if (existingSubSiteEntity.Name != subSite.Name)
            {
                existingSubSiteEntity.Name = subSite.Name;
                await _sqliteContext.SaveChangesAsync();
            }

            return Convert(existingSubSiteEntity);
        }

        var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Uuid == subSite.Site.Uuid.ToString());
        var subSiteEntity = new SubSiteEntity()
        {
            Uuid = UuidGenerator.Generate().ToString(),
            ShortName = subSite.ShortName,
            Name = subSite.Name,
            SiteUuid = siteEntity.Uuid,
            Site = siteEntity
        };

        await _sqliteContext.SubSites.AddAsync(subSiteEntity);
        await _sqliteContext.SaveChangesAsync();

        return Convert(subSiteEntity);
    }

    public async Task<Scene> UpsertScene(Scene scene)
    {
        var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Uuid == scene.Site.Uuid.ToString());
        SubSiteEntity subSiteEntity = null;
        if (scene.SubSite != null)
        {
            subSiteEntity = await _sqliteContext.SubSites.FirstOrDefaultAsync(s => s.SiteUuid == scene.Site.Uuid.ToString() && s.ShortName == scene.SubSite.ShortName);
            if (subSiteEntity == null)
            {
                subSiteEntity = new SubSiteEntity()
                {
                    Uuid = UuidGenerator.Generate().ToString(),
                    ShortName = scene.SubSite.ShortName,
                    Name = scene.SubSite.Name,
                    SiteUuid = siteEntity.Uuid,
                    Site = siteEntity
                };
                _sqliteContext.SubSites.Add(subSiteEntity);
                await _sqliteContext.SaveChangesAsync();
            }
        }

        List<SitePerformerEntity> performerEntities = await GetOrCreatePerformersAsync(scene.Performers, siteEntity);
        List<SiteTagEntity> tagEntities = await GetOrCreateTagsAsync(scene.Tags, siteEntity);

        var existingSceneEntity = await _sqliteContext.Releases.FirstOrDefaultAsync(s => s.Uuid == scene.Uuid.ToString());
        
        if (existingSceneEntity == null)
        {
            var sceneEntity = new SceneEntity()
            {
                Uuid = scene.Uuid.ToString(),
                ReleaseDate = scene.ReleaseDate,
                ShortName = scene.ShortName,
                Name = scene.Name,
                Url = scene.Url,
                Description = scene.Description,
                Duration = scene.Duration,
                Performers = performerEntities,
                Tags = tagEntities,
                Created = DateTime.Now,
                LastUpdated = DateTime.Now,

                SiteUuid = siteEntity.Uuid,
                Site = siteEntity,
                SubSiteUuid = subSiteEntity?.Uuid,
                SubSite = subSiteEntity,

                JsonDocument = scene.JsonDocument,

                Downloads = new List<DownloadEntity>(),
                DownloadOptions = JsonSerializer.Serialize(scene.DownloadOptions)
            };
            await _sqliteContext.Releases.AddAsync(sceneEntity);
            await _sqliteContext.SaveChangesAsync();

            return Convert(sceneEntity);
        }

        existingSceneEntity.ReleaseDate = scene.ReleaseDate;
        existingSceneEntity.ShortName = scene.ShortName;
        existingSceneEntity.Name = scene.Name;
        existingSceneEntity.Url = scene.Url;
        existingSceneEntity.Description = scene.Description;
        existingSceneEntity.Duration = scene.Duration;
        existingSceneEntity.Performers = performerEntities;
        existingSceneEntity.Tags = tagEntities;
        existingSceneEntity.JsonDocument = scene.JsonDocument;

        if (existingSceneEntity.Created == DateTime.MinValue)
        {
            existingSceneEntity.Created = DateTime.Now;
        }
        existingSceneEntity.LastUpdated = DateTime.Now;

        existingSceneEntity.SiteUuid = siteEntity.Uuid;
        existingSceneEntity.Site = siteEntity;

        existingSceneEntity.DownloadOptions = JsonSerializer.Serialize(scene.DownloadOptions);

        await _sqliteContext.SaveChangesAsync();

        return Convert(existingSceneEntity);
    }

    private async Task<List<SitePerformerEntity>> GetOrCreatePerformersAsync(IEnumerable<SitePerformer> performers, SiteEntity siteEntity)
    {
        var shortNames = performers.Select(p => p.ShortName).ToList();
        
        var existingPerformers = await _sqliteContext.Performers.Where(p => p.SiteUuid == siteEntity.Uuid && shortNames.Contains(p.ShortName)).ToListAsync();
        var existingPerformerShortNames = existingPerformers.Select(p => p.ShortName).ToList();
        
        var newPerformersEntities = performers
            .Where(p => !existingPerformerShortNames.Contains(p.ShortName))
            .Select(p => new SitePerformerEntity
            {
                Uuid = UuidGenerator.Generate().ToString(),
                Name = p.Name,
                ShortName = p.ShortName,
                Url = p.Url,
                SiteUuid = siteEntity.Uuid,
                Site = siteEntity,
                Releases = new List<SceneEntity>()
            }).ToList();

        if (newPerformersEntities.Any())
        {
            await _sqliteContext.Performers.AddRangeAsync(newPerformersEntities);
            await _sqliteContext.SaveChangesAsync();            
        }

        return existingPerformers.Concat(newPerformersEntities).ToList();
    }

    private async Task<List<SiteTagEntity>> GetOrCreateTagsAsync(IEnumerable<SiteTag> tags, SiteEntity siteEntity)
    {
        var tagShortNames = tags.Select(t => t.Id).ToList();
        
        var existingTags = await _sqliteContext.Tags.Where(t => t.SiteUuid == siteEntity.Uuid && tagShortNames.Contains(t.ShortName)).ToListAsync();
        var existingTagShortNames = existingTags.Select(t => t.ShortName).ToList();
        
        var newTagEntities = tags
            .Where(t => !existingTagShortNames.Contains(t.Id))
            .Select(t => new SiteTagEntity
            {
                Uuid = UuidGenerator.Generate().ToString(),
                Name = t.Name,
                ShortName = t.Id,
                Url = t.Url,
                SiteUuid = siteEntity.Uuid,
                Site = siteEntity,
                Releases = new List<SceneEntity>()
            }).ToList();

        if (newTagEntities.Any())
        {
            await _sqliteContext.Tags.AddRangeAsync(newTagEntities);
            await _sqliteContext.SaveChangesAsync();            
        }

        return existingTags.Concat(newTagEntities).ToList();
    }

    public async Task UpdateStorageStateAsync(Site site, string storageState)
    {
        var storageStateEntity = await _sqliteContext.StorageStates.FirstOrDefaultAsync(s => s.SiteUuid == site.Uuid.ToString());
        if (storageStateEntity != null)
        {
            storageStateEntity.StorageState = storageState;
        }
        else
        {
            var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Uuid == site.Uuid.ToString());
            _sqliteContext.StorageStates.Add(new StorageStateEntity()
            {
                Uuid = UuidGenerator.Generate().ToString(),
                StorageState = storageState,

                SiteUuid = siteEntity.Uuid,
                Site = siteEntity
            });
        }

        await _sqliteContext.SaveChangesAsync();
        Log.Information($"Updated storage state for {site.Name}.");
    }

    private static Site Convert(SiteEntity siteEntity)
    {
        return new Site(
            Guid.Parse(siteEntity.Uuid),
            siteEntity.ShortName,
            siteEntity.Name,
            siteEntity.Url,
            siteEntity.Username,
            siteEntity.Password,
            siteEntity.StorageState?.StorageState ?? string.Empty);
    }

    private static SubSite? Convert(SubSiteEntity? subSiteEntity)
    {
        return subSiteEntity != null
            ? new SubSite(
                Guid.Parse(subSiteEntity.Uuid),
                subSiteEntity.ShortName,
                subSiteEntity.Name,
                Convert(subSiteEntity.Site)
              )
            : null;
    }

    private static Scene Convert(SceneEntity sceneEntity)
    {
        var downloadOptions = string.IsNullOrEmpty(sceneEntity.DownloadOptions)
            ? "[]"
            : sceneEntity.DownloadOptions;

        return new Scene(
            Guid.Parse(sceneEntity.Uuid),
            Convert(sceneEntity.Site),
            Convert(sceneEntity.SubSite),
            sceneEntity.ReleaseDate,
            sceneEntity.ShortName,
            sceneEntity.Name,
            sceneEntity.Url,
            sceneEntity.Description,
            sceneEntity.Duration,
            sceneEntity.Performers.Select(Convert),
            sceneEntity.Tags.Select(Convert),
            JsonSerializer.Deserialize<IEnumerable<DownloadOption>>(downloadOptions),
            sceneEntity.JsonDocument,
            sceneEntity.LastUpdated);
    }

    private static SitePerformer Convert(SitePerformerEntity performerEntity)
    {
        return new SitePerformer(
            performerEntity.ShortName ?? performerEntity.Name,
            performerEntity.Name,
            performerEntity.Url ?? string.Empty);
    }

    private static SiteTag Convert(SiteTagEntity siteTagEntity)
    {
        return new SiteTag(
            siteTagEntity.ShortName ?? siteTagEntity.Name,
            siteTagEntity.Name,
            siteTagEntity.Url ?? string.Empty);
    }

    public async Task SaveDownloadAsync(Download download, PreferredDownloadQuality preferredDownloadQuality)
    {
        var sceneEntity = await _sqliteContext.Releases.FirstAsync(s => s.Uuid == download.Scene.Uuid.ToString());

        var json = JsonSerializer.Serialize(new JsonSummary(download.DownloadOption, download.VideoHashes));

        _sqliteContext.Downloads.Add(new DownloadEntity
        {
            Uuid = UuidGenerator.Generate().ToString(),
            DownloadedAt = DateTime.Now,
            DownloadOptions = json,
            DownloadQuality = Enum.GetName(preferredDownloadQuality),
            OriginalFilename = download.OriginalFilename,
            SavedFilename = download.SavedFilename,

            ReleaseUuid = sceneEntity.Uuid,
            Release = sceneEntity,
        });
        await _sqliteContext.SaveChangesAsync();
    }

    private class JsonSummary
    {
        public JsonSummary(DownloadOption downloadOption, VideoHashes videoHashes)
        {
            DownloadOption = downloadOption;
            VideoHashes = videoHashes;
        }

        public DownloadOption DownloadOption { get; }
        public VideoHashes VideoHashes { get; }
    }
}
