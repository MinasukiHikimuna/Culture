using CultureExtractor.Interfaces;
using CultureExtractor.Models;
using Microsoft.EntityFrameworkCore;
using System.Collections.Immutable;

namespace CultureExtractor
{
    public class DownloadPlanner : IDownloadPlanner
    {
        private readonly ICultureExtractorContext _context;

        public DownloadPlanner(ICultureExtractorContext context)
        {
            _context = context;
        }

        public async Task<IReadOnlyList<DownloadEntity>> GetExistingDownloadsAsync(Release release)
        {
            var existingDownloads = await _context.Downloads.Where(d => d.ReleaseUuid == release.Uuid).ToListAsync();
            return existingDownloads.ToImmutableList();
        }

        public bool NotDownloadedYet(IReadOnlyList<DownloadEntity> existingDownloadEntities, IAvailableFile bestVideo)
        {
            return !existingDownloadEntities.Any(d => d.FileType == bestVideo.FileType && d.ContentType == bestVideo.ContentType && d.Variant == bestVideo.Variant);
        }

        public async Task<ReleaseDownloadPlan> PlanMissingDownloadsAsync(ReleaseDownloadPlan releaseDownloadPlan)
        {
            var existingDownloads = await GetExistingDownloadsAsync(releaseDownloadPlan.Release);
            var notYetDownloaded = releaseDownloadPlan.AvailableFiles
                .Where(f => !existingDownloads.Any(d =>
                    d.FileType == f.FileType && d.ContentType == f.ContentType && d.Variant == f.Variant))
                .ToImmutableList();

            return releaseDownloadPlan with { AvailableFiles = notYetDownloaded };
        }
    }
}
