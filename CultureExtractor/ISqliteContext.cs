using Microsoft.EntityFrameworkCore;

namespace CultureExtractor
{
    public interface ISqliteContext
    {
        string DbPath { get; }
        DbSet<DownloadEntity> Downloads { get; set; }
        DbSet<GalleryEntity> Galleries { get; set; }
        DbSet<SitePerformerEntity> Performers { get; set; }
        DbSet<SceneEntity> Scenes { get; set; }
        DbSet<SiteEntity> Sites { get; set; }
        DbSet<StorageStateEntity> StorageStates { get; set; }
        DbSet<SiteTagEntity> Tags { get; set; }
        Task<int> SaveChangesAsync(CancellationToken cancellationToken = default);
    }
}