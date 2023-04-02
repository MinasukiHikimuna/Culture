using CultureExtractor.CaptchaBuster;
using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor
{
    public class CaptchaSolver : ICaptchaSolver
    {
        private readonly IDownloader _downloader;

        public CaptchaSolver(IDownloader downloader)
        {
            _downloader = downloader;
        }

        public async Task SolveCaptchaIfNeededAsync(IPage page)
        {
            await Task.Delay(3000);

            var blocked = await page.IsVisibleAsync("div#g-recaptcha");
            if (!blocked)
            {
                Log.Verbose("No CAPTCHA found.");
                return;
            }

            Log.Information("CAPTCHA found. Solving...");

            var iframeName = await page.EvaluateAsync<string>("document.querySelector(\"iframe[title='reCAPTCHA']\").name");

            await Task.Delay(1000);

            await page.FrameLocator($"iframe[name=\"{iframeName}\"]").GetByRole(AriaRole.Checkbox, new() { NameString = "I'm not a robot" }).ClickAsync();

            await Task.Delay(1000);

            var innerIframeName = await page.EvaluateAsync<string>("document.querySelector(\"iframe[title='recaptcha challenge expires in two minutes']\").name");

            await Task.Delay(2000);

            await page.FrameLocator($"iframe[name=\"{innerIframeName}\"]").Locator("button#recaptcha-audio-button").ClickAsync();
            var audioUrl = await page.FrameLocator($"iframe[name=\"{innerIframeName}\"]").Locator("a.rc-audiochallenge-tdownload-link").GetAttributeAsync("href");

            var audioPath = await _downloader.DownloadCaptchaAudioAsync(audioUrl);

            var captchaBuster = new CaptchaBusterImplementation();
            var result = await captchaBuster.SolveCaptchaAsync(audioPath);

            Log.Verbose($"CAPTCHA challenge text transcriped: {result.Text}");

            await Task.Delay(5000);

            await page
                .FrameLocator($"iframe[name=\"{innerIframeName}\"]")
                .GetByRole(AriaRole.Textbox, new() { NameString = "Enter what you hear" })
                .FillAsync(result.Text);

            await Task.Delay(2000);

            await page
                .FrameLocator($"iframe[name=\"{innerIframeName}\"]")
                .GetByRole(AriaRole.Button, new() { NameString = "Verify" })
                .ClickAsync();

            await Task.Delay(3000);

            /*await page
                .Locator($"div#blocked input[type=\"submit\"]")
                .ClickAsync();*/

            await Task.Delay(5000);

            Log.Information("CAPTCHA solved!");
        }
    }
}
