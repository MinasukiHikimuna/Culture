using System.Text.RegularExpressions;
using CultureExtractor.Models;

namespace CultureExtractor
{
    public static class SceneNamer
    {
        public static string Name(Scene scene, string suffix, string performers = "")
        {
            var performersStr = !string.IsNullOrEmpty(performers)
                ? performers
                : FormatPerformers(scene);

            var subSiteName = scene.SubSite != null ? " - " + scene.SubSite.Name : "";

            var nameWithoutSuffix =
                string.Concat(
                    Regex.Replace(
                        $"{performersStr} - {scene.Site.Name}{subSiteName} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.ShortName} - {scene.Name}",
                        @"\s+",
                        " "
                    ).Split(Path.GetInvalidFileNameChars()));

            var name = (nameWithoutSuffix + suffix).Length > 244
                ? nameWithoutSuffix[..(244 - suffix.Length - "...".Length)] + "..." + suffix
                : nameWithoutSuffix + suffix;

            return name;
        }

        private static string FormatPerformers(Scene scene)
        {
            var performerNames = scene.Performers.Select(p => p.Name).ToList();
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
