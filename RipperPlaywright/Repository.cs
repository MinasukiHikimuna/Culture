using Microsoft.EntityFrameworkCore;

namespace RipperPlaywright
{
    public class Repository
    {
        private readonly SqliteContext _sqliteContext;

        public Repository(SqliteContext sqliteContext)
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

        public async Task<Scene> SaveSceneAsync(Scene scene)
        {
            var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Id == scene.Site.Id);

            List<SitePerformerEntity> performerEntities = await GetOrCreatePerformersAsync(scene.Performers, siteEntity);
            List<SiteTagEntity> tagEntities = await GetOrCreateTagsAsync(scene.Tags, siteEntity);

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

                SiteId = siteEntity.Id,
                Site = siteEntity
            };

            await _sqliteContext.Scenes.AddAsync(sceneEntity);
            await _sqliteContext.SaveChangesAsync();

            return Convert(sceneEntity);
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
            var performerEntities = performers.Select(p => new SitePerformerEntity() { Name = p.Name, ShortName = p.Id, Url = p.Url, SiteId = siteEntity.Id, Site = siteEntity, Scenes = new List<SceneEntity>() }).ToList();
            var shortNames = performerEntities.Select(p => p.ShortName).ToList();

            var existingPerformers = await _sqliteContext.Performers.Where(p => shortNames.Contains(p.ShortName)).ToListAsync();
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

        private static Scene Convert(SceneEntity sceneEntity)
        {
            return new Scene(
                sceneEntity.Id,
                Convert(sceneEntity.Site),
                sceneEntity.ReleaseDate,
                sceneEntity.ShortName,
                sceneEntity.Name,
                sceneEntity.Url,
                sceneEntity.Description,
                sceneEntity.Duration,
                sceneEntity.Performers.Select(Convert),
                sceneEntity.Tags.Select(Convert));
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
    }
}
