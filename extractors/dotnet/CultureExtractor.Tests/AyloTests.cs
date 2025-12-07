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
        var rootObject = await DeserializeMoviesRootObject();
        rootObject.meta.Should().BeEquivalentTo(new AyloMoviesRequest.Meta { count = 20, total = 3369 });
    }

    [Test]
    public async Task ParseResult()
    {
        var rootObject = await DeserializeMoviesRootObject();
        rootObject.result[0].brand.Should().Be("digitalplayground");
    }

    [Test]
    public async Task ParseSingle()
    {
        var rootObject = await DeserializeMovieRootObject();
        rootObject.result.brand.Should().Be("digitalplayground");
    }

    private static async Task<AyloMoviesRequest.RootObject?> DeserializeMoviesRootObject()
    {
        var json = await File.ReadAllTextAsync("aylo.json");
        var rootObject = JsonSerializer.Deserialize<AyloMoviesRequest.RootObject>(json);
        return rootObject;
    }
    
    private static async Task<AyloMovieRequest.RootObject?> DeserializeMovieRootObject()
    {
        var json = await File.ReadAllTextAsync("aylo_single.json");
        var rootObject = JsonSerializer.Deserialize<AyloMovieRequest.RootObject>(json);
        return rootObject;
    }
}