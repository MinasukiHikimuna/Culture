import os
import json
import newnewid
from datetime import datetime, timezone
from dotenv import load_dotenv
import scrapy
from cultureextractorscrapy.spiders.database import (
    get_site_item,
    get_or_create_performer,
    get_or_create_tag,
    get_existing_releases_with_status,
)
from cultureextractorscrapy.items import (
    AvailableGalleryZipFile,
    AvailableImageFile,
    AvailableVideoFile,
    AvailableFileEncoder,
    ReleaseItem,
    DirectDownloadItem,
)
from cultureextractorscrapy.utils import (
    parse_resolution_height,
    parse_resolution_width,
    get_log_filename,
)
from itemadapter import ItemAdapter

load_dotenv()

cookies = json.loads(os.getenv("LEZKISS_COOKIES"))
base_url = os.getenv("LEZKISS_BASE_URL")


class LezKissSpider(scrapy.Spider):
    name = "lezkiss"
    allowed_domains = os.getenv("LEZKISS_ALLOWED_DOMAINS").split(",")
    start_urls = [base_url]
    site_short_name = "lezkiss"

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(LezKissSpider, cls).from_crawler(crawler, *args, **kwargs)

        # Set the log file using the spider name
        crawler.settings.set("LOG_FILE", get_log_filename(spider.name))

        # Get force_update from crawler settings or default to False
        spider.force_update = crawler.settings.getbool("FORCE_UPDATE", False)

        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(
                f"Site with short_name '{spider.site_short_name}' not found in the database."
            )
        spider.site = site_item

        # Get existing releases with their download status
        spider.existing_releases = get_existing_releases_with_status(site_item.id)
        return spider

    def parse(self, response):
        """Initial parse method - entry point for the spider."""
        # Start crawling both videos and photos sections
        yield scrapy.Request(
            url=f"{base_url}/videos/",
            callback=self.parse_videos,
            cookies=cookies,
            meta={"page": 1},
        )

        yield scrapy.Request(
            url=f"{base_url}/photos/",
            callback=self.parse_photos,
            cookies=cookies,
            meta={"page": 1},
        )

    def parse_videos(self, response):
        """Parse the videos listing page."""
        # Extract video entries
        video_entries = response.css(
            "div.update-item"
        )  # Adjust selector based on actual HTML structure

        for entry in video_entries:
            # Extract basic information from the listing
            title = entry.css("h2::text").get()
            if not title:
                continue

            # Extract performer names from title (assuming format "Performer1 & Performer2")
            performers = [p.strip() for p in title.split("&")]

            # Generate a unique external ID for the video
            external_id = f"video-{entry.css('::attr(data-id)').get()}"  # Adjust based on actual HTML

            # Get the detail page URL
            detail_url = entry.css("a::attr(href)").get()
            if detail_url and not detail_url.startswith(("http://", "https://")):
                detail_url = response.urljoin(detail_url)

            # Check if we already have this release
            existing_release = self.existing_releases.get(external_id)

            if self.force_update or not existing_release:
                yield scrapy.Request(
                    url=detail_url,
                    callback=self.parse_video_detail,
                    cookies=cookies,
                    meta={
                        "external_id": external_id,
                        "title": title,
                        "performers": performers,
                    },
                )
            else:
                self.logger.info(f"Skipping existing video release: {external_id}")

        # Handle pagination
        next_page = response.css(
            "a.next-page::attr(href)"
        ).get()  # Adjust selector based on actual HTML
        if next_page:
            current_page = response.meta["page"]
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse_videos,
                cookies=cookies,
                meta={"page": current_page + 1},
            )

    def parse_photos(self, response):
        """Parse the photos listing page."""
        # Extract photo gallery entries
        gallery_entries = response.css(
            "div.update-item"
        )  # Adjust selector based on actual HTML structure

        for entry in gallery_entries:
            # Extract basic information from the listing
            title = entry.css("h2::text").get()
            if not title:
                continue

            # Extract performer names from title (assuming format "Performer1 & Performer2")
            performers = [p.strip() for p in title.split("&")]

            # Generate a unique external ID for the gallery
            external_id = f"gallery-{entry.css('::attr(data-id)').get()}"  # Adjust based on actual HTML

            # Get the detail page URL
            detail_url = entry.css("a::attr(href)").get()
            if detail_url and not detail_url.startswith(("http://", "https://")):
                detail_url = response.urljoin(detail_url)

            # Check if we already have this release
            existing_release = self.existing_releases.get(external_id)

            if self.force_update or not existing_release:
                yield scrapy.Request(
                    url=detail_url,
                    callback=self.parse_gallery_detail,
                    cookies=cookies,
                    meta={
                        "external_id": external_id,
                        "title": title,
                        "performers": performers,
                    },
                )
            else:
                self.logger.info(f"Skipping existing gallery release: {external_id}")

        # Handle pagination
        next_page = response.css(
            "a.next-page::attr(href)"
        ).get()  # Adjust selector based on actual HTML
        if next_page:
            current_page = response.meta["page"]
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse_photos,
                cookies=cookies,
                meta={"page": current_page + 1},
            )

    def parse_video_detail(self, response):
        """Parse individual video detail page."""
        # This will be implemented next
        pass

    def parse_gallery_detail(self, response):
        """Parse individual gallery detail page."""
        # This will be implemented next
        pass
