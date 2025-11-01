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
    public DbSet<TargetSystemEntity> TargetSystems { get; set; }
    public DbSet<SiteExternalIdEntity> SiteExternalIds { get; set; }
    public DbSet<SubSiteExternalIdEntity> SubSiteExternalIds { get; set; }
    public DbSet<ReleaseExternalIdEntity> ReleaseExternalIds { get; set; }
    public DbSet<PerformerExternalIdEntity> PerformerExternalIds { get; set; }

    // The following configures EF to create a Sqlite database file in the
    // special "local" folder for your platform.
    //
    // Add .LogTo(Log.Debug) to function chain to enable query logging.
    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
        => optionsBuilder
            .UseNpgsql("Host=localhost;Port=5434;Database=cultureextractor;Username=ce_admin;Password=gTmtNikmpEGf26Fb;") // Include Error Detail=true;")
            .UseSnakeCaseNamingConvention();
    // .LogTo(Log.Debug);

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // Configure TargetSystem unique constraint on Name
        modelBuilder.Entity<TargetSystemEntity>()
            .HasIndex(ts => ts.Name)
            .IsUnique();

        // Configure SiteExternalId
        modelBuilder.Entity<SiteExternalIdEntity>()
            .HasOne(e => e.Site)
            .WithMany(s => s.ExternalIds)
            .HasForeignKey(e => e.SiteUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<SiteExternalIdEntity>()
            .HasOne(e => e.TargetSystem)
            .WithMany()
            .HasForeignKey(e => e.TargetSystemUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<SiteExternalIdEntity>()
            .HasIndex(e => new { e.SiteUuid, e.TargetSystemUuid })
            .IsUnique();

        modelBuilder.Entity<SiteExternalIdEntity>()
            .HasIndex(e => new { e.TargetSystemUuid, e.ExternalId })
            .IsUnique();

        // Configure SubSiteExternalId
        modelBuilder.Entity<SubSiteExternalIdEntity>()
            .HasOne(e => e.SubSite)
            .WithMany(s => s.ExternalIds)
            .HasForeignKey(e => e.SubSiteUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<SubSiteExternalIdEntity>()
            .HasOne(e => e.TargetSystem)
            .WithMany()
            .HasForeignKey(e => e.TargetSystemUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<SubSiteExternalIdEntity>()
            .HasIndex(e => new { e.SubSiteUuid, e.TargetSystemUuid })
            .IsUnique();

        modelBuilder.Entity<SubSiteExternalIdEntity>()
            .HasIndex(e => new { e.TargetSystemUuid, e.ExternalId })
            .IsUnique();

        // Configure ReleaseExternalId
        modelBuilder.Entity<ReleaseExternalIdEntity>()
            .HasOne(e => e.Release)
            .WithMany(r => r.ExternalIds)
            .HasForeignKey(e => e.ReleaseUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<ReleaseExternalIdEntity>()
            .HasOne(e => e.TargetSystem)
            .WithMany()
            .HasForeignKey(e => e.TargetSystemUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<ReleaseExternalIdEntity>()
            .HasIndex(e => new { e.ReleaseUuid, e.TargetSystemUuid })
            .IsUnique();

        modelBuilder.Entity<ReleaseExternalIdEntity>()
            .HasIndex(e => new { e.TargetSystemUuid, e.ExternalId })
            .IsUnique();

        // Configure PerformerExternalId
        modelBuilder.Entity<PerformerExternalIdEntity>()
            .HasOne(e => e.Performer)
            .WithMany(p => p.ExternalIds)
            .HasForeignKey(e => e.PerformerUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<PerformerExternalIdEntity>()
            .HasOne(e => e.TargetSystem)
            .WithMany()
            .HasForeignKey(e => e.TargetSystemUuid)
            .OnDelete(DeleteBehavior.Cascade);

        modelBuilder.Entity<PerformerExternalIdEntity>()
            .HasIndex(e => new { e.PerformerUuid, e.TargetSystemUuid })
            .IsUnique();

        modelBuilder.Entity<PerformerExternalIdEntity>()
            .HasIndex(e => new { e.TargetSystemUuid, e.ExternalId })
            .IsUnique();
    }
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
    public ICollection<SiteExternalIdEntity>? ExternalIds { get; set; }
}

public class SubSiteEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required string ShortName { get; set; }
    public required string Name { get; set; }
    [Column(TypeName = "json")]
    public required string JsonDocument { get; set; }

    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
    public ICollection<SubSiteExternalIdEntity>? ExternalIds { get; set; }
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
    public ICollection<PerformerExternalIdEntity>? ExternalIds { get; set; }
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
    [Column(TypeName = "json")]
    public required string AvailableFiles { get; set; }
    [Column(TypeName = "json")]
    public required string JsonDocument { get; set; }

    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }
    public Guid? SubSiteUuid { get; set; }
    public SubSiteEntity? SubSite { get; set; }

    public required ICollection<DownloadEntity> Downloads { get; set; }
    public ICollection<ReleaseExternalIdEntity>? ExternalIds { get; set; }
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
    [Column(TypeName = "json")]
    public required string AvailableFile { get; set; }
    [Column(TypeName = "json")]
    public required string FileMetadata { get; set; }
    public string? OriginalFilename { get; set; }
    public string? SavedFilename { get; set; }

    public required Guid ReleaseUuid { get; set; }
    public required ReleaseEntity Release { get; set; }
}

public class TargetSystemEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required string Name { get; set; }
    public string? Description { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime Created { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime LastUpdated { get; set; }
}

public class SiteExternalIdEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required string ExternalId { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime Created { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime LastUpdated { get; set; }

    public required Guid SiteUuid { get; set; }
    public required SiteEntity Site { get; set; }

    public required Guid TargetSystemUuid { get; set; }
    public required TargetSystemEntity TargetSystem { get; set; }
}

public class SubSiteExternalIdEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required string ExternalId { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime Created { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime LastUpdated { get; set; }

    public required Guid SubSiteUuid { get; set; }
    public required SubSiteEntity SubSite { get; set; }

    public required Guid TargetSystemUuid { get; set; }
    public required TargetSystemEntity TargetSystem { get; set; }
}

public class ReleaseExternalIdEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required string ExternalId { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime Created { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime LastUpdated { get; set; }

    public required Guid ReleaseUuid { get; set; }
    public required ReleaseEntity Release { get; set; }

    public required Guid TargetSystemUuid { get; set; }
    public required TargetSystemEntity TargetSystem { get; set; }
}

public class PerformerExternalIdEntity
{
    [Key]
    public required Guid Uuid { get; set; }
    public required string ExternalId { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime Created { get; set; }
    [Column(TypeName = "timestamp")]
    public required DateTime LastUpdated { get; set; }

    public required Guid PerformerUuid { get; set; }
    public required SitePerformerEntity Performer { get; set; }

    public required Guid TargetSystemUuid { get; set; }
    public required TargetSystemEntity TargetSystem { get; set; }
}
