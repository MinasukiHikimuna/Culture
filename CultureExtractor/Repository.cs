using Microsoft.EntityFrameworkCore;
using Serilog;
using System.Text.Json;

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

    public async Task<Site> GetSiteAsync(string shortName)
    {
        var siteEntity = await _sqliteContext.Sites
            .Include(s => s.StorageState)
            .FirstAsync(site => site.ShortName == shortName);

        return Convert(siteEntity);
    }

    public async Task<IEnumerable<Scene>> GetScenesAsync()
    {
        var siteEntities = await _sqliteContext.Scenes
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
        var siteEntities = await _sqliteContext.Scenes
            .Include(s => s.Site)
            .Include(s => s.SubSite)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Where(s => s.SiteId == site.Id)
            .Where(s => !downloadConditions.DownloadedFileNames.Any() || s.Downloads.Any(d => downloadConditions.DownloadedFileNames.Contains(d.SavedFilename)))
            .Where(s => !s.Downloads.Any(d => d.DownloadQuality == Enum.GetName(downloadConditions.PreferredDownloadQuality)))
            .OrderBy(s => s.Site.Name)
            .ThenByDescending(s => s.ReleaseDate)
            .ToListAsync();

        return siteEntities.Select(Convert).AsEnumerable();
    }

    public async Task<Scene?> GetSceneAsync(string siteShortName, string sceneShortName)
    {
        var sceneEntity = await _sqliteContext.Scenes
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .FirstOrDefaultAsync(s => s.Site.ShortName == siteShortName && s.ShortName == sceneShortName);

        return sceneEntity != null
            ? Convert(sceneEntity)
            : null;
    }

    public async Task<Gallery?> GetGalleryAsync(string siteShortName, string galleryShortScene)
    {
        var sceneEntity = await _sqliteContext.Galleries
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .FirstOrDefaultAsync(s => s.Site.ShortName == siteShortName && s.ShortName == galleryShortScene);

        return sceneEntity != null
            ? Convert(sceneEntity)
            : null;
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

        var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Id == subSite.Site.Id);
        var subSiteEntity = new SubSiteEntity()
        {
            ShortName = subSite.ShortName,
            Name = subSite.Name,
            SiteId = siteEntity.Id,
            Site = siteEntity
        };

        await _sqliteContext.SubSites.AddAsync(subSiteEntity);
        await _sqliteContext.SaveChangesAsync();

        return Convert(subSiteEntity);
    }

    public async Task<Scene> UpsertScene(Scene scene)
    {
        var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Id == scene.Site.Id);
        SubSiteEntity subSiteEntity = null;
        if (scene.SubSite != null)
        {
            subSiteEntity = await _sqliteContext.SubSites.FirstOrDefaultAsync(s => s.SiteId == scene.Site.Id && s.ShortName == scene.SubSite.ShortName);
            if (subSiteEntity == null)
            {
                subSiteEntity = new SubSiteEntity()
                {
                    ShortName = scene.SubSite.ShortName,
                    Name = scene.SubSite.Name,
                    SiteId = siteEntity.Id,
                    Site = siteEntity
                };
                _sqliteContext.SubSites.Add(subSiteEntity);
                await _sqliteContext.SaveChangesAsync();
            }
        }

        List<SitePerformerEntity> performerEntities = await GetOrCreatePerformersAsync(scene.Performers, siteEntity);
        List<SiteTagEntity> tagEntities = await GetOrCreateTagsAsync(scene.Tags, siteEntity);

        if (!scene.Id.HasValue)
        {
            var sceneEntity = new SceneEntity()
            {
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

                SiteId = siteEntity.Id,
                Site = siteEntity,
                SubSiteId = subSiteEntity?.Id,
                SubSite = subSiteEntity,

                JsonDocument = scene.JsonDocument,

                Downloads = new List<DownloadEntity>(),
                DownloadOptions = JsonSerializer.Serialize(scene.DownloadOptions)
            };
            await _sqliteContext.Scenes.AddAsync(sceneEntity);
            await _sqliteContext.SaveChangesAsync();

            return Convert(sceneEntity);
        }

        var existingSceneEntity = await _sqliteContext.Scenes.FirstAsync(s => s.Id == scene.Id);

        existingSceneEntity.ReleaseDate = scene.ReleaseDate;
        existingSceneEntity.ShortName = scene.ShortName;
        existingSceneEntity.Name = scene.Name;
        existingSceneEntity.Url = scene.Url;
        existingSceneEntity.Description = scene.Description;
        existingSceneEntity.Duration = scene.Duration;
        existingSceneEntity.Performers = performerEntities;
        existingSceneEntity.Tags = tagEntities;

        if (existingSceneEntity.Created == DateTime.MinValue)
        {
            existingSceneEntity.Created = DateTime.Now;
        }
        existingSceneEntity.LastUpdated = DateTime.Now;

        existingSceneEntity.SiteId = siteEntity.Id;
        existingSceneEntity.Site = siteEntity;

        existingSceneEntity.DownloadOptions = JsonSerializer.Serialize(scene.DownloadOptions);

        await _sqliteContext.SaveChangesAsync();

        return Convert(existingSceneEntity);
    }

    public async Task<Gallery> SaveGalleryAsync(Gallery gallery)
    {
        var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Id == gallery.Site.Id);

        List<SitePerformerEntity> performerEntities = await GetOrCreatePerformersAsync(gallery.Performers, siteEntity);
        List<SiteTagEntity> tagEntities = await GetOrCreateTagsAsync(gallery.Tags, siteEntity);

        var galleryEntity = new GalleryEntity()
        {
            ReleaseDate = gallery.ReleaseDate,
            ShortName = gallery.ShortName,
            Name = gallery.Name,
            Url = gallery.Url,
            Description = gallery.Description,
            Pictures = gallery.Pictures,
            Performers = performerEntities,
            Tags = tagEntities,

            SiteId = siteEntity.Id,
            Site = siteEntity
        };

        await _sqliteContext.Galleries.AddAsync(galleryEntity);
        await _sqliteContext.SaveChangesAsync();

        return Convert(galleryEntity);
    }

    private async Task<List<SitePerformerEntity>> GetOrCreatePerformersAsync(IEnumerable<SitePerformer> performers, SiteEntity siteEntity)
    {
        var performerEntities = performers.Select(p => new SitePerformerEntity() { Name = p.Name, ShortName = p.ShortName, Url = p.Url, SiteId = siteEntity.Id, Site = siteEntity, Scenes = new List<SceneEntity>() }).ToList();
        var shortNames = performerEntities.Select(p => p.ShortName).ToList();

        var existingPerformers = await _sqliteContext.Performers.Where(p => p.SiteId == siteEntity.Id && shortNames.Contains(p.ShortName)).ToListAsync();
        var existingPerformerShortNames = existingPerformers.Select(p => p.ShortName).ToList();

        var newPerformers = performerEntities.Where(p => !existingPerformerShortNames.Contains(p.ShortName)).ToList();
        await _sqliteContext.Performers.AddRangeAsync(newPerformers);

        await _sqliteContext.SaveChangesAsync();

        return existingPerformers.Concat(newPerformers).ToList();
    }

    private async Task<List<SiteTagEntity>> GetOrCreateTagsAsync(IEnumerable<SiteTag> tags, SiteEntity siteEntity)
    {
        var tagEntities = tags.Select(p => new SiteTagEntity() { Name = p.Name, ShortName = p.Id, Url = p.Url, SiteId = siteEntity.Id, Site = siteEntity, Scenes = new List<SceneEntity>() }).ToList();
        var tagShortNames = tagEntities.Select(t => t.ShortName).ToList();

        var existingTags = await _sqliteContext.Tags.Where(t => tagShortNames.Contains(t.ShortName)).ToListAsync();
        var existingTagShortNames = existingTags.Select(t => t.ShortName).ToList();

        var newTags = tagEntities.Where(t => !existingTagShortNames.Contains(t.ShortName)).ToList();
        await _sqliteContext.Tags.AddRangeAsync(newTags);

        await _sqliteContext.SaveChangesAsync();

        return existingTags.Concat(newTags).ToList();
    }

    public async Task UpdateStorageStateAsync(Site site, string storageState)
    {
        var storageStateEntity = await _sqliteContext.StorageStates.FirstOrDefaultAsync(s => s.SiteId == site.Id);
        if (storageStateEntity != null)
        {
            storageStateEntity.StorageState = storageState;
        }
        else
        {
            var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Id == site.Id);
            _sqliteContext.StorageStates.Add(new StorageStateEntity()
            {
                StorageState = storageState,

                SiteId = siteEntity.Id,
                Site = siteEntity
            });
        }

        await _sqliteContext.SaveChangesAsync();
        Log.Information($"Updated storage state for {site.Name}.");
    }

    private static Site Convert(SiteEntity siteEntity)
    {
        return new Site(
            siteEntity.Id,
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
                subSiteEntity.Id,
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
            sceneEntity.Id,
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
            sceneEntity.JsonDocument);
    }

    private static Gallery Convert(GalleryEntity galleryEntity)
    {
        return new Gallery(
            galleryEntity.Id,
            Convert(galleryEntity.Site),
            galleryEntity.ReleaseDate,
            galleryEntity.ShortName,
            galleryEntity.Name,
            galleryEntity.Url,
            galleryEntity.Description,
            galleryEntity.Pictures,
            galleryEntity.Performers.Select(Convert),
            galleryEntity.Tags.Select(Convert));
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
        var sceneEntity = await _sqliteContext.Scenes.FirstAsync(s => s.Id == download.Scene.Id);

        var json = JsonSerializer.Serialize(new JsonSummary(download.DownloadOption, download.VideoHashes));

        _sqliteContext.Downloads.Add(new DownloadEntity()
        {
            DownloadedAt = DateTime.Now,
            DownloadOptions = json,
            DownloadQuality = Enum.GetName(preferredDownloadQuality),
            OriginalFilename = download.OriginalFilename,
            SavedFilename = download.SavedFilename,

            SceneId = sceneEntity.Id,
            Scene = sceneEntity,
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
