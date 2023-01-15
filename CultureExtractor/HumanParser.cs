using System.Globalization;
using System.Text.RegularExpressions;

namespace CultureExtractor;

public static class HumanParser
{
    public static double ParseFileSize(string sizeString)
    {
        string pattern = @"(?<wholeNumbers>[0-9]+)(?<decimalNumbers>(.|,)[0-9]+)? (?<unit>GB|MB)";
        Match match = Regex.Match(sizeString, pattern);
        if (match.Success)
        {
            var wholeNumbers = int.Parse(match.Groups["wholeNumbers"].Value);
            var decimalNumbers =
                !string.IsNullOrEmpty(match.Groups["decimalNumbers"].Value)
                    ? double.Parse("0." + match.Groups["decimalNumbers"].Value[1..], CultureInfo.InvariantCulture)
                    : 0.0;
            var unitFactor = GetUnitFactor(match.Groups["unit"].Value);
            return (wholeNumbers + decimalNumbers) * unitFactor;
        }

        return 0;
    }

    public static int ParseResolutionWidth(string resolutionString)
    {
        if (new List<string>() { "4K", "2160", "2160P", "UHD" }.Any(s => resolutionString.Contains(s, StringComparison.InvariantCultureIgnoreCase))) {
            return 2160;
        }

        if (new List<string>() { "1080", "1080P", "Full HD" }.Any(s => resolutionString.Contains(s, StringComparison.InvariantCultureIgnoreCase)))
        {
            return 1080;
        }

        string pattern = @"(?<width>[0-9]+)p";
        Match match = Regex.Match(resolutionString, pattern);
        if (match.Success)
        {
            return int.Parse(match.Groups["width"].Value);
        }

        return -1;
    }

    private static int GetUnitFactor(string unit)
    {
        return unit switch
        {
            "GB" => 1024 * 1024 * 1024,
            "MB" => 1024 * 1024,
            _ => throw new ArgumentException($"Unknown unit {unit}")
        };
    }
}
