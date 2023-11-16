using System.Text.Json;
using CultureExtractor.Sites;
using FluentAssertions;

namespace CultureExtractor.Tests;

[TestFixture]
public class AyloTests
{
    [Test]
    public async Task ParseMeta()
    {
        var rootObject = await DeserializeRootObject();
        rootObject.meta.Should().BeEquivalentTo(new AyloMoviesRequest.Meta { count = 20, total = 3369 });
    }

    [Test]
    public async Task ParseResult()
    {
        var rootObject = await DeserializeRootObject();
        rootObject.result[0].brand.Should().Be("digitalplayground");
    }

    private static async Task<AyloMoviesRequest.RootObject?> DeserializeRootObject()
    {
        var json = await File.ReadAllTextAsync("aylo.json");
        var rootObject = JsonSerializer.Deserialize<AyloMoviesRequest.RootObject>(json);
        return rootObject;
    }
}