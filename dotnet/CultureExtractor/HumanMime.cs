using Microsoft.Playwright;

namespace CultureExtractor;

public static class HumanMime
{
    private static readonly Random Random = new();

    public static async Task DelayRandomlyAsync(int minDelay, int maxDelay, CancellationToken cancellationToken)
    {
        if (minDelay > maxDelay)
        {
            throw new ArgumentException("Minimum delay cannot be greater than maximum delay.");
        }

        var delay = Random.Next(minDelay, maxDelay);
        await Task.Delay(delay, cancellationToken);
    }
    
    public static async Task TypeLikeHumanAsync(ILocator locator, string value)
    {
        await locator.HoverAsync();
        await locator.ClickAsync();
        await locator.FocusAsync();
        
        foreach (var character in value)
        {
            var delay = Random.Next(48, 514);
            await locator.PressSequentiallyAsync(character.ToString(), new() { Delay = delay });
        }
        
        await DelayRandomlyAsync(124, 2174, CancellationToken.None);
    }
}
