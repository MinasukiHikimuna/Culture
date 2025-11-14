import json
import os
from datetime import UTC, datetime

import newnewid
import scrapy
from dotenv import load_dotenv
from itemadapter import ItemAdapter

from cultureextractorscrapy.items import (
    AvailableFileEncoder,
    AvailableGalleryZipFile,
    AvailableImageFile,
    AvailableVideoFile,
    DirectDownloadItem,
    ReleaseItem,
)
from cultureextractorscrapy.spiders.database import (
    get_existing_releases_with_status,
    get_or_create_performer,
    get_or_create_tag,
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
    allowed_domains = [
        "angels.love",
        "dd-thumbs.wowgirls.com",
        "dd-photo.wowgirls.com",
        "dd-video.wowgirls.com",
        "dd-vthumbs.wowgirls.com",
    ]
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

    def _create_performer_items(self, performers, performer_urls):
        """Create performer items from names and URLs."""
        performer_items = []
        for i, performer_name in enumerate(performers):
            performer_url = performer_urls[i] if i < len(performer_urls) else None
            performer_short_name = performer_url.split("/")[-1] if performer_url else None
            full_url = f"{base_url}{performer_url}" if performer_url else None

            # Create or get performer from database
            performer = get_or_create_performer(
                self.site.id, performer_short_name, performer_name.strip(), full_url
            )
            performer_items.append(performer)
        return performer_items

    def _create_tag_items(self, tags):
        """Create tag items from tag names."""
        tag_items = []
        for tag_name in tags:
            # Tags don't have URLs on this site, use name as short_name
            tag_short_name = tag_name.lower().replace(" ", "-")

            # Create or get tag from database
            tag = get_or_create_tag(self.site.id, tag_short_name, tag_name.strip(), None)
            tag_items.append(tag)
        return tag_items

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
        detail_date_str = response.css(".metadata .release-date .date::text").get()

        # Parse date to ISO format (from "Nov 13, 2025" to "2025-11-13")
        detail_date = None
        if detail_date_str:
            try:
                parsed_date = datetime.strptime(detail_date_str, "%b %d, %Y").date()
                detail_date = parsed_date.isoformat()
            except ValueError:
                self.logger.warning(f"Could not parse date: {detail_date_str}")

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

            if format_name and download_url:
                download_files.append(
                    {
                        "format": format_name.strip(),
                        "url": download_url.strip(),
                        "size": file_size.strip() if file_size else None,
                    }
                )

        # Extract duration (always present for video content)
        duration_str = response.css(".video-duration .count::text").get()

        # Parse duration to seconds (format: MM:SS or HH:MM:SS)
        duration_seconds = 0
        if duration_str:
            parts = duration_str.split(":")
            if len(parts) == 2:  # MM:SS
                duration_seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

        # Create performer and tag items
        performer_items = self._create_performer_items(performers, performer_urls)
        tag_items = self._create_tag_items(tags)

        # Check if this release already exists
        existing_release = self.existing_releases.get(external_id)
        release_id = existing_release["uuid"] if existing_release else newnewid.uuid7()

        # Create available files list and download items
        available_files = []
        download_items = []

        # Add thumbnail as cover image
        if thumbnail:
            cover_file = AvailableImageFile(
                file_type="image",
                content_type="cover",
                variant="thumbnail",
                url=thumbnail,
            )
            available_files.append(cover_file)
            download_items.append(
                DirectDownloadItem(
                    release_id=str(release_id),
                    file_info=ItemAdapter(cover_file).asdict(),
                    url=cover_file.url,
                )
            )

        # Add only the highest quality video (last in list) to available_files for download
        # Full list of all formats is kept in json_document's download_files
        if download_files:
            # Last item in download_files list is the highest quality
            df = download_files[-1]
            video_file = AvailableVideoFile(
                file_type="video",
                content_type="video",
                variant=df["format"],
                url=df["url"],
                file_size=None,  # Size is in string format like "4.91GB", would need parsing
            )
            available_files.append(video_file)
            download_items.append(
                DirectDownloadItem(
                    release_id=str(release_id),
                    file_info=ItemAdapter(video_file).asdict(),
                    url=video_file.url,
                )
            )

        if existing_release:
            self.logger.info(
                f"Release ID={release_id} short_name={external_id} already exists. Updating existing release."
            )
        else:
            self.logger.info(f"Creating new release ID={release_id} short_name={external_id}.")

        # Create post data for json_document (convert items to dicts)
        post_data = {
            "external_id": external_id,
            "title": title,
            "performers": [
                {"name": p.name, "short_name": p.short_name, "url": p.url} for p in performer_items
            ],
            "tags": [{"name": t.name, "short_name": t.short_name, "url": t.url} for t in tag_items],
            "release_date": detail_date,
            "thumbnail": thumbnail,
            "duration": duration_str,
            "likes_count": likes_count,
            "download_files": download_files,
        }

        # First yield the ReleaseItem to ensure it's saved to database
        release_item = ReleaseItem(
            id=release_id,
            release_date=detail_date,
            short_name=external_id,
            name=title,
            url=response.url,
            description="",
            duration=duration_seconds,
            created=datetime.now(tz=UTC).astimezone(),
            last_updated=datetime.now(tz=UTC).astimezone(),
            performers=performer_items,
            tags=tag_items,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(post_data),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item

        # Now yield all the DirectDownloadItems
        yield from download_items

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
        detail_date_str = response.css(".metadata .release-date .date::text").get()

        # Parse date to ISO format (from "Nov 13, 2025" to "2025-11-13")
        detail_date = None
        if detail_date_str:
            try:
                parsed_date = datetime.strptime(detail_date_str, "%b %d, %Y").date()
                detail_date = parsed_date.isoformat()
            except ValueError:
                self.logger.warning(f"Could not parse date: {detail_date_str}")

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

            if format_name and download_url:
                download_files.append(
                    {
                        "format": format_name.strip(),
                        "url": download_url.strip(),
                        "size": file_size.strip() if file_size else None,
                    }
                )

        # Create performer and tag items
        performer_items = self._create_performer_items(performers, performer_urls)
        tag_items = self._create_tag_items(tags)

        # Check if this release already exists
        existing_release = self.existing_releases.get(external_id)
        release_id = existing_release["uuid"] if existing_release else newnewid.uuid7()

        # Create available files list and download items
        available_files = []
        download_items = []

        # Add thumbnail as cover image
        if thumbnail:
            cover_file = AvailableImageFile(
                file_type="image",
                content_type="cover",
                variant="thumbnail",
                url=thumbnail,
            )
            available_files.append(cover_file)
            download_items.append(
                DirectDownloadItem(
                    release_id=str(release_id),
                    file_info=ItemAdapter(cover_file).asdict(),
                    url=cover_file.url,
                )
            )

        # Add only the highest quality gallery (last in list) to available_files for download
        # Full list of all formats is kept in json_document's download_files
        if download_files:
            # Last item in download_files list is the highest quality
            df = download_files[-1]
            gallery_file = AvailableGalleryZipFile(
                file_type="zip",
                content_type="gallery",
                variant=df["format"],
                url=df["url"],
                file_size=None,  # Size is in string format like "164.83MB", would need parsing
            )
            available_files.append(gallery_file)
            download_items.append(
                DirectDownloadItem(
                    release_id=str(release_id),
                    file_info=ItemAdapter(gallery_file).asdict(),
                    url=gallery_file.url,
                )
            )

        if existing_release:
            self.logger.info(
                f"Release ID={release_id} short_name={external_id} already exists. Updating existing release."
            )
        else:
            self.logger.info(f"Creating new release ID={release_id} short_name={external_id}.")

        # Create post data for json_document (convert items to dicts)
        post_data = {
            "external_id": external_id,
            "title": title,
            "performers": [
                {"name": p.name, "short_name": p.short_name, "url": p.url} for p in performer_items
            ],
            "tags": [{"name": t.name, "short_name": t.short_name, "url": t.url} for t in tag_items],
            "release_date": detail_date,
            "thumbnail": thumbnail,
            "images_count": images_count,
            "likes_count": likes_count,
            "download_files": download_files,
        }

        # First yield the ReleaseItem to ensure it's saved to database
        release_item = ReleaseItem(
            id=release_id,
            release_date=detail_date,
            short_name=external_id,
            name=title,
            url=response.url,
            description="",
            duration=0,  # Galleries don't have duration
            created=datetime.now(tz=UTC).astimezone(),
            last_updated=datetime.now(tz=UTC).astimezone(),
            performers=performer_items,
            tags=tag_items,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(post_data),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item

        # Now yield all the DirectDownloadItems
        yield from download_items
