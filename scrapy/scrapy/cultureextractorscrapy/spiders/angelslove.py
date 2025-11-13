import json
import os

from dotenv import load_dotenv

import scrapy
from cultureextractorscrapy.spiders.database import (
    get_existing_releases_with_status,
    get_site_item,
)
from cultureextractorscrapy.utils import (
    get_log_filename,
)

load_dotenv()

cookies_json = os.getenv("ANGELSLOVE_COOKIES")
if cookies_json:
    # Parse browser-format cookies and convert to scrapy format
    browser_cookies = json.loads(cookies_json)
    # Convert to dictionary format that scrapy expects
    cookies = {cookie["name"]: cookie["value"] for cookie in browser_cookies}
else:
    cookies = {}

base_url = "https://angels.love"


class AngelsLoveSpider(scrapy.Spider):
    name = "angelslove"
    allowed_domains = ["angels.love"]
    start_urls = [base_url]
    site_short_name = "angelslove"

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)

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
        # Request movies first, then photos
        yield scrapy.Request(
            url=f"{base_url}/members/content?page=1",
            callback=self.parse_movies_page,
            cookies=cookies,
            meta={"page": 1, "content_type": "all"},
        )

    def parse_movies_page(self, response):
        """Parse a page of movies."""
        page_num = response.meta.get("page", 1)
        self.logger.info(f"Parsing movies page {page_num}: {response.url}")

        # Extract all content items from the grid
        content_items = response.css("div.content-view-grid div.content-grid-item-wrapper")

        self.logger.info(f"Found {len(content_items)} content items on movies page {page_num}")

        for item in content_items:
            # Extract the URL and external ID from the link
            item_link = item.css('a[href*="/members/content/item/"]::attr(href)').get()
            if item_link:
                # Extract external ID from URL (e.g., /members/content/item/b9738634-whispers-of-ecstasy)
                external_id = item_link.split("/")[-1]

                # Extract title from the metadata section
                title = item.css(".metadata .title::text").get()
                if title:
                    title = title.strip()

                # Extract performers
                performers = item.css(".metadata .models a::text").getall()
                performer_urls = item.css(".metadata .models a::attr(href)").getall()

                # Extract date (not available on list page - will get from detail page)
                date_text = item.css(".metadata .release-date .date::text").get()

                # Extract thumbnail
                thumbnail = item.css(".elastic-content-tile img.thumb::attr(src)").get()

                # Check if content has play overlay (indicates video/media content)
                has_play_overlay = item.css(".content-tile-play").get() is not None

                self.logger.info(f"Found release: {external_id} - {title}")

                # Yield request to parse detail page
                yield scrapy.Request(
                    url=f"{base_url}{item_link}",
                    callback=self.parse_detail_page,
                    cookies=cookies,
                    meta={
                        "external_id": external_id,
                        "title": title,
                        "performers": performers,
                        "performer_urls": performer_urls,
                        "date_text": date_text,
                        "thumbnail": thumbnail,
                        "has_play_overlay": has_play_overlay,
                    },
                )

        # Check if there's a next page - looking at the pagination
        # For the first run, just process page 1
        if page_num == 1:
            self.logger.info("Finished processing movies page 1 (stopping here for initial test)")

        self.logger.info(f"Finished processing movies page {page_num}")

    def parse_detail_page(self, response):
        """Parse a content detail page to extract additional metadata."""
        # Get metadata from list page
        external_id = response.meta["external_id"]
        title = response.meta["title"]
        performers = response.meta["performers"]
        performer_urls = response.meta["performer_urls"]
        date_text = response.meta["date_text"]
        thumbnail = response.meta["thumbnail"]
        has_play_overlay = response.meta["has_play_overlay"]

        self.logger.info(f"Parsing detail page: {external_id} - {title}")

        # Extract tags
        tags = response.css('a[href*="/members/home/watchall/"]::text').getall()

        # Extract release date from detail page
        detail_date = response.css(".metadata .release-date .date::text").get()

        # Extract photo/image count (only present for galleries)
        images_count = response.css(".images-count .count::text").get()

        # Extract likes count (not important - optional field)
        likes_count = response.css(".likes-count .count::text").get()

        # Extract download options
        download_formats = response.css(".download-button .format-name::text").getall()

        # Extract file sizes (matching MB or GB patterns)
        file_sizes_raw = response.css("div.download-button-wrapper *::text").getall()
        file_sizes = [
            text.strip()
            for text in file_sizes_raw
            if text.strip() and ("MB" in text or "GB" in text)
        ]

        # Description is not available on this site
        description = None

        # Extract duration (only present for video content)
        duration = response.css(".video-duration .count::text").get()

        # Print all extracted data for validation
        print(f"\n{'=' * 80}")
        print(f"DETAIL PAGE: {external_id}")
        print(f"{'=' * 80}")
        print(f"Title: {title}")
        print(f"URL: {response.url}")
        print(f"Performers: {', '.join(performers) if performers else 'N/A'}")
        print(f"Performer URLs: {', '.join(performer_urls) if performer_urls else 'N/A'}")
        print(f"Date (list page): {date_text}")
        print(f"Date (detail page): {detail_date}")
        print(f"Thumbnail: {thumbnail}")
        print(f"Has Play Overlay: {has_play_overlay}")
        print(f"Tags: {', '.join(tags) if tags else 'N/A'}")
        print(f"Images Count: {images_count}")
        print(f"Likes Count: {likes_count}")
        print(f"Download Formats: {', '.join(download_formats) if download_formats else 'N/A'}")
        print(f"File Sizes: {', '.join(file_sizes) if file_sizes else 'N/A'}")
        print(f"Description: {description if description else 'N/A'}")
        print(f"Duration: {duration if duration else 'N/A'}")
        print(f"{'=' * 80}\n")

        # TODO: Create ReleaseItem and yield when ready for database updates
