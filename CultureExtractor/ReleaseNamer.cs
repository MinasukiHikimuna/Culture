using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor
{
    public static class ReleaseNamer
    {
        public static string Name(Release release, string suffix, string performers = "")
        {
            var performersStr = !string.IsNullOrEmpty(performers)
                ? performers
                : FormatPerformers(release);

            var subSiteName = release.SubSite != null ? " - " + release.SubSite.Name : "";

            var nameWithoutSuffix =
                string.Concat(
                    Regex.Replace(
                        $"{performersStr} - {release.Site.Name}{subSiteName} - {release.ReleaseDate.ToString("yyyy-MM-dd")} - {release.ShortName} - {release.Name}",
                        @"\s+",
                        " "
                    ).Split(Path.GetInvalidFileNameChars()));

            var name = (nameWithoutSuffix + suffix).Length > 244
                ? nameWithoutSuffix[..(244 - suffix.Length - "...".Length)] + "..." + suffix
                : nameWithoutSuffix + suffix;

            return name;
        }

        private static string FormatPerformers(Release release)
        {
            var performerNames = release.Performers.Select(p => p.Name).ToList();
            var performersStr = performerNames.Count > 1
                ? string.Join(", ", performerNames.SkipLast(1)) + " & " + performerNames.Last()
                : performerNames.FirstOrDefault();

            if (string.IsNullOrWhiteSpace(performersStr))
            {
                performersStr = "Unknown";
            }

            return performersStr;
        }
    }
}
