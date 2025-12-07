using CultureExtractor.Models;

namespace CultureExtractor
{
    public interface IDownloadPlanner
    {
        Task<IReadOnlyList<DownloadEntity>> GetExistingDownloadsAsync(Release release);
        bool NotDownloadedYet(IReadOnlyList<DownloadEntity> existingDownloadEntities, IAvailableFile bestVideo);
        Task<ReleaseDownloadPlan> PlanMissingDownloadsAsync(ReleaseDownloadPlan releaseDownloadPlan);
    }
}