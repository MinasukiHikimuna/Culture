using Microsoft.Playwright;

namespace CultureExtractor
{
    public interface ICaptchaSolver
    {
        Task SolveCaptchaIfNeededAsync(IPage page);
    }
}