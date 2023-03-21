using FluentAssertions;

namespace CultureExtractor.Tests;

public class HumanParserTests
{
    [TestCase("13 GB", 13.0 * 1024 * 1024 * 1024)]
    [TestCase("13,1 GB", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("13.1 GB", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("13 Gb", 13.0 * 1024 * 1024 * 1024)]
    [TestCase("13,1 Gb", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("13.1 Gb", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("205 MB", 205.0 * 1024 * 1024)]
    [TestCase("1,087.81 MB", 1087.81 * 1024 * 1024)]
    [TestCase("681.21 MB", 681.21 * 1024 * 1024)]
    [TestCase("205 Mb", 205.0 * 1024 * 1024)]
    [TestCase("1,087.81 Mb", 1087.81 * 1024 * 1024)]
    [TestCase("681.21 Mb", 681.21 * 1024 * 1024)]
    [TestCase("MP4 - 4K - 25Mpbs (5393.2 MB)", 5393.2 * 1024 * 1024)]
    [TestCase("MP4 - 720p - 3Mbps (672.2 MB)", 672.2 * 1024 * 1024)]
    public void ParseFileSizeTests(string sizeString, double expectedSize)
    {
        HumanParser
            .ParseFileSize(sizeString)
            .Should().Be(expectedSize);
    }

    [TestCase("3840x2160", 3840)]
    [TestCase("3840 x 2160", 3840)]
    [TestCase("640x360", 640)]
    [TestCase("Oculus Quest 2 7680x4320", 7680)]
    public void ParseResolutionWidthTests(string resolutionString, int expectedWidth)
    {
        HumanParser
            .ParseResolutionWidth(resolutionString)
            .Should().Be(expectedWidth);
    }

    [TestCase("UHD", 2160)]
    [TestCase("4k", 2160)]
    [TestCase("4K", 2160)]
    [TestCase("2160", 2160)]
    [TestCase("2160p", 2160)]
    [TestCase("3840 x 2160", 2160)]
    [TestCase("3840x2160", 2160)]
    [TestCase("864p", 864)]
    [TestCase("720p", 720)]
    [TestCase("360p", 360)]
    [TestCase("270p", 270)]
    [TestCase("Oculus Quest 2 7680x4320", 4320)]
    public void ParseResolutionHeightTests(string resolutionString, int expectedWidth)
    {
        HumanParser
            .ParseResolutionHeight(resolutionString)
            .Should().Be(expectedWidth);
    }

    [TestCase("17:13", 17 * 60 + 13)]
    [TestCase("01:17:13", 1 * 3600 + 17 * 60 + 13)]
    [TestCase("36m31", 36 * 60 + 31)]
    [TestCase("1h", 1 * 3600)]
    [TestCase("1h 22", 1 * 3600 + 22 * 60)]
    [TestCase("11 min", 11 * 60)]
    public void ParseDuration(string sizeString, int expectedTotalSeconds)
    {
        var timeSpan = HumanParser.ParseDuration(sizeString);
        timeSpan.TotalSeconds.Should().Be(expectedTotalSeconds);
    }

    [TestCase("60fps", 60.0)]
    [TestCase("30fps", 30.0)]
    [TestCase("24fps", 24.0)]
    public void ParseFps(string sizeString, double expectedFps)
    {
        HumanParser
            .ParseFps(sizeString)
            .Should().Be(expectedFps);
    }

    [TestCase("h264", "H.264")]
    [TestCase("H264", "H.264")]
    [TestCase("H.264", "H.264")]
    [TestCase("h265", "H.265")]
    [TestCase("H265", "H.265")]
    [TestCase("H.265", "H.265")]
    [TestCase("hevc", "H.265")]
    [TestCase("HEVC", "H.265")]
    public void ParseCodec(string sizeString, string expectedCodec)
    {
        HumanParser
            .ParseCodec(sizeString)
            .Should().Be(expectedCodec);
    }
}
