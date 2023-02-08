using System.Text.RegularExpressions;

namespace CultureExtractor
{
    public static class SceneNamer
    {
        public static string Name(Scene scene, string suffix)
        {
            var performerNames = scene.Performers.Select(p => p.Name).ToList();
            var performersStr = performerNames.Count() > 1
                ? string.Join(", ", performerNames.SkipLast(1)) + " & " + performerNames.Last()
                : performerNames.FirstOrDefault();

            if (string.IsNullOrWhiteSpace(performersStr))
            {
                performersStr = "Unknown";
            }

            var nameWithoutSuffix =
                string.Concat(
                    Regex.Replace(
                        $"{performersStr} - {scene.Site.Name} - {scene.ReleaseDate.ToString("yyyy-MM-dd")} - {scene.Name}",
                        @"\s+",
                        " "
                    ).Split(Path.GetInvalidFileNameChars()));

            var name = (nameWithoutSuffix + suffix).Length > 244
                ? nameWithoutSuffix[..(244 - suffix.Length - "...".Length)] + "..." + suffix
                : nameWithoutSuffix + suffix;

            return name;
        }
    }
}
