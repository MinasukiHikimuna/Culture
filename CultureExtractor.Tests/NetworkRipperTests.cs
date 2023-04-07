using CultureExtractor.Interfaces;
using Microsoft.Playwright;
using Moq;
using Serilog;
using Serilog.Sinks.InMemory;

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
            Log.Logger = new LoggerConfiguration()
                .MinimumLevel.Verbose()
                .WriteTo.InMemory()
                .CreateLogger();

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

            var pageMock = new Mock<IPage>();
            var contextMock = new Mock<IBrowserContext>();

            _siteScraperMock.Setup(ss => ss.NavigateToScenesAndReturnPageCountAsync(It.IsAny<Site>(), It.IsAny<IPage>())).ReturnsAsync(1);

            contextMock.Setup(c => c.StorageStateAsync(null)).ReturnsAsync("{\"cookies\":[],\"origins\":[]}");
            pageMock.SetupGet(p => p.Context).Returns(contextMock.Object);

            _playwrightFactoryMock.Setup(pf => pf.CreatePageAsync(site, browserSettings)).ReturnsAsync(pageMock.Object);

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
