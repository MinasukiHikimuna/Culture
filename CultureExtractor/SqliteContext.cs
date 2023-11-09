using System.ComponentModel.DataAnnotations;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;

namespace CultureExtractor;

public class SqliteContext : DbContext, ISqliteContext
{
    public DbSet<SiteEntity> Sites { get; set; }
    public DbSet<SubSiteEntity> SubSites { get; set; }
    public DbSet<ReleaseEntity> Releases { get; set; }
    public DbSet<SitePerformerEntity> Performers { get; set; }
    public DbSet<SiteTagEntity> Tags { get; set; }
    public DbSet<StorageStateEntity> StorageStates { get; set; }
    public DbSet<DownloadEntity> Downloads { get; set; }

    public string DbPath { get; }

    public SqliteContext()
    {
        DbPath = @"I:\Ripping\ripping.db";
    }

    public SqliteContext(IConfiguration configuration)
    {
        var pathsOptions = new PathsOptions();
        configuration.GetSection(PathsOptions.Paths).Bind(pathsOptions);

        DbPath = pathsOptions.DatabasePath;
    }

    // The following configures EF to create a Sqlite database file in the
    // special "local" folder for your platform.
    //
    // Add .LogTo(Log.Debug) to function chain to enable query logging.
    protected override void OnConfiguring(DbContextOptionsBuilder options)
        => options.UseSqlite($"Data Source={DbPath}");
}

public class SiteEntity
{
    [Key]
    public required string Uuid { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }
    public required string Url { get; set; }
    public required string Username { get; set; }
    public required string Password { get; set; }
    public StorageStateEntity? StorageState { get; set; }
}

public class SubSiteEntity
{
    [Key]
    public required string Uuid { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }

    public required string SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
}

public class StorageStateEntity
{
    [Key]
    public required string Uuid { get; set; }
    public required string StorageState { get; set; }

    public required string SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
}

public class SiteTagEntity
{
    [Key]
    public required string Uuid { get; set; }
    public string? ShortName { get; set; }
    public required string Name { get; set; }
    public string? Url { get; set; }

    public required string SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }

    public required ICollection<ReleaseEntity> Releases { get; set; }
}

public class SitePerformerEntity
{
    [Key]
    public required string Uuid { get; set; }
    public string? ShortName { get; set; }
    public required string Name { get; set; }
    public string? Url { get; set; }
    public required string SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }

    public required ICollection<ReleaseEntity> Releases { get; set; }
}

public class ReleaseEntity
{
    [Key]
    public required string Uuid { get; set; }
    public required DateOnly ReleaseDate { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }
    public required string Url { get; set; }
    public required string Description { get; set; }
    public required double Duration { get; set; }
    public required DateTime Created { get; set; }
    public required DateTime LastUpdated { get; set; }
    public required ICollection<SitePerformerEntity> Performers { get; set; }
    public required ICollection<SiteTagEntity> Tags { get; set; }
    public required string AvailableFiles { get; set; }
    public required string JsonDocument { get; set; }

    public required string SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
    public string? SubSiteUuid { get; set; }
    public SubSiteEntity? SubSite { get; set; }

    public required ICollection<DownloadEntity> Downloads { get; set; }
}

public class DownloadEntity
{
    [Key]
    public required string Uuid { get; set; }
    public required DateTime DownloadedAt { get; set; }
    public required string FileType { get; set; }
    public required string ContentType { get; set; }
    public required string Variant { get; set; }
    public required string AvailableFile { get; set; }
    public string? OriginalFilename { get; set; }
    public string? SavedFilename { get; set; }

    public required string ReleaseUuid { get; set; }
    public required ReleaseEntity Release { get; set; }
}
