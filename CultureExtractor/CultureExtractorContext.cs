using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Serilog;

namespace CultureExtractor;

public class CultureExtractorContext : DbContext, ICultureExtractorContext
{
    public DbSet<SiteEntity> Sites { get; set; }
    public DbSet<SubSiteEntity> SubSites { get; set; }
    public DbSet<ReleaseEntity> Releases { get; set; }
    public DbSet<SitePerformerEntity> Performers { get; set; }
    public DbSet<SiteTagEntity> Tags { get; set; }
    public DbSet<StorageStateEntity> StorageStates { get; set; }
    public DbSet<DownloadEntity> Downloads { get; set; }

    // The following configures EF to create a Sqlite database file in the
    // special "local" folder for your platform.
    //
    // Add .LogTo(Log.Debug) to function chain to enable query logging.
    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
        => optionsBuilder
            .UseNpgsql("Host=localhost;Port=5434;Database=cultureextractor;Username=ce_admin;Password=gTmtNikmpEGf26Fb;")
            .UseSnakeCaseNamingConvention()
            .LogTo(Log.Debug);
}

public class SiteEntity
{
    [Key]
    public required Guid Uuid { get; set; }
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
    public required Guid Uuid { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }

    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
}

public class StorageStateEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required string StorageState { get; set; }

    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
}

public class SiteTagEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public string? ShortName { get; set; }
    public required string Name { get; set; }
    public string? Url { get; set; }

    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }

    public required ICollection<ReleaseEntity> Releases { get; set; }
}

public class SitePerformerEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public string? ShortName { get; set; }
    public required string Name { get; set; }
    public string? Url { get; set; }
    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }

    public required ICollection<ReleaseEntity> Releases { get; set; }
}

public class ReleaseEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required DateOnly ReleaseDate { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }
    public required string Url { get; set; }
    public required string Description { get; set; }
    public required double Duration { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime Created { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime LastUpdated { get; set; }
    public required ICollection<SitePerformerEntity> Performers { get; set; }
    public required ICollection<SiteTagEntity> Tags { get; set; }
    public required string AvailableFiles { get; set; }
    public required string JsonDocument { get; set; }

    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
    public Guid? SubSiteUuid { get; set; }
    public SubSiteEntity? SubSite { get; set; }

    public required ICollection<DownloadEntity> Downloads { get; set; }
}

public class DownloadEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime DownloadedAt { get; set; }
    public required string FileType { get; set; }
    public required string ContentType { get; set; }
    public required string Variant { get; set; }
    public required string AvailableFile { get; set; }
    public string? OriginalFilename { get; set; }
    public string? SavedFilename { get; set; }

    public required Guid ReleaseUuid { get; set; }
    public required ReleaseEntity Release { get; set; }
}
