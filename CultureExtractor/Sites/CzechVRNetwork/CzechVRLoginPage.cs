using Microsoft.Playwright;
using Serilog;

namespace CultureExtractor.Sites.CzechVRNetwork;

public class CzechVRLoginPage
{
    private readonly IPage _page;

    private readonly ILocator _memberLoginHeader;

    public CzechVRLoginPage(IPage page)
    {
        _page = page;

        _memberLoginHeader = _page.GetByRole(AriaRole.Heading, new() { NameString = "Member login" });
    }

    public async Task LoginIfNeededAsync(Site site)
    {
        // TODO: sometimes this requires captcha, how to handle reliably?
        if (await _memberLoginHeader.IsVisibleAsync())
        {
            // Login requires CAPTCHA so we need to create a headful browser
            /*IPage loginPage = await PlaywrightFactory.CreatePageAsync(site, new BrowserSettings(false));
            await loginPage.WaitForLoadStateAsync();*/

            var loginPage = _page;

            await loginPage.GetByPlaceholder("Username").TypeAsync(site.Username);
            await loginPage.GetByPlaceholder("Password").TypeAsync(site.Password);
            await loginPage.GetByRole(AriaRole.Button, new() { NameString = "CLICK HERE TO LOGIN" }).ClickAsync();
            await loginPage.WaitForLoadStateAsync();

            Thread.Sleep(10000);

            // Log.Warning("CAPTCHA required! Please enter manually.");
            // Thread.Sleep(60000);
            // await loginPage.Locator("#rc-imageselect").WaitForAsync(new LocatorWaitForOptions() { State = WaitForSelectorState.Detached, Timeout = 60000 });

            // await loginPage.CloseAsync();
        }
    }
}
