using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Moq;

namespace CultureExtractor.Tests
{
    [TestFixture]
    public class NetworkRipperTests
    {
        private Mock<IRepository> _repositoryMock;
        private Mock<IServiceProvider> _serviceProviderMock;
        private Mock<IDownloader> _downloaderMock;
        private Mock<IPlaywrightFactory> _playwrightFactoryMock;
        private Mock<ISiteScraper> _siteScraperMock;

        [SetUp]
        public void SetUp()
        {
            _repositoryMock = new Mock<IRepository>();
            _serviceProviderMock = new Mock<IServiceProvider>();
            _downloaderMock = new Mock<IDownloader>();
            _playwrightFactoryMock = new Mock<IPlaywrightFactory>();
            _siteScraperMock = new Mock<ISiteScraper>();

            _serviceProviderMock.Setup(sp => sp.GetService(typeof(ISiteScraper))).Returns(_siteScraperMock.Object);
        }

        [Test]
        public async Task ScrapeScenesAsync_CallsExpectedMethods()
        {
            // Arrange
            var site = new Site(1, "shortName", "name", "https://example.com", "username", "password", "storageState");
            var browserSettings = new BrowserSettings(true, "browserChannel");
            var scrapeOptions = new ScrapeOptions { FullScrape = false };

            _playwrightFactoryMock.Setup(pf => pf.CreatePageAsync(site, browserSettings)).ReturnsAsync(new Mock<IPage>().Object);

            var networkRipper = new NetworkRipper(_repositoryMock.Object, _serviceProviderMock.Object, _downloaderMock.Object, _playwrightFactoryMock.Object);

            // Act
            await networkRipper.ScrapeScenesAsync(site, browserSettings, scrapeOptions);

            // Assert
            _siteScraperMock.Verify(ss => ss.NavigateToScenesAndReturnPageCountAsync(site, It.IsAny<IPage>()), Times.Once());
            _siteScraperMock.Verify(ss => ss.GetCurrentScenesAsync(site, It.IsAny<IPage>()), Times.AtLeastOnce());
            _siteScraperMock.Verify(ss => ss.GoToPageAsync(It.IsAny<IPage>(), site, null, It.IsAny<int>()), Times.AtLeastOnce());
        }
    }
}
