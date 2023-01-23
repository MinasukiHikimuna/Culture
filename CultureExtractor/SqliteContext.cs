using Microsoft.EntityFrameworkCore;

namespace CultureExtractor;

public class SqliteContext : DbContext
{
    public DbSet<SiteEntity> Sites { get; set; }
    public DbSet<SceneEntity> Scenes { get; set; }
    public DbSet<GalleryEntity> Galleries { get; set; }
    public DbSet<SitePerformerEntity> Performers { get; set; }
    public DbSet<SiteTagEntity> Tags { get; set; }
    public DbSet<StorageStateEntity> StorageStates { get; set; }
    public DbSet<DownloadEntity> Downloads { get; set; }
    public DbSet<DownloadOptionEntity> DownloadOptions { get; set; }

    public string DbPath { get; }

    public SqliteContext()
    {
        DbPath = @"B:\Ripping\ripping.db";
    }

    // The following configures EF to create a Sqlite database file in the
    // special "local" folder for your platform.
    protected override void OnConfiguring(DbContextOptionsBuilder options)
        => options.UseSqlite($"Data Source={DbPath}");
}

public class SiteEntity
{
    public int Id { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }
    public required string Url { get; set; }
    public required string Username { get; set; }
    public required string Password { get; set; }
    public StorageStateEntity? StorageState { get; set; }
}

public class StorageStateEntity
{
    public int Id { get; set; }
    public required string StorageState { get; set; }

    public required int SiteId { get; set; }
    public required SiteEntity Site { get; set; }
}

public class SiteTagEntity
{
    public int Id { get; set; }
    public string? ShortName { get; set; }
    public required string Name { get; set; }
    public string? Url { get; set; }

    public required int SiteId { get; set; }
    public required SiteEntity Site { get; set; }

    public required ICollection<SceneEntity> Scenes { get; set; }
}

public class SitePerformerEntity
{
    public int Id { get; set; }
    public string? ShortName { get; set; }
    public required string Name { get; set; }
    public string? Url { get; set; }
    public required int SiteId { get; set; }
    public required SiteEntity Site { get; set; }

    public required ICollection<SceneEntity> Scenes { get; set; }
}

public class SceneEntity
{
    public int Id { get; set; }
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
    public required ICollection<DownloadOptionEntity> DownloadOptions { get; set; }

    public required int SiteId { get; set; }
    public required SiteEntity Site { get; set; }

    public required ICollection<DownloadEntity> Downloads { get; set; }
}

public class GalleryEntity
{
    public int Id { get; set; }
    public required DateOnly ReleaseDate { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }
    public required string Url { get; set; }
    public required string Description { get; set; }
    public required int Pictures { get; set; }
    public required ICollection<SitePerformerEntity> Performers { get; set; }
    public required ICollection<SiteTagEntity> Tags { get; set; }

    public required int SiteId { get; set; }
    public required SiteEntity Site { get; set; }
}

public class DownloadEntity
{
    public int Id { get; set; }
    public required DateTime DownloadedAt { get; set; }
    public required string DownloadQuality { get; set; }
    public required string DownloadOptions { get; set; }
    public string? OriginalFilename { get; set; }
    public string? SavedFilename { get; set; }

    public required int SceneId { get; set; }
    public required SceneEntity Scene { get; set; }
}

public class DownloadOptionEntity
{
    public int Id { get; set; }
    public required string Description { get; set; }
    public required string Url { get; set; }
    public int? ResolutionWidth { get; set; }
    public int? ResolutionHeight { get; set; }
    public double? FileSize { get; set; }
    public double? Fps { get; set; }
    public string? Codec { get; set; }
}
