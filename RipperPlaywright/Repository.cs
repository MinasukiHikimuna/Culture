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

        public async Task<Site> GetSiteAsync(string shortName)
        {
            var siteEntity = await _sqliteContext.Sites
                .Include(s => s.StorageState)
                .FirstAsync(site => site.ShortName == shortName);

            return new Site(
                siteEntity.Id,
                siteEntity.ShortName,
                siteEntity.Name,
                siteEntity.Url,
                siteEntity.Username,
                siteEntity.Password,
                siteEntity.StorageState?.StorageState ?? string.Empty);
        }

        public async Task<int> SaveSceneAsync(Scene scene)
        {
            var siteEntity = await _sqliteContext.Sites.FirstAsync(s => s.Id == scene.Site.Id);

            var performers = scene.Performers.Select(p => new SitePerformerEntity() { Name = p.Name, ShortName = p.Id, Url = p.Url, SiteId = siteEntity.Id, Site = siteEntity, Scenes = new List<SceneEntity>() }).ToList();
            var shortNames = performers.Select(p => p.ShortName).ToList();

            var existingPerformers = await _sqliteContext.Performers.Where(p => shortNames.Contains(p.ShortName)).ToListAsync();
            var existingPerformerShortNames = existingPerformers.Select(p => p.ShortName).ToList();

            var newPerformers = performers.Where(p => !existingPerformerShortNames.Contains(p.ShortName)).ToList();
            await _sqliteContext.Performers.AddRangeAsync(newPerformers);

            await _sqliteContext.SaveChangesAsync();

            var allPerformers = existingPerformers.Concat(newPerformers).ToList();



            var tags = scene.Tags.Select(p => new SiteTagEntity() { Name = p.Name, ShortName = p.Id, Url = p.Url, SiteId = siteEntity.Id, Site = siteEntity, Scenes = new List<SceneEntity>() }).ToList();
            var tagShortNames = tags.Select(t => t.ShortName).ToList();

            var existingTags = await _sqliteContext.Tags.Where(t => tagShortNames.Contains(t.ShortName)).ToListAsync();
            var existingTagShortNames = existingTags.Select(t => t.ShortName).ToList();

            var newTags = tags.Where(t => !existingTagShortNames.Contains(t.ShortName)).ToList();
            await _sqliteContext.Tags.AddRangeAsync(newTags);

            await _sqliteContext.SaveChangesAsync();

            var allTags = existingTags.Concat(newTags).ToList();



            var sceneEntity = new SceneEntity()
            {
                ReleaseDate = scene.ReleaseDate,
                ShortName = scene.ShortName,
                Name = scene.Name,
                Url = scene.Url,
                Description = scene.Description,
                Duration = scene.Duration,
                Performers = allPerformers,
                Tags = allTags,

                SiteId = siteEntity.Id,
                Site = siteEntity
            };

            await _sqliteContext.Scenes.AddAsync(sceneEntity);
            await _sqliteContext.SaveChangesAsync();

            return sceneEntity.Id;
        }

        public async Task UpdateStorageStateAsync(Site site, string storageState)
        {
            var storageStateEntity = await _sqliteContext.StorageStates.FirstAsync(s => s.SiteId == site.Id);
            storageStateEntity.StorageState = storageState;
            await _sqliteContext.SaveChangesAsync();
        }
    }
}
