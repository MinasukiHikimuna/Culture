import json
import os
from datetime import UTC, datetime

import newnewid
from dotenv import load_dotenv

import scrapy
from cultureextractorscrapy.items import (
    ReleaseItem,
)
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
    cookies = json.loads(cookies_json)
else:
    cookies = []

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
        crawler.settings.set('LOG_FILE', get_log_filename(spider.name))

        # Get force_update from crawler settings or default to False
        spider.force_update = crawler.settings.getbool('FORCE_UPDATE', False)

        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(f"Site with short_name '{spider.site_short_name}' not found in the database.")
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
            meta={"page": 1, "content_type": "all"})

    def parse_movies_page(self, response):
        """Parse a page of movies."""
        page_num = response.meta.get("page", 1)
        self.logger.info(f"Parsing movies page {page_num}: {response.url}")

        # Extract all content items from the grid
        content_items = response.css('div.content-view-grid div.content-grid-item-wrapper')

        self.logger.info(f"Found {len(content_items)} content items on movies page {page_num}")

        for item in content_items:
            # Extract the URL and external ID from the link
            item_link = item.css('a::attr(href)').get()
            if item_link:
                # Extract external ID from URL (e.g., /members/content/item/b9738634-whispers-of-ecstasy)
                external_id = item_link.split('/')[-1]

                # Extract title from the text content
                title = item.css('div > div:first-child::text').get()
                if title:
                    title = title.strip()

                # Extract performers
                performers = item.css('a[href*="/members/model/"]::text').getall()

                # Extract date
                date_text = item.css('div > div:last-child > div:first-child::text').get()

                self.logger.info(f"Found release: {external_id} - {title}")

                # For now, just print the data without scraping detail pages
                print(f"Release: {external_id}")
                print(f"  Title: {title}")
                print(f"  Performers: {', '.join(performers) if performers else 'N/A'}")
                print(f"  Date: {date_text}")
                print(f"  URL: {base_url}{item_link}")
                print()

        # Check if there's a next page - looking at the pagination
        # For the first run, just process page 1
        if page_num == 1:
            self.logger.info(f"Finished processing movies page 1 (stopping here for initial test)")

        self.logger.info(f"Finished processing movies page {page_num}")
