using System.Globalization;
using System.Text.RegularExpressions;

namespace CultureExtractor;

public static class HumanParser
{
    public static double ParseFileSize(string sizeString)
    {
        sizeString = sizeString.Replace(" ", "");

        string purgatoryPattern = @"(?<thousands>[0-9]+),(?<wholeNumbers>[0-9]+).(?<decimalNumbers>[0-9]+)?(?<unit>GB|MB)";
        Match purgatoryMatch = Regex.Match(sizeString, purgatoryPattern);
        if (purgatoryMatch.Success)
        {
            var thousands = int.Parse(purgatoryMatch.Groups["thousands"].Value);
            var wholeNumbers = int.Parse(purgatoryMatch.Groups["wholeNumbers"].Value);
            var decimalNumbers =
                !string.IsNullOrEmpty(purgatoryMatch.Groups["decimalNumbers"].Value)
                    ? double.Parse("0." + purgatoryMatch.Groups["decimalNumbers"].Value, CultureInfo.InvariantCulture)
                    : 0.0;
            var unitFactor = GetUnitFactor(purgatoryMatch.Groups["unit"].Value);
            return (thousands * 1000 + wholeNumbers + decimalNumbers) * unitFactor;
        }

        string pattern = @"(?<wholeNumbers>[0-9]+)(?<decimalNumbers>(.|,)[0-9]+)?(?<unit>GB|MB)";
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
        var trimmedResolutionString = resolutionString.Trim().Replace(" ", "");

        var patternWithinOtherTextResolution = @"^(?<width>[0-9]+)x(?<height>[0-9]+)$";
        var matchWithinOtherTextResolution = Regex.Match(trimmedResolutionString, patternWithinOtherTextResolution);
        if (matchWithinOtherTextResolution.Success)
        {
            return int.Parse(matchWithinOtherTextResolution.Groups["width"].Value);
        }

        return -1;
    }

    public static int ParseResolutionHeight(string resolutionString)
    {
        var trimmedResolutionString = resolutionString.Trim();

        var patternWithinOtherTextResolution = @"(?<width>[0-9]+)x(?<height>[0-9]+)";
        var matchWithinOtherTextResolution = Regex.Match(trimmedResolutionString, patternWithinOtherTextResolution);
        if (matchWithinOtherTextResolution.Success)
        {
            return int.Parse(matchWithinOtherTextResolution.Groups["height"].Value);
        }

        if (new List<string>() { "4K", "2160", "2160P", "UHD" }.Any(s => resolutionString.Contains(s, StringComparison.InvariantCultureIgnoreCase))) {
            return 2160;
        }

        if (new List<string>() { "1080", "1080P", "Full HD" }.Any(s => resolutionString.Contains(s, StringComparison.InvariantCultureIgnoreCase)))
        {
            return 1080;
        }

        string pattern = @"(?<height>[0-9]+)p";
        Match match = Regex.Match(resolutionString, pattern);
        if (match.Success)
        {
            return int.Parse(match.Groups["height"].Value);
        }

        return -1;
    }

    public static TimeSpan ParseDuration(string durationString)
    {
        var trimmedDurationString = durationString.Trim();

        var patternHhHMm = @"^(?<hours>[0-9]+)h (?<minutes>[0-9]+)";
        var matchHhHMm = Regex.Match(trimmedDurationString, patternHhHMm);
        if (matchHhHMm.Success)
        {
            return TimeSpan.Zero
                .Add(TimeSpan.FromHours(int.Parse(matchHhHMm.Groups["hours"].Value)))
                .Add(TimeSpan.FromMinutes(int.Parse(matchHhHMm.Groups["minutes"].Value)));
        }

        var patternHhH = @"^(?<hours>[0-9]+)h";
        var matchHhH = Regex.Match(trimmedDurationString, patternHhH);
        if (matchHhH.Success)
        {
            return TimeSpan.Zero
                .Add(TimeSpan.FromHours(int.Parse(matchHhH.Groups["hours"].Value)));
        }

        var patternMmMSs = @"^(?<minutes>[0-9]+)m(?<seconds>[0-9]+)";
        var matchMmMSs = Regex.Match(trimmedDurationString, patternMmMSs);
        if (matchMmMSs.Success)
        {
            return TimeSpan.Zero
                .Add(TimeSpan.FromMinutes(int.Parse(matchMmMSs.Groups["minutes"].Value)))
                .Add(TimeSpan.FromSeconds(int.Parse(matchMmMSs.Groups["seconds"].Value)));
        }

        var patternHhMmSs = @"^(?<hours>[0-9]+):(?<minutes>[0-9]+):(?<seconds>[0-9]+)$";
        var matchHhMmSs = Regex.Match(trimmedDurationString, patternHhMmSs);
        if (matchHhMmSs.Success)
        {
            return TimeSpan.Zero
                .Add(TimeSpan.FromHours(int.Parse(matchHhMmSs.Groups["hours"].Value)))
                .Add(TimeSpan.FromMinutes(int.Parse(matchHhMmSs.Groups["minutes"].Value)))
                .Add(TimeSpan.FromSeconds(int.Parse(matchHhMmSs.Groups["seconds"].Value)));
        }

        var patternMmSs = @"^(?<minutes>[0-9]+):(?<seconds>[0-9]+)$";
        var matchMmSs = Regex.Match(trimmedDurationString, patternMmSs);
        if (matchMmSs.Success)
        {
            return TimeSpan.Zero
                .Add(TimeSpan.FromMinutes(int.Parse(matchMmSs.Groups["minutes"].Value)))
                .Add(TimeSpan.FromSeconds(int.Parse(matchMmSs.Groups["seconds"].Value)));
        }

        return TimeSpan.Zero;
    }

    public static string ParseCodec(string codecString)
    {
        var upperCodecString = codecString.ToUpper();

        if (upperCodecString.ToUpper().Contains("H264") || upperCodecString.Contains("H.264"))
        {
            return "H.264";
        }

        if (upperCodecString.ToUpper().Contains("H265") || upperCodecString.Contains("H.265") || upperCodecString.Contains("HEVC"))
        {
            return "H.265";
        }

        return string.Empty;
    }

    public static double ParseFps(string inputString)
    {
        var pattern = @"(?<fps>[0-9]+)fps";
        var match = Regex.Match(inputString, pattern);
        if (match.Success)
        {
            return double.Parse(match.Groups["fps"].Value);
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
