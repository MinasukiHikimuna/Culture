using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ISite
{
    Task LoginAsync(Site site, IPage page);
}
