import json
import os
import re
from datetime import UTC, datetime

import newnewid
import scrapy
from dotenv import load_dotenv
from itemadapter import ItemAdapter
from scrapy.exceptions import CloseSpider

from cultureextractorscrapy.items import (
    AvailableFileEncoder,
    AvailableGalleryZipFile,
    AvailableImageFile,
    AvailableVideoFile,
    DirectDownloadItem,
    PerformerItem,
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

# Site configurations for the WowGirls network sites
SITE_CONFIGS = {
    "angelslove": {
        "base_url": "https://angels.love",
        "cookie_env_var": "ANGELSLOVE_COOKIES",
        "site_short_name": "angelslove",
        "allowed_domains": [
            "angels.love",
            "dd-thumbs.wowgirls.com",
            "dd-photo.wowgirls.com",
            "dd-video.wowgirls.com",
            "dd-vthumbs.wowgirls.com",
        ],
    },
    "sensuallove": {
        "base_url": "https://sensual.love",
        "cookie_env_var": "SENSUALLOVE_COOKIES",
        "site_short_name": "sensuallove",
        "allowed_domains": [
            "sensual.love",
            "dd-thumbs.wowgirls.com",
            "dd-photo.wowgirls.com",
            "dd-video.wowgirls.com",
            "dd-vthumbs.wowgirls.com",
        ],
    },
    "ultrafilms": {
        "base_url": "https://ultrafilms.com",
        "cookie_env_var": "ULTRAFILMS_COOKIES",
        "site_short_name": "ultrafilms",
        "allowed_domains": [
            "ultrafilms.com",
            "dd-thumbs.wowgirls.com",
            "dd-photo.wowgirls.com",
            "dd-video.wowgirls.com",
            "dd-vthumbs.wowgirls.com",
        ],
    },
}


def get_cookies_for_site(site_key):
    """Load cookies from environment variable for the specified site."""
    config = SITE_CONFIGS.get(site_key, SITE_CONFIGS["angelslove"])
    cookies_json = os.getenv(config["cookie_env_var"])
    if cookies_json:
        browser_cookies = json.loads(cookies_json)
        return {cookie["name"]: cookie["value"] for cookie in browser_cookies}
    return {}


class AngelsLoveSpider(scrapy.Spider):
    name = "angelslove"

    def __init__(self, mode="releases", site="angelslove", scan_all=False, *args, **kwargs):
        """Initialize spider with mode and site parameters.

        Args:
            mode: 'releases' (default), 'performers', or 'all'
            site: 'angelslove' (default) or 'sensuallove'
            scan_all: If True, scan ALL pages looking for new releases (don't stop early)
        """
        super().__init__(*args, **kwargs)
        self.mode = mode
        self.scan_all = scan_all in (True, "True", "true", "1", 1)
        if mode not in ["releases", "performers", "all"]:
            raise ValueError(f"Invalid mode: {mode}. Must be 'releases', 'performers', or 'all'")

        # Load site-specific configuration
        if site not in SITE_CONFIGS:
            raise ValueError(
                f"Invalid site: {site}. Must be one of: {', '.join(SITE_CONFIGS.keys())}"
            )

        self.site_key = site
        self.site_config = SITE_CONFIGS[site]
        self.base_url = self.site_config["base_url"]
        self.site_short_name = self.site_config["site_short_name"]
        self.allowed_domains = self.site_config["allowed_domains"]
        self.start_urls = [self.base_url]
        self.cookies = get_cookies_for_site(site)

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
        # Route based on mode
        if self.mode in ["releases", "all"]:
            # Request movies first, then photos
            yield scrapy.Request(
                url=f"{self.base_url}/members/content?page=1",
                callback=self.parse_list_page,
                cookies=self.cookies,
                meta={"page": 1, "content_type": "all"},
            )

        if self.mode in ["performers", "all"]:
            # Request performers listing
            yield scrapy.Request(
                url=f"{self.base_url}/members/girls?page=1",
                callback=self.parse_performers_page,
                cookies=self.cookies,
                meta={"page": 1},
            )

    def parse_list_page(self, response):
        """Parse a page of releases."""
        page_num = response.meta.get("page", 1)

        # Extract all content items from the grid
        # Note: Page has 3 grids (lg/md/mob for responsive). We only want the desktop (lg) one.
        content_items = response.css(".content-view-lg div.content-grid-item-wrapper")

        # Track counts for this page
        new_releases_count = 0
        existing_releases_count = 0

        # Collect release info for summary log
        release_lines = []

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
                content_type = "scene" if is_video else "gallery"

                # Check if this release already exists
                existing_release = self.existing_releases.get(external_id)
                performers_str = ", ".join(performers) if performers else "Unknown"

                if existing_release and not self.force_update:
                    existing_releases_count += 1
                    release_lines.append(f"  [EXISTS] {title} ({performers_str}) [{content_type}]")
                    continue

                # This is a new release
                new_releases_count += 1
                release_lines.append(f"  [NEW]    {title} ({performers_str}) [{content_type}]")

                # Yield request to appropriate detail page parser based on content type
                callback = self.parse_video_detail if is_video else self.parse_gallery_detail
                yield scrapy.Request(
                    url=f"{self.base_url}{item_link}",
                    callback=callback,
                    cookies=self.cookies,
                    meta={
                        "external_id": external_id,
                        "title": title,
                        "performers": performers,
                        "performer_urls": performer_urls,
                        "thumbnail": thumbnail,
                    },
                )

        # Log page summary with all releases
        releases_detail = "\n".join(release_lines) if release_lines else "  (no releases found)"
        self.logger.info(
            f"Page {page_num}: {new_releases_count} new, {existing_releases_count} existing "
            f"({len(content_items)} total)\n{releases_detail}"
        )

        # Handle pagination - extract next page if available
        # Give pagination requests lower priority so they're processed after all releases on current page
        page_options = response.css(".page-selector-select option::attr(data-href)").getall()
        if page_options:
            # Check if there's a next page
            current_page_index = page_num - 1
            if current_page_index + 1 < len(page_options):
                # Early stopping logic: if scan_all is False and entire page was existing releases,
                # stop pagination (assumes releases are ordered by date, newest first)
                if not self.scan_all and new_releases_count == 0 and existing_releases_count > 0:
                    self.logger.info(
                        f"Stopping: all releases on page {page_num} already exist. "
                        f"Use -a scan_all=1 to scan all pages."
                    )
                    return

                next_page_url = page_options[current_page_index + 1]
                self.logger.info(f"Found next page: {next_page_url}")
                yield scrapy.Request(
                    url=f"{self.base_url}{next_page_url}",
                    callback=self.parse_list_page,
                    cookies=self.cookies,
                    meta={"page": page_num + 1, "content_type": "all"},
                    priority=-page_num,  # Lower priority for pagination (higher page numbers = lower priority)
                )

        self.logger.info(f"Finished processing movies page {page_num}")

    def _create_performer_items(self, performers, performer_urls):
        """Create performer items from names and URLs."""
        performer_items = []
        for i, performer_name in enumerate(performers):
            performer_url = performer_urls[i] if i < len(performer_urls) else None
            performer_short_name = performer_url.split("/")[-1] if performer_url else None
            full_url = f"{self.base_url}{performer_url}" if performer_url else None

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
        list_thumbnail = response.meta["thumbnail"]

        self.logger.info(f"Parsing video detail page: {external_id} - {title}")

        # Check if we've been redirected to login page
        if "/login" in response.url:
            raise CloseSpider(
                f"Session expired: Redirected to login page for {external_id}. "
                f"Please update the {self.site_config['cookie_env_var']} environment variable with fresh cookies."
            )

        # Extract high-quality preview image from video player
        # The JW Player uses a background-image CSS property on .jw-preview element
        poster_style = response.css(".jw-preview::attr(style)").get()
        thumbnail = None
        if poster_style:
            # Extract URL from background-image: url("...")
            match = re.search(r'url\(["\']?([^"\'()]+)["\']?\)', poster_style)
            if match:
                thumbnail = match.group(1)
                self.logger.info(f"Found high-quality preview image: {thumbnail}")

        # Fallback to list thumbnail if we couldn't extract the video player poster
        if not thumbnail:
            thumbnail = list_thumbnail
            self.logger.warning("Could not extract video player poster, using list thumbnail")

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

        # If we couldn't extract a release date, skip this release
        if not detail_date:
            self.logger.error(
                f"No release date found for video {external_id}. Skipping this release. "
                "This might indicate a page structure change or missing data."
            )
            return

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

        # Get already downloaded files for this release (if any)
        downloaded_files = existing_release["downloaded_files"] if existing_release else set()

        # Add thumbnail as cover image
        if thumbnail:
            cover_file = AvailableImageFile(
                file_type="image",
                content_type="cover",
                variant="thumbnail",
                url=thumbnail,
            )
            available_files.append(cover_file)
            # Only add to download items if not already downloaded
            if (
                cover_file.file_type,
                cover_file.content_type,
                cover_file.variant,
            ) not in downloaded_files:
                download_items.append(
                    DirectDownloadItem(
                        release_id=str(release_id),
                        file_info=ItemAdapter(cover_file).asdict(),
                        url=cover_file.url,
                    )
                )
            else:
                self.logger.info(
                    f"Skipping already downloaded file: {cover_file.variant} ({cover_file.file_type}/{cover_file.content_type})"
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
            # Only add to download items if not already downloaded
            if (
                video_file.file_type,
                video_file.content_type,
                video_file.variant,
            ) not in downloaded_files:
                download_items.append(
                    DirectDownloadItem(
                        release_id=str(release_id),
                        file_info=ItemAdapter(video_file).asdict(),
                        url=video_file.url,
                    )
                )
            else:
                self.logger.info(
                    f"Skipping already downloaded file: {video_file.variant} ({video_file.file_type}/{video_file.content_type})"
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

        # Check if we've been redirected to login page
        if "/login" in response.url:
            raise CloseSpider(
                f"Session expired: Redirected to login page for {external_id}. "
                f"Please update the {self.site_config['cookie_env_var']} environment variable with fresh cookies."
            )

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

        # If we couldn't extract a release date, skip this release
        if not detail_date:
            self.logger.error(
                f"No release date found for gallery {external_id}. Skipping this release. "
                "This might indicate a page structure change or missing data."
            )
            return

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

        # Get already downloaded files for this release (if any)
        downloaded_files = existing_release["downloaded_files"] if existing_release else set()

        # Add thumbnail as cover image
        if thumbnail:
            cover_file = AvailableImageFile(
                file_type="image",
                content_type="cover",
                variant="thumbnail",
                url=thumbnail,
            )
            available_files.append(cover_file)
            # Only add to download items if not already downloaded
            if (
                cover_file.file_type,
                cover_file.content_type,
                cover_file.variant,
            ) not in downloaded_files:
                download_items.append(
                    DirectDownloadItem(
                        release_id=str(release_id),
                        file_info=ItemAdapter(cover_file).asdict(),
                        url=cover_file.url,
                    )
                )
            else:
                self.logger.info(
                    f"Skipping already downloaded file: {cover_file.variant} ({cover_file.file_type}/{cover_file.content_type})"
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
            # Only add to download items if not already downloaded
            if (
                gallery_file.file_type,
                gallery_file.content_type,
                gallery_file.variant,
            ) not in downloaded_files:
                download_items.append(
                    DirectDownloadItem(
                        release_id=str(release_id),
                        file_info=ItemAdapter(gallery_file).asdict(),
                        url=gallery_file.url,
                    )
                )
            else:
                self.logger.info(
                    f"Skipping already downloaded file: {gallery_file.variant} ({gallery_file.file_type}/{gallery_file.content_type})"
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

    def parse_performers_page(self, response):
        """Parse a page of performers/models."""
        page_num = response.meta.get("page", 1)
        self.logger.info(f"Parsing performers page {page_num}: {response.url}")

        # Extract all performer cards from the grid
        performer_cards = response.css('a[href*="/members/model/"]')

        self.logger.info(f"Found {len(performer_cards)} performers on page {page_num}")

        for card in performer_cards:
            # Extract performer data from the card
            performer_url = card.css("::attr(href)").get()
            performer_name = card.css(".content-tile-title::text").get()
            performer_image = card.css("img.thumb::attr(src)").get()
            performer_id = card.css(".elastic-model-tile::attr(data-id)").get()

            if performer_url and performer_name:
                # Extract slug from URL (e.g., /members/model/cherry-crush -> cherry-crush)
                performer_slug = performer_url.split("/")[-1]

                self.logger.info(
                    f"Found performer: {performer_name} (ID: {performer_id}, slug: {performer_slug})"
                )

                # Request the performer detail page
                yield scrapy.Request(
                    url=f"{self.base_url}{performer_url}",
                    callback=self.parse_performer_detail,
                    cookies=self.cookies,
                    meta={
                        "performer_name": performer_name,
                        "performer_slug": performer_slug,
                        "performer_id": performer_id,
                        "list_image": performer_image,
                    },
                )

        # Handle pagination - extract next page if available
        # Give pagination requests lower priority so they're processed after all performers on current page
        page_options = response.css(".page-selector-select option::attr(data-href)").getall()
        if page_options:
            # Check if there's a next page
            current_page_index = page_num - 1
            if current_page_index + 1 < len(page_options):
                next_page_url = page_options[current_page_index + 1]
                self.logger.info(f"Found next page: {next_page_url}")
                yield scrapy.Request(
                    url=f"{self.base_url}{next_page_url}",
                    callback=self.parse_performers_page,
                    cookies=self.cookies,
                    meta={"page": page_num + 1},
                    priority=-page_num,  # Lower priority for pagination (higher page numbers = lower priority)
                )

        self.logger.info(f"Finished processing performers page {page_num}")

    def parse_performer_detail(self, response):
        """Parse a performer detail page to extract images and metadata."""
        performer_name = response.meta["performer_name"]
        performer_slug = response.meta["performer_slug"]
        list_image = response.meta["list_image"]

        self.logger.info(f"Parsing performer detail page: {performer_slug} - {performer_name}")

        # Extract profile images - we want both left (main) and right (alternative) images
        # Image URL pattern: https://dd-models.wowgirls.com/{modelId}/{left|right}_960x1440.jpg
        profile_images = response.css(f'img[alt*="{performer_name}"]::attr(src)').getall()

        # Filter for left and right images
        left_image = None
        right_image = None
        for img_url in profile_images:
            if "left_" in img_url:
                left_image = img_url
            elif "right_" in img_url:
                right_image = img_url

        # If we didn't find left image in detail page, use the one from list view
        if not left_image and list_image:
            left_image = list_image

        # Create or get performer from database
        performer = get_or_create_performer(
            self.site.id,
            performer_slug,  # Use slug as short_name
            performer_name,
            response.url,
        )

        # Build image URLs list - left (main) image first, then right (alternative)
        image_urls = []
        if left_image:
            image_urls.append({"url": left_image, "type": "profile"})
        if right_image:
            image_urls.append({"url": right_image, "type": "profile-alt"})

        # Create PerformerItem
        performer_item = PerformerItem(
            performer=performer,
            image_urls=image_urls,
        )

        self.logger.info(
            f"Created performer item for {performer_name} with {len(image_urls)} images"
        )

        yield performer_item
