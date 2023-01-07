using Microsoft.Playwright;

namespace RipperPlaywright.Pages.WowNetwork
{
    public class WowLoginPage
    {
        private readonly IPage _page;

        private readonly ILocator _signInButton;
        private readonly ILocator _emailInput;
        private readonly ILocator _passwordInput;
        private readonly ILocator _getInsideButton;

        public WowLoginPage(IPage page)
        {
            _page = page;

            _signInButton = _page.GetByRole(AriaRole.Link, new() { NameString = "Sign in" });
            _emailInput = _page.GetByPlaceholder("E-Mail");
            _passwordInput = _page.GetByPlaceholder("Password");
            _getInsideButton = _page.GetByText("Get Inside");
        }

        public async Task LoginIfNeededAsync(Site site)
        {
            if (await _signInButton.IsVisibleAsync())
            {
                await _signInButton.ClickAsync();
                await _page.WaitForLoadStateAsync();

                await _emailInput.TypeAsync(site.Username);
                await _passwordInput.TypeAsync(site.Password);
                await _getInsideButton.ClickAsync();
                await _page.WaitForLoadStateAsync();
            }
        }
    }
}
