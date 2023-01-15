using FluentAssertions;

namespace CultureExtractor.Tests;

public class HumanParserTests
{
    [TestCase("13 GB", 13.0 * 1024 * 1024 * 1024)]
    [TestCase("13,1 GB", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("13.1 GB", 13.1 * 1024 * 1024 * 1024)]
    [TestCase("205 MB", 205.0 * 1024 * 1024)]
    public void FileSizeParser(string sizeString, double expectedSize)
    {
        HumanParser
            .ParseFileSize(sizeString)
            .Should().Be(expectedSize);
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
    public void ResolutionParser(string resolutionString, int expectedWidth)
    {
        HumanParser
            .ParseResolutionWidth(resolutionString)
            .Should().Be(expectedWidth);
    }
}
