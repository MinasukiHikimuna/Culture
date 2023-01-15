using FluentAssertions;

namespace CultureExtractor.Tests;

public class HumanParserTests
{
    [TestCase("13 GB", 13.0 * 1024 * 1024 * 1024)]
    [TestCase("13,1 GB", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("13.1 GB", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("205 MB", 205.0 * 1024 * 1024)]
    [TestCase("1,087.81 MB", 1087.81 * 1024 * 1024)]
    [TestCase("681.21 MB", 681.21 * 1024 * 1024)]
    public void ParseFileSizeTests(string sizeString, double expectedSize)
    {
        HumanParser
            .ParseFileSize(sizeString)
            .Should().Be(expectedSize);
    }

    [TestCase("3840x2160", 3840)]
    [TestCase("640x360", 640)]
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
    public void ParseResolutionHeightTests(string resolutionString, int expectedWidth)
    {
        HumanParser
            .ParseResolutionHeight(resolutionString)
            .Should().Be(expectedWidth);
    }

    [TestCase("17:13", 17 * 60 + 13)]
    [TestCase("01:17:13", 1 * 3600 + 17 * 60 + 13)]
    public void ParseDuration(string sizeString, int expectedTotalSeconds)
    {
        var timeSpan = HumanParser.ParseDuration(sizeString);
        timeSpan.TotalSeconds.Should().Be(expectedTotalSeconds);
    }
}
