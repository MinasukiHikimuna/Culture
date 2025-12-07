using CultureExtractor.CaptchaBuster;
using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor
{
    public class CaptchaSolver : ICaptchaSolver
    {
        private readonly ILegacyDownloader _legacyDownloader;

        public CaptchaSolver(ILegacyDownloader legacyDownloader)
        {
            _legacyDownloader = legacyDownloader;
        }

        public async Task SolveCaptchaIfNeededAsync(IPage page)
        {
            await Task.Delay(3000);

            if (!(await page.Locator("div.captcha").IsVisibleAsync()) && !(await page.Locator("div.g-recaptcha").IsVisibleAsync()))
            {
                Log.Error("CAPTCHA not found! Exiting!");
                return;
            }

            var iframes = await page.QuerySelectorAllAsync("iframe");

            IElementHandle iframeA = null;
            IElementHandle iframeC = null;

            string iframeAName = null;
            string iframeCName = null;

            foreach (var iframe in iframes)
            {
                var iframeName = await iframe.GetAttributeAsync("name");
                if (!string.IsNullOrWhiteSpace(iframeName))
                {
                    if (iframeName.StartsWith("a-"))
                    {
                        iframeA = iframe;
                        iframeAName = iframeName;
                    }
                    if (iframeName.StartsWith("c-"))
                    {
                        iframeC = iframe;
                        iframeCName = iframeName;
                    }
                }
            }

            if (iframeA == null)
            {
                throw new InvalidOperationException("iframeA is missing!");
            }
            if (iframeC == null)
            {
                throw new InvalidOperationException("iframeC is missing!");
            }
            if (string.IsNullOrWhiteSpace(iframeAName))
            {
                throw new InvalidOperationException($"iframeAName is {iframeAName}");
            }
            if (string.IsNullOrWhiteSpace(iframeCName))
            {
                throw new InvalidOperationException($"iframeCName is {iframeCName}");
            }

            Log.Information("CAPTCHA found. Solving...");

            var captchaButton = page.FrameLocator($"iframe[name=\"{iframeAName}\"]").GetByLabel("I'm not a robot");
            if (await captchaButton.IsVisibleAsync())
            {
                await captchaButton.ClickAsync();
            }

            await Task.Delay(5000);

            var audioButton = page.FrameLocator($"iframe[name=\"{iframeCName}\"]").Locator("button#recaptcha-audio-button");
            if (await audioButton.IsVisibleAsync())
            {
                await audioButton.ClickAsync();
            }

            var audioUrl = await page.FrameLocator($"iframe[name=\"{iframeCName}\"]").Locator("a.rc-audiochallenge-tdownload-link").GetAttributeAsync("href");

            var audioPath = await _legacyDownloader.DownloadCaptchaAudioAsync(audioUrl);

            var captchaBuster = new CaptchaBusterImplementation();
            var result = await captchaBuster.SolveCaptchaAsync(audioPath);

            Log.Debug($"CAPTCHA challenge text transcriped: {result.Text}");

            await Task.Delay(5000);

            await page
                .FrameLocator($"iframe[name=\"{iframeCName}\"]")
                .GetByRole(AriaRole.Textbox, new() { NameString = "Enter what you hear" })
                .FillAsync(result.Text);

            await Task.Delay(2000);

            await page
                .FrameLocator($"iframe[name=\"{iframeCName}\"]")
                .GetByRole(AriaRole.Button, new() { NameString = "Verify" })
                .ClickAsync();

            await Task.Delay(5000);

            Log.Information("CAPTCHA solved!");
        }
    }
}
