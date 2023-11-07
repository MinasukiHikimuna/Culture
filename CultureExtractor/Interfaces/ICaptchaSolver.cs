using Microsoft.Playwright;

namespace CultureExtractor.Interfaces;

public interface ICaptchaSolver
{
    Task SolveCaptchaIfNeededAsync(IPage page);
}