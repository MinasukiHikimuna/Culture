namespace CultureExtractor
{
    public interface IRepository
    {
        Task<Gallery?> GetGalleryAsync(string siteShortName, string galleryShortScene);
        Task<Scene?> GetSceneAsync(string siteShortName, string sceneShortName);
        Task<IEnumerable<Scene>> GetScenesAsync();
        Task<Site> GetSiteAsync(string shortName);
        Task<IEnumerable<Site>> GetSitesAsync();
        Task<IEnumerable<Scene>> QueryScenesAsync(Site site, DownloadConditions downloadConditions);
        Task SaveDownloadAsync(Download download, PreferredDownloadQuality preferredDownloadQuality);
        Task<Gallery> SaveGalleryAsync(Gallery gallery);
        Task UpdateStorageStateAsync(Site site, string storageState);
        Task<Scene> UpsertScene(Scene scene);
    }
}