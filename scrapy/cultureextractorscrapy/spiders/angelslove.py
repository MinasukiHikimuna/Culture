import json
import os

import scrapy
from dotenv import load_dotenv

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

                # Extract thumbnail
                thumbnail = item.css(".elastic-content-tile img.thumb::attr(src)").get()

                # Check content type by hover image:
                # Videos: /static/images/members/play-button-hover-ab70d572a3.png
                # Galleries: /static/svg/members/photo-tile-overlay-hover-6cd82fe9c7.svg
                hover_img = item.css("img.hover::attr(src)").get()
                is_video = hover_img and "play-button-hover" in hover_img if hover_img else False

                self.logger.info(f"Found release: {external_id} - {title}")

                # Yield request to appropriate detail page parser based on content type
                callback = self.parse_video_detail if is_video else self.parse_gallery_detail
                yield scrapy.Request(
                    url=f"{base_url}{item_link}",
                    callback=callback,
                    cookies=cookies,
                    meta={
                        "external_id": external_id,
                        "title": title,
                        "performers": performers,
                        "performer_urls": performer_urls,
                        "thumbnail": thumbnail,
                    },
                )

        # Check if there's a next page - looking at the pagination
        # For the first run, just process page 1
        if page_num == 1:
            self.logger.info("Finished processing movies page 1 (stopping here for initial test)")

        self.logger.info(f"Finished processing movies page {page_num}")

    def parse_video_detail(self, response):
        """Parse a video detail page to extract additional metadata."""
        # Get metadata from list page
        external_id = response.meta["external_id"]
        title = response.meta["title"]
        performers = response.meta["performers"]
        performer_urls = response.meta["performer_urls"]
        thumbnail = response.meta["thumbnail"]

        self.logger.info(f"Parsing video detail page: {external_id} - {title}")

        # Extract tags
        tags = response.css('a[href*="/members/home/watchall/"]::text').getall()

        # Extract release date from detail page
        detail_date = response.css(".metadata .release-date .date::text").get()

        # Extract likes count (not important - optional field)
        likes_count = response.css(".likes-count .count::text").get()

        # Extract download options (videos have multiple resolutions)
        download_buttons = response.css("div.download-button")
        download_files = []

        for button in download_buttons:
            format_name = button.css("div.format-name::text").get()
            download_url = button.css("::attr(data-href)").get()
            # Get file size from sibling div.info
            file_size = button.xpath("following-sibling::div[@class='info']/text()").get()
            # Check if premium content
            button_classes = button.css("::attr(class)").get() or ""
            is_premium = "download-button-premium" in button_classes

            if format_name and download_url:
                download_files.append(
                    {
                        "format": format_name.strip(),
                        "url": download_url.strip(),
                        "size": file_size.strip() if file_size else None,
                        "is_premium": is_premium,
                    }
                )

        # Extract duration (always present for video content)
        duration = response.css(".video-duration .count::text").get()

        # Print all extracted data for validation
        print(f"\n{'=' * 80}")
        print(f"VIDEO: {external_id}")
        print(f"{'=' * 80}")
        print(f"Title: {title}")
        print(f"URL: {response.url}")
        print(f"Performers: {', '.join(performers) if performers else 'N/A'}")
        print(f"Performer URLs: {', '.join(performer_urls) if performer_urls else 'N/A'}")
        print(f"Date (detail page): {detail_date}")
        print(f"Thumbnail: {thumbnail}")
        print(f"Tags: {', '.join(tags) if tags else 'N/A'}")
        print(f"Likes Count: {likes_count if likes_count else 'N/A'}")
        print(f"Duration: {duration}")
        print("\nDownload Files:")
        for df in download_files:
            premium_marker = " [PREMIUM]" if df["is_premium"] else ""
            print(f"  - {df['format']}: {df['size']}{premium_marker}")
            print(f"    URL: {df['url']}")
        print(f"{'=' * 80}\n")

        # TODO: Create ReleaseItem and yield when ready for database updates

    def parse_gallery_detail(self, response):
        """Parse a gallery detail page to extract additional metadata."""
        # Get metadata from list page
        external_id = response.meta["external_id"]
        title = response.meta["title"]
        performers = response.meta["performers"]
        performer_urls = response.meta["performer_urls"]
        thumbnail = response.meta["thumbnail"]

        self.logger.info(f"Parsing gallery detail page: {external_id} - {title}")

        # Extract tags
        tags = response.css('a[href*="/members/home/watchall/"]::text').getall()

        # Extract release date from detail page
        detail_date = response.css(".metadata .release-date .date::text").get()

        # Extract photo/image count (always present for galleries)
        images_count = response.css(".images-count .count::text").get()

        # Extract likes count (not important - optional field)
        likes_count = response.css(".likes-count .count::text").get()

        # Extract download options (galleries have different size options)
        download_buttons = response.css("div.download-button")
        download_files = []

        for button in download_buttons:
            format_name = button.css("div.format-name::text").get()
            download_url = button.css("::attr(data-href)").get()
            # Get file size from sibling div.info (or parent's sibling for galleries)
            file_size = button.xpath("following-sibling::div[@class='info']/text()").get()
            if not file_size:
                # For galleries with wrapper, try parent's sibling
                file_size = button.xpath("../following-sibling::div[@class='info']/text()").get()
            # Check if premium content
            button_classes = button.css("::attr(class)").get() or ""
            is_premium = "download-button-premium" in button_classes

            if format_name and download_url:
                download_files.append(
                    {
                        "format": format_name.strip(),
                        "url": download_url.strip(),
                        "size": file_size.strip() if file_size else None,
                        "is_premium": is_premium,
                    }
                )

        # Print all extracted data for validation
        print(f"\n{'=' * 80}")
        print(f"GALLERY: {external_id}")
        print(f"{'=' * 80}")
        print(f"Title: {title}")
        print(f"URL: {response.url}")
        print(f"Performers: {', '.join(performers) if performers else 'N/A'}")
        print(f"Performer URLs: {', '.join(performer_urls) if performer_urls else 'N/A'}")
        print(f"Date (detail page): {detail_date}")
        print(f"Thumbnail: {thumbnail}")
        print(f"Tags: {', '.join(tags) if tags else 'N/A'}")
        print(f"Likes Count: {likes_count if likes_count else 'N/A'}")
        print(f"Images Count: {images_count}")
        print("\nDownload Files:")
        for df in download_files:
            premium_marker = " [PREMIUM]" if df["is_premium"] else ""
            print(f"  - {df['format']}: {df['size']}{premium_marker}")
            print(f"    URL: {df['url']}")
        print(f"{'=' * 80}\n")

        # TODO: Create ReleaseItem and yield when ready for database updates
