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
        # Extract video entries - each video is in a div.item-col
        video_entries = response.css("div.item-col")

        for entry in video_entries:
            # Extract basic information from the listing
            link = entry.css("div.item-inner-col a[href*=video]")
            if not link:
                continue

            # Get the URL and title
            detail_url = link.css("::attr(href)").get()
            title = link.css("span.item-info span.title::text").get().strip()

            # Extract duration
            duration_text = link.css("span.image span.time::text").get()
            if duration_text:
                # Convert MM:SS to seconds
                try:
                    minutes, seconds = map(int, duration_text.split(":"))
                    duration = minutes * 60 + seconds
                except ValueError:
                    duration = 0

            # Extract video ID from URL
            video_id = detail_url.split("-")[-1].replace(".html", "")
            external_id = f"video-{video_id}"

            # Extract performer names from title (format "Performer1 & Performer2")
            performers = [p.strip() for p in title.split("&")]

            # Check if we already have this release
            existing_release = self.existing_releases.get(external_id)

            if self.force_update or not existing_release:
                yield scrapy.Request(
                    url=response.urljoin(detail_url),
                    callback=self.parse_video_detail,
                    cookies=cookies,
                    meta={
                        "external_id": external_id,
                        "title": title,
                        "performers": performers,
                        "duration": duration,
                    },
                )
            else:
                self.logger.info(f"Skipping existing video release: {external_id}")

        # Handle pagination - look for next page link
        next_page = response.css('a.next[rel="next"]::attr(href)').get()
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
        # Extract photo gallery entries - each gallery is in a div.item-col
        gallery_entries = response.css("div.item-col")

        for entry in gallery_entries:
            # Extract basic information from the listing
            link = entry.css("div.item-inner-col a[href*=photo]")
            if not link:
                continue

            # Get the URL and title
            detail_url = link.css("::attr(href)").get()
            title = link.css("span.item-info span.title::text").get().strip()

            # Extract gallery ID from URL
            gallery_id = detail_url.split("-")[-1].replace(".html", "")
            external_id = f"gallery-{gallery_id}"

            # Extract performer names from title (format "Performer1 & Performer2")
            performers = [p.strip() for p in title.split("&")]

            # Check if we already have this release
            existing_release = self.existing_releases.get(external_id)

            if self.force_update or not existing_release:
                yield scrapy.Request(
                    url=response.urljoin(detail_url),
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

        # Handle pagination - look for next page link
        next_page = response.css('a.next[rel="next"]::attr(href)').get()
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
