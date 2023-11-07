using Microsoft.EntityFrameworkCore;

namespace CultureExtractor.Interfaces;

public interface ISqliteContext
{
    string DbPath { get; }
    DbSet<DownloadEntity> Downloads { get; set; }
    DbSet<SitePerformerEntity> Performers { get; set; }
    DbSet<ReleaseEntity> Releases { get; set; }
    DbSet<SiteEntity> Sites { get; set; }
    DbSet<SubSiteEntity> SubSites { get; set; }
    DbSet<StorageStateEntity> StorageStates { get; set; }
    DbSet<SiteTagEntity> Tags { get; set; }
    Task<int> SaveChangesAsync(CancellationToken cancellationToken = default);
}