using Microsoft.EntityFrameworkCore;
using Serilog;
using System.Text.Json;
using System.Text.Json.Serialization;
using CultureExtractor.Interfaces;
using CultureExtractor.Models;

namespace CultureExtractor;

public class Repository : IRepository
{
    private readonly Interfaces.ICultureExtractorContext _cultureExtractorContext;

    public Repository(Interfaces.ICultureExtractorContext cultureExtractorContext)
    {
        _cultureExtractorContext = cultureExtractorContext;
    }

    public async Task<IEnumerable<Site>> GetSitesAsync()
    {
        var siteEntities = await _cultureExtractorContext.Sites
            .Include(s => s.StorageState)
            .OrderBy(s => s.Name)
            .ToListAsync();

        return siteEntities.Select(Convert).AsEnumerable();
    }

    public async Task<IEnumerable<SubSite?>> GetSubSitesAsync(Guid siteUuid)
    {
        var subSites = await _cultureExtractorContext.SubSites
            .Where(s => s.SiteUuid == siteUuid)
            .OrderBy(s => s.Name)
            .ToListAsync();

        return subSites.Select(Convert).AsEnumerable();
    }
    
    public async Task<Site> GetSiteAsync(string shortName)
    {
        var siteEntity = await _cultureExtractorContext.Sites
            .Include(s => s.StorageState)
            .FirstAsync(site => site.ShortName == shortName);

        return Convert(siteEntity);
    }

    public async Task<IEnumerable<Release>> GetReleasesAsync()
    {
        var siteEntities = await _cultureExtractorContext.Releases
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .OrderBy(s => s.Site.Name)
            .ThenByDescending(s => s.ReleaseDate)
            .ToListAsync();

        return siteEntities.Select(Convert).AsEnumerable();
    }

    public async Task<IEnumerable<Release>> QueryReleasesAsync(Site site, DownloadConditions downloadConditions)
    {
        var siteEntities = await _cultureExtractorContext.Releases
            .Include(s => s.Site)
            .Include(s => s.SubSite)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Where(s => s.SiteUuid == site.Uuid)
            .Where(s => !downloadConditions.DownloadedFileNames.Any() || s.Downloads.Any(d => downloadConditions.DownloadedFileNames.Contains(d.SavedFilename)))
            .Where(s => !s.Downloads.Any(d => d.Variant == Enum.GetName(downloadConditions.PreferredDownloadQuality)))
            .OrderBy(s => s.Site.Name)
            .ThenByDescending(s => s.ReleaseDate)
            .ToListAsync();

        return siteEntities.Select(Convert).AsEnumerable();
    }

    public async Task<Release?> GetReleaseAsync(string siteShortName, string releaseShortName)
    {
        var releaseEntity = await _cultureExtractorContext.Releases
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .FirstOrDefaultAsync(s => s.Site.ShortName == siteShortName && s.ShortName == releaseShortName);

        return releaseEntity != null
            ? Convert(releaseEntity)
            : null;
    }

    public async Task<IReadOnlyList<Release>> GetReleasesAsync(string siteShortName, IList<string> releaseShortNames)
    {
        var releaseEntities = await _cultureExtractorContext.Releases
            .Include(s => s.Site)
            .Include(s => s.Performers)
            .Include(s => s.Tags)
            .Where(s => s.Site.ShortName == siteShortName && releaseShortNames.Contains(s.ShortName))
            .ToListAsync();

        return releaseEntities
            .Select(Convert)
            .ToList()
            .AsReadOnly();
    }

    public async Task<SubSite> UpsertSubSite(SubSite subSite)
    {
        var existingSubSiteEntity = await _cultureExtractorContext.SubSites
            .Include(s => s.Site)
            .FirstOrDefaultAsync(s =>
                s.Site.ShortName == subSite.Site.ShortName &&
                s.ShortName == subSite.ShortName);

        if (existingSubSiteEntity != null)
        {
            if (existingSubSiteEntity.Name != subSite.Name)
            {
                existingSubSiteEntity.Name = subSite.Name;
                await _cultureExtractorContext.SaveChangesAsync();
            }

            return Convert(existingSubSiteEntity);
        }

        var siteEntity = await _cultureExtractorContext.Sites.FirstAsync(s => s.Uuid == subSite.Site.Uuid);
        var subSiteEntity = new SubSiteEntity()
        {
            Uuid = UuidGenerator.Generate(),
            ShortName = subSite.ShortName,
            Name = subSite.Name,
            SiteUuid = siteEntity.Uuid,
            Site = siteEntity
        };

        await _cultureExtractorContext.SubSites.AddAsync(subSiteEntity);
        await _cultureExtractorContext.SaveChangesAsync();

        return Convert(subSiteEntity);
    }

    public async Task<Release> UpsertRelease(Release release)
    {
        var siteEntity = await _cultureExtractorContext.Sites.FirstAsync(s => s.Uuid == release.Site.Uuid);
        SubSiteEntity subSiteEntity = null;
        if (release.SubSite != null)
        {
            subSiteEntity = await _cultureExtractorContext.SubSites.FirstOrDefaultAsync(s => s.SiteUuid == release.Site.Uuid && s.ShortName == release.SubSite.ShortName);
            if (subSiteEntity == null)
            {
                subSiteEntity = new SubSiteEntity()
                {
                    Uuid = UuidGenerator.Generate(),
                    ShortName = release.SubSite.ShortName,
                    Name = release.SubSite.Name,
                    SiteUuid = siteEntity.Uuid,
                    Site = siteEntity
                };
                _cultureExtractorContext.SubSites.Add(subSiteEntity);
                await _cultureExtractorContext.SaveChangesAsync();
            }
        }

        List<SitePerformerEntity> performerEntities = await GetOrCreatePerformersAsync(release.Performers, siteEntity);
        List<SiteTagEntity> tagEntities = await GetOrCreateTagsAsync(release.Tags, siteEntity);

        var existingReleaseEntity = await _cultureExtractorContext.Releases.FirstOrDefaultAsync(s => s.Uuid == release.Uuid);
        
        if (existingReleaseEntity == null)
        {
            var releaseEntity = new ReleaseEntity()
            {
                Uuid = release.Uuid,
                ReleaseDate = release.ReleaseDate,
                ShortName = release.ShortName,
                Name = release.Name,
                Url = release.Url,
                Description = release.Description,
                Duration = release.Duration,
                Performers = performerEntities,
                Tags = tagEntities,
                Created = DateTime.Now,
                LastUpdated = DateTime.Now,

                SiteUuid = siteEntity.Uuid,
                Site = siteEntity,
                SubSiteUuid = subSiteEntity?.Uuid,
                SubSite = subSiteEntity,

                JsonDocument = release.JsonDocument,

                Downloads = new List<DownloadEntity>(),
                AvailableFiles = JsonSerializer.Serialize(release.AvailableFiles)
            };
            await _cultureExtractorContext.Releases.AddAsync(releaseEntity);
            await _cultureExtractorContext.SaveChangesAsync();

            return Convert(releaseEntity);
        }

        existingReleaseEntity.ReleaseDate = release.ReleaseDate;
        existingReleaseEntity.ShortName = release.ShortName;
        existingReleaseEntity.Name = release.Name;
        existingReleaseEntity.Url = release.Url;
        existingReleaseEntity.Description = release.Description;
        existingReleaseEntity.Duration = release.Duration;
        existingReleaseEntity.Performers = performerEntities;
        existingReleaseEntity.Tags = tagEntities;
        existingReleaseEntity.JsonDocument = release.JsonDocument;

        if (existingReleaseEntity.Created == DateTime.MinValue)
        {
            existingReleaseEntity.Created = DateTime.Now;
        }
        existingReleaseEntity.LastUpdated = DateTime.Now;

        existingReleaseEntity.SiteUuid = siteEntity.Uuid;
        existingReleaseEntity.Site = siteEntity;

        existingReleaseEntity.AvailableFiles = JsonSerializer.Serialize(release.AvailableFiles);

        await _cultureExtractorContext.SaveChangesAsync();

        return Convert(existingReleaseEntity);
    }

    private async Task<List<SitePerformerEntity>> GetOrCreatePerformersAsync(IEnumerable<SitePerformer> performers, SiteEntity siteEntity)
    {
        var shortNames = performers.Select(p => p.ShortName).ToList();
        
        var existingPerformers = await _cultureExtractorContext.Performers.Where(p => p.SiteUuid == siteEntity.Uuid && shortNames.Contains(p.ShortName)).ToListAsync();
        var existingPerformerShortNames = existingPerformers.Select(p => p.ShortName).ToList();
        
        var newPerformersEntities = performers
            .Where(p => !existingPerformerShortNames.Contains(p.ShortName))
            .Select(p => new SitePerformerEntity
            {
                Uuid = UuidGenerator.Generate(),
                Name = p.Name,
                ShortName = p.ShortName,
                Url = p.Url,
                SiteUuid = siteEntity.Uuid,
                Site = siteEntity,
                Releases = new List<ReleaseEntity>()
            }).ToList();

        if (newPerformersEntities.Any())
        {
            await _cultureExtractorContext.Performers.AddRangeAsync(newPerformersEntities);
            await _cultureExtractorContext.SaveChangesAsync();            
        }

        return existingPerformers.Concat(newPerformersEntities).ToList();
    }

    private async Task<List<SiteTagEntity>> GetOrCreateTagsAsync(IEnumerable<SiteTag> tags, SiteEntity siteEntity)
    {
        var tagShortNames = tags.Select(t => t.Id).ToList();
        
        var existingTags = await _cultureExtractorContext.Tags.Where(t => t.SiteUuid == siteEntity.Uuid && tagShortNames.Contains(t.ShortName)).ToListAsync();
        var existingTagShortNames = existingTags.Select(t => t.ShortName).ToList();
        
        var newTagEntities = tags
            .Where(t => !existingTagShortNames.Contains(t.Id))
            .Select(t => new SiteTagEntity
            {
                Uuid = UuidGenerator.Generate(),
                Name = t.Name,
                ShortName = t.Id,
                Url = t.Url,
                SiteUuid = siteEntity.Uuid,
                Site = siteEntity,
                Releases = new List<ReleaseEntity>()
            }).ToList();

        if (newTagEntities.Any())
        {
            await _cultureExtractorContext.Tags.AddRangeAsync(newTagEntities);
            await _cultureExtractorContext.SaveChangesAsync();            
        }

        return existingTags.Concat(newTagEntities).ToList();
    }

    public async Task UpdateStorageStateAsync(Site site, string storageState)
    {
        var storageStateEntity = await _cultureExtractorContext.StorageStates.FirstOrDefaultAsync(s => s.SiteUuid == site.Uuid);
        if (storageStateEntity != null)
        {
            storageStateEntity.StorageState = storageState;
        }
        else
        {
            var siteEntity = await _cultureExtractorContext.Sites.FirstAsync(s => s.Uuid == site.Uuid);
            _cultureExtractorContext.StorageStates.Add(new StorageStateEntity()
            {
                Uuid = UuidGenerator.Generate(),
                StorageState = storageState,

                SiteUuid = siteEntity.Uuid,
                Site = siteEntity
            });
        }

        await _cultureExtractorContext.SaveChangesAsync();
        Log.Information($"Updated storage state for {site.Name}.");
    }

    private static Site Convert(SiteEntity siteEntity)
    {
        return new Site(
            siteEntity.Uuid,
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
                subSiteEntity.Uuid,
                subSiteEntity.ShortName,
                subSiteEntity.Name,
                Convert(subSiteEntity.Site)
              )
            : null;
    }

    private static Release Convert(ReleaseEntity releaseEntity)
    {
        var availableFilesJson = string.IsNullOrEmpty(releaseEntity.AvailableFiles)
            ? "[]"
            : releaseEntity.AvailableFiles;
        var availableFiles = JsonSerializer.Deserialize<List<IAvailableFile>>(availableFilesJson).AsReadOnly();
        
        return new Release(
            releaseEntity.Uuid,
            Convert(releaseEntity.Site),
            Convert(releaseEntity.SubSite),
            releaseEntity.ReleaseDate,
            releaseEntity.ShortName,
            releaseEntity.Name,
            releaseEntity.Url,
            releaseEntity.Description,
            releaseEntity.Duration,
            releaseEntity.Performers.Select(Convert),
            releaseEntity.Tags.Select(Convert),
            availableFiles,
            releaseEntity.JsonDocument,
            releaseEntity.LastUpdated);
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
        var releaseEntity = await _cultureExtractorContext.Releases.FirstAsync(s => s.Uuid == download.Release.Uuid);

        var json = JsonSerializer.Serialize(new JsonSummary(download.AvailableFile, download.FileMetadata));

        _cultureExtractorContext.Downloads.Add(new DownloadEntity
        {
            Uuid = UuidGenerator.Generate(),
            DownloadedAt = DateTime.Now,
            AvailableFile = json,
            
            FileType = download.AvailableFile.FileType,
            ContentType = download.AvailableFile.ContentType,
            Variant = download.AvailableFile.Variant, // Enum.GetName(preferredDownloadQuality),
            OriginalFilename = download.OriginalFilename,
            SavedFilename = download.SavedFilename,

            ReleaseUuid = releaseEntity.Uuid,
            Release = releaseEntity,
        });
        await _cultureExtractorContext.SaveChangesAsync();
    }

    private record JsonSummary(IAvailableFile AvailableFile, IFileMetadata FileMetadata);
}
