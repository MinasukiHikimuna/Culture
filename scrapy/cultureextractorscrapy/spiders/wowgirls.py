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


def get_cookies_for_site():
    """Load cookies from environment variable for wowgirls."""
    cookies_json = os.getenv("WOWGIRLS_COOKIES")
    if cookies_json:
        browser_cookies = json.loads(cookies_json)
        return {cookie["name"]: cookie["value"] for cookie in browser_cookies}
    return {}


class WowGirlsSpider(scrapy.Spider):
    name = "wowgirls"
    allowed_domains = [
        "venus.wowgirls.com",
        "content-video2.wowgirls.com",
        "content-photo2.wowgirls.com",
        "content-vthumbs2.wowgirls.com",
    ]

    def __init__(self, mode="releases", scan_all=False, *args, **kwargs):
        """Initialize spider with mode parameter.

        Args:
            mode: 'releases' (default), 'performers', or 'all'
            scan_all: If True, scan ALL pages looking for new releases (don't stop early)
        """
        super().__init__(*args, **kwargs)
        self.mode = mode
        self.scan_all = scan_all in (True, "True", "true", "1", 1)
        if mode not in ["releases", "performers", "all"]:
            raise ValueError(f"Invalid mode: {mode}. Must be 'releases', 'performers', or 'all'")

        self.base_url = "https://venus.wowgirls.com"
        self.site_short_name = "wowgirls"
        self.start_urls = [self.base_url]
        self.cookies = get_cookies_for_site()

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
            # Use /updates/ endpoint with site filter for WowGirls only (site=32)
            # This ensures we only scrape WowGirls content, not AllFineGirls or WowPorn
            # First, we need to set up the site filter by toggling on site=32
            yield scrapy.FormRequest(
                url=f"{self.base_url}/updates/cf",
                formdata={
                    "__operation": "toggle",
                    "__state": "sites=32",
                },
                callback=self.parse_updates_list,
                cookies=self.cookies,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                },
                meta={"page": 1, "site_filter_set": True},
            )

        if self.mode in ["performers", "all"]:
            # Request performers listing
            yield scrapy.Request(
                url=f"{self.base_url}/girls/",
                callback=self.parse_performers_page,
                cookies=self.cookies,
                meta={"page": 1},
            )

    def parse_updates_list(self, response):
        """Parse the updates list page (combined films and galleries, filtered by site)."""
        page_num = response.meta.get("page", 1)

        # Check if we've been redirected to login page
        if "/login" in response.url or "auth.wowgirls.com" in response.url:
            raise CloseSpider(
                "Session expired: Redirected to login page. "
                "Please update the WOWGIRLS_COOKIES environment variable with fresh cookies."
            )

        # Extract all content items (both films and galleries)
        content_items = response.css("div.content_item")

        # Track counts for this page
        new_releases_count = 0
        existing_releases_count = 0
        release_lines = []

        for item in content_items:
            # Determine if it's a film or gallery based on class
            is_film = "ct_video" in (item.css("::attr(class)").get() or "")
            is_gallery = "ct_photo" in (item.css("::attr(class)").get() or "")

            if is_film:
                item_link = item.css('a[href*="/film/"]')
                item_url = item_link.css("::attr(href)").get()
                if not item_url:
                    continue
                match = re.match(r"/film/(\w+)/", item_url)
                content_type = "film"
            elif is_gallery:
                item_link = item.css('a[href*="/gallery/"]')
                item_url = item_link.css("::attr(href)").get()
                if not item_url:
                    continue
                match = re.match(r"/gallery/(\w+)/", item_url)
                content_type = "gallery"
            else:
                continue

            if not match:
                continue
            short_name = match.group(1)

            # Extract title from the title link
            title_link = item.css("a.title")
            title = title_link.css("::text").get()
            if title:
                title = title.strip()
            else:
                # Fallback to image alt
                title = item.css("img::attr(alt)").get() or short_name

            # Check if this release already exists
            existing_release = self.existing_releases.get(short_name)

            if existing_release and not self.force_update:
                existing_releases_count += 1
                release_lines.append(f"  [EXISTS] {title} [{content_type}]")
                continue

            # This is a new release
            new_releases_count += 1
            release_lines.append(f"  [NEW]    {title} [{content_type}]")

            # Request detail page with appropriate callback
            if is_film:
                yield scrapy.Request(
                    url=f"{self.base_url}{item_url}",
                    callback=self.parse_film_detail,
                    cookies=self.cookies,
                    meta={
                        "short_name": short_name,
                        "title": title,
                    },
                )
            else:
                yield scrapy.Request(
                    url=f"{self.base_url}{item_url}",
                    callback=self.parse_gallery_detail,
                    cookies=self.cookies,
                    meta={
                        "short_name": short_name,
                        "title": title,
                    },
                )

        # Log page summary
        releases_detail = "\n".join(release_lines) if release_lines else "  (no releases found)"
        self.logger.info(
            f"Updates page {page_num}: {new_releases_count} new, {existing_releases_count} existing\n{releases_detail}"
        )

        # Handle pagination
        next_page = self._get_next_page(response, page_num)
        if next_page:
            # Early stopping logic
            if not self.scan_all and new_releases_count == 0 and existing_releases_count > 0:
                self.logger.info(
                    f"Stopping updates: all releases on page {page_num} already exist. "
                    f"Use -a scan_all=1 to scan all pages."
                )
                return

            # Use /updates/cf endpoint for pagination (site filter is maintained in session)
            yield scrapy.FormRequest(
                url=f"{self.base_url}/updates/cf",
                formdata={
                    "__operation": "modify",
                    "__state": f"paginator.page={next_page}",
                },
                callback=self.parse_updates_list,
                cookies=self.cookies,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                },
                meta={"page": next_page},
                priority=-page_num,
            )

    def parse_films_list(self, response):
        """Parse the films list page."""
        page_num = response.meta.get("page", 1)

        # Check if we've been redirected to login page
        if "/login" in response.url or "auth.wowgirls.com" in response.url:
            raise CloseSpider(
                "Session expired: Redirected to login page. "
                "Please update the WOWGIRLS_COOKIES environment variable with fresh cookies."
            )

        # Extract film items from the list
        film_items = response.css('a[href*="/film/"]')

        # Track counts for this page
        new_releases_count = 0
        existing_releases_count = 0
        release_lines = []

        # Process unique film URLs (dedupe since title appears twice)
        seen_urls = set()
        for item in film_items:
            item_url = item.css("::attr(href)").get()
            if not item_url or item_url in seen_urls or not item_url.startswith("/film/"):
                continue
            seen_urls.add(item_url)

            # Extract short_name (ID) from URL: /film/{id}/{slug}
            match = re.match(r"/film/(\w+)/", item_url)
            if not match:
                continue
            short_name = match.group(1)

            # Extract title
            title = item.css("::text").get() or item.css("img::attr(alt)").get()
            if title:
                title = title.strip()

            # Check if this release already exists
            existing_release = self.existing_releases.get(short_name)

            if existing_release and not self.force_update:
                existing_releases_count += 1
                release_lines.append(f"  [EXISTS] {title} [film]")
                continue

            # This is a new release
            new_releases_count += 1
            release_lines.append(f"  [NEW]    {title} [film]")

            # Request detail page
            yield scrapy.Request(
                url=f"{self.base_url}{item_url}",
                callback=self.parse_film_detail,
                cookies=self.cookies,
                meta={
                    "short_name": short_name,
                    "title": title,
                },
            )

        # Log page summary
        releases_detail = "\n".join(release_lines) if release_lines else "  (no releases found)"
        self.logger.info(
            f"Films page {page_num}: {new_releases_count} new, {existing_releases_count} existing\n{releases_detail}"
        )

        # Handle pagination
        next_page = self._get_next_page(response, page_num)
        if next_page:
            # Early stopping logic
            if not self.scan_all and new_releases_count == 0 and existing_releases_count > 0:
                self.logger.info(
                    f"Stopping films: all releases on page {page_num} already exist. "
                    f"Use -a scan_all=1 to scan all pages."
                )
                return

            # The site uses POST requests to /films/cf with form data for pagination
            yield scrapy.FormRequest(
                url=f"{self.base_url}/films/cf",
                formdata={
                    "__operation": "modify",
                    "__state": f"paginator.page={next_page}",
                },
                callback=self.parse_films_list,
                cookies=self.cookies,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                },
                meta={"page": next_page},
                priority=-page_num,
            )

    def parse_galleries_list(self, response):
        """Parse the galleries list page."""
        page_num = response.meta.get("page", 1)

        # Check if we've been redirected to login page
        if "/login" in response.url or "auth.wowgirls.com" in response.url:
            raise CloseSpider(
                "Session expired: Redirected to login page. "
                "Please update the WOWGIRLS_COOKIES environment variable with fresh cookies."
            )

        # Extract gallery items from the list
        gallery_items = response.css('a[href*="/gallery/"]')

        # Track counts for this page
        new_releases_count = 0
        existing_releases_count = 0
        release_lines = []

        # Process unique gallery URLs (dedupe since title appears twice)
        seen_urls = set()
        for item in gallery_items:
            item_url = item.css("::attr(href)").get()
            if not item_url or item_url in seen_urls or not item_url.startswith("/gallery/"):
                continue
            seen_urls.add(item_url)

            # Extract short_name (ID) from URL: /gallery/{id}/{slug}
            match = re.match(r"/gallery/(\w+)/", item_url)
            if not match:
                continue
            short_name = match.group(1)

            # Extract title
            title = item.css("::text").get() or item.css("img::attr(alt)").get()
            if title:
                title = title.strip()

            # Check if this release already exists
            existing_release = self.existing_releases.get(short_name)

            if existing_release and not self.force_update:
                existing_releases_count += 1
                release_lines.append(f"  [EXISTS] {title} [gallery]")
                continue

            # This is a new release
            new_releases_count += 1
            release_lines.append(f"  [NEW]    {title} [gallery]")

            # Request detail page
            yield scrapy.Request(
                url=f"{self.base_url}{item_url}",
                callback=self.parse_gallery_detail,
                cookies=self.cookies,
                meta={
                    "short_name": short_name,
                    "title": title,
                },
            )

        # Log page summary
        releases_detail = "\n".join(release_lines) if release_lines else "  (no releases found)"
        self.logger.info(
            f"Galleries page {page_num}: {new_releases_count} new, {existing_releases_count} existing\n{releases_detail}"
        )

        # Handle pagination
        next_page = self._get_next_page(response, page_num)
        if next_page:
            # Early stopping logic
            if not self.scan_all and new_releases_count == 0 and existing_releases_count > 0:
                self.logger.info(
                    f"Stopping galleries: all releases on page {page_num} already exist. "
                    f"Use -a scan_all=1 to scan all pages."
                )
                return

            # The site uses POST requests to /galleries/cf with form data for pagination
            yield scrapy.FormRequest(
                url=f"{self.base_url}/galleries/cf",
                formdata={
                    "__operation": "modify",
                    "__state": f"paginator.page={next_page}",
                },
                callback=self.parse_galleries_list,
                cookies=self.cookies,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                },
                meta={"page": next_page},
                priority=-page_num,
            )

    def _get_next_page(self, response, current_page):
        """Extract next page number from pagination."""
        # Look for pagination span elements with class "page"
        # They have data-ca-state="paginator.page=N" attribute
        page_spans = response.css("span.page::text").getall()
        self.logger.info(f"Pagination spans found: {page_spans}")
        # Filter to numeric values
        page_numbers = [int(p.strip()) for p in page_spans if p.strip().isdigit()]
        self.logger.info(f"Page numbers: {page_numbers}, current_page: {current_page}")
        if page_numbers:
            max_page = max(page_numbers)
            if current_page < max_page:
                self.logger.info(f"Next page: {current_page + 1}")
                return current_page + 1
        self.logger.info("No next page found")
        return None

    def parse_film_detail(self, response):
        """Parse a film detail page to extract metadata and download options."""
        short_name = response.meta["short_name"]
        title = response.meta["title"]

        self.logger.info(f"Parsing film detail page: {short_name} - {title}")

        # Check if we've been redirected to login page
        if "/login" in response.url or "auth.wowgirls.com" in response.url:
            raise CloseSpider(
                f"Session expired: Redirected to login page for {short_name}. "
                "Please update the WOWGIRLS_COOKIES environment variable with fresh cookies."
            )

        # Extract performer info
        performer_links = response.css('a[href*="/girl/"]')
        performers = []
        performer_urls = []
        for link in performer_links:
            name = link.css("::text").get()
            url = link.css("::attr(href)").get()
            if name and url and url.startswith("/girl/"):
                performers.append(name.strip())
                performer_urls.append(url)

        # Extract date from metadata (format: "01 Dec 2025")
        date_text = response.xpath("//li[contains(text(), ' 20')]/text()").get()
        release_date = None
        if date_text:
            try:
                parsed_date = datetime.strptime(date_text.strip(), "%d %b %Y").date()
                release_date = parsed_date.isoformat()
            except ValueError:
                self.logger.warning(f"Could not parse date: {date_text}")

        # Extract duration (format: "00:27:43")
        duration_text = response.xpath("//li[contains(text(), ':')]/text()").re_first(
            r"\d+:\d+:\d+"
        )
        duration_seconds = 0
        if duration_text:
            parts = duration_text.split(":")
            if len(parts) == 3:
                duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                duration_seconds = int(parts[0]) * 60 + int(parts[1])

        # Extract tags
        tag_links = response.css('a[href*="/updates/genre/"]')
        tags = [link.css("::text").get().strip() for link in tag_links if link.css("::text").get()]

        # Extract download options
        download_files = []
        # Get all download list items (each contains an <a> and details <div>)
        download_items = response.css(".ct_dl_items li")

        for item in download_items:
            link = item.css('a[href*="content-video2.wowgirls.com/download/"]')
            if not link:
                continue

            url = link.css("::attr(href)").get()
            # Resolution is inside <span class="title">
            resolution_text = link.css("span.title::text").get()
            # Details are in sibling <div class="ct_dl_details">
            details_div = item.css("div.ct_dl_details")
            codec_text = details_div.css("span.format::text").get()
            fps_text = details_div.css("span.fps::text").get()
            size_text = details_div.css("span.size::text").get()

            if not url or not resolution_text:
                continue

            # Parse resolution
            res_match = re.match(r"(\d+)\s*x\s*(\d+)", resolution_text.strip())
            if not res_match:
                continue
            width = int(res_match.group(1))
            height = int(res_match.group(2))

            # Parse codec from format text (h264 -> H.264, hevc -> H.265)
            codec = "H.264"
            if codec_text:
                if "hevc" in codec_text.lower():
                    codec = "H.265"
                elif "h264" in codec_text.lower():
                    codec = "H.264"

            # Parse fps from fps text (e.g., "60fps" -> 60)
            fps = 30
            if fps_text:
                fps_match = re.search(r"(\d+)", fps_text)
                if fps_match:
                    fps = int(fps_match.group(1))

            # Parse file size from size text (e.g., "2.36Gb" or "480Mb")
            file_size = None
            if size_text:
                size_match = re.search(r"([\d.]+)(Gb|Mb)", size_text)
                if size_match:
                    size_value = float(size_match.group(1))
                    size_unit = size_match.group(2)
                    if size_unit == "Gb":
                        file_size = size_value * 1024 * 1024 * 1024
                    else:
                        file_size = size_value * 1024 * 1024

            # Format variant to match existing database format: "H.264 1920x1080 60fps"
            variant = f"{codec} {width}x{height} {fps}fps"

            download_files.append(
                {
                    "variant": variant,
                    "url": url,
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "codec": codec,
                    "file_size": file_size,
                }
            )

        # Extract preview image URL
        thumbnail = response.css('img[src*="content-vthumbs"]::attr(src)').get()

        if not release_date:
            self.logger.error(
                f"No release date found for film {short_name}. Skipping this release."
            )
            return

        # Create performer and tag items
        performer_items = self._create_performer_items(performers, performer_urls)
        tag_items = self._create_tag_items(tags)

        # Check if this release already exists
        existing_release = self.existing_releases.get(short_name)
        release_id = existing_release["uuid"] if existing_release else newnewid.uuid7()

        # Create available files list and download items
        available_files = []
        download_items = []

        # Get already downloaded files for this release (if any)
        downloaded_files = existing_release["downloaded_files"] if existing_release else set()

        # Add preview image
        if thumbnail:
            cover_file = AvailableImageFile(
                file_type="image",
                content_type="scene",
                variant="preview",
                url=thumbnail,
            )
            available_files.append(cover_file)
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

        # Add all video files to available_files
        for df in download_files:
            video_file = AvailableVideoFile(
                file_type="video",
                content_type="scene",
                variant=df["variant"],
                url=df["url"],
                resolution_width=df["width"],
                resolution_height=df["height"],
                file_size=df["file_size"],
                fps=df["fps"],
                codec=df["codec"],
            )
            available_files.append(video_file)

        # Add only the highest quality video for download
        # TEMPORARY: Only download if this release has NO video downloads at all
        has_any_video_download = any(
            ft == "video" for (ft, ct, v) in downloaded_files
        )

        if download_files and not has_any_video_download:
            # Sort by resolution (width * height) descending, prefer H.265
            sorted_downloads = sorted(
                download_files,
                key=lambda x: (x["width"] * x["height"], x["codec"] == "H.265", x["fps"]),
                reverse=True,
            )
            best_download = sorted_downloads[0]

            video_file = AvailableVideoFile(
                file_type="video",
                content_type="scene",
                variant=best_download["variant"],
                url=best_download["url"],
                resolution_width=best_download["width"],
                resolution_height=best_download["height"],
                file_size=best_download["file_size"],
                fps=best_download["fps"],
                codec=best_download["codec"],
            )

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
        elif has_any_video_download:
            self.logger.info(f"Skipping video download for {short_name} - already has video downloads")

        # Create post data for json_document
        post_data = {
            "external_id": short_name,
            "title": title,
            "performers": [
                {"name": p.name, "short_name": p.short_name, "url": p.url} for p in performer_items
            ],
            "tags": [{"name": t.name, "short_name": t.short_name} for t in tag_items],
            "release_date": release_date,
            "thumbnail": thumbnail,
            "duration": duration_seconds,
            "download_files": download_files,
        }

        # Create and yield the ReleaseItem
        release_item = ReleaseItem(
            id=release_id,
            release_date=release_date,
            short_name=short_name,
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
        yield from download_items

    def parse_gallery_detail(self, response):
        """Parse a gallery detail page to extract metadata and download options."""
        short_name = response.meta["short_name"]
        title = response.meta["title"]

        self.logger.info(f"Parsing gallery detail page: {short_name} - {title}")

        # Check if we've been redirected to login page
        if "/login" in response.url or "auth.wowgirls.com" in response.url:
            raise CloseSpider(
                f"Session expired: Redirected to login page for {short_name}. "
                "Please update the WOWGIRLS_COOKIES environment variable with fresh cookies."
            )

        # Extract performer info
        performer_links = response.css('a[href*="/girl/"]')
        performers = []
        performer_urls = []
        for link in performer_links:
            name = link.css("::text").get()
            url = link.css("::attr(href)").get()
            if name and url and url.startswith("/girl/"):
                performers.append(name.strip())
                performer_urls.append(url)

        # Extract date from metadata (format: "02 Dec 2025")
        date_text = response.xpath("//li[contains(text(), ' 20')]/text()").get()
        release_date = None
        if date_text:
            try:
                parsed_date = datetime.strptime(date_text.strip(), "%d %b %Y").date()
                release_date = parsed_date.isoformat()
            except ValueError:
                self.logger.warning(f"Could not parse date: {date_text}")

        # Extract image count
        image_count = response.xpath("//li[not(contains(text(), ' '))]/text()").re_first(r"^\d+$")

        # Extract tags
        tag_links = response.css('a[href*="/updates/genre/"]')
        tags = [link.css("::text").get().strip() for link in tag_links if link.css("::text").get()]

        # Extract download options
        download_files = []
        download_links = response.css('a[href*="content-photo2.wowgirls.com/zip/"]')

        for link in download_links:
            url = link.css("::attr(href)").get()
            variant_text = link.css("*::text").get()  # e.g., "4000px" or "Original"
            info_text = link.xpath("following-sibling::*[1]/text()").get()  # e.g., "jpeg • 117Mb"

            if not url or not variant_text:
                continue

            variant = variant_text.strip()
            file_size = None

            if info_text:
                # Extract file size
                size_match = re.search(r"([\d.]+)(Gb|Mb)", info_text)
                if size_match:
                    size_value = float(size_match.group(1))
                    size_unit = size_match.group(2)
                    if size_unit == "Gb":
                        file_size = size_value * 1024 * 1024 * 1024
                    else:
                        file_size = size_value * 1024 * 1024

            # Extract resolution width from variant if numeric
            resolution_width = None
            if variant != "Original":
                width_match = re.match(r"(\d+)px", variant)
                if width_match:
                    resolution_width = int(width_match.group(1))

            download_files.append(
                {
                    "variant": variant,
                    "url": url,
                    "resolution_width": resolution_width,
                    "file_size": file_size,
                }
            )

        if not release_date:
            self.logger.error(
                f"No release date found for gallery {short_name}. Skipping this release."
            )
            return

        # Create performer and tag items
        performer_items = self._create_performer_items(performers, performer_urls)
        tag_items = self._create_tag_items(tags)

        # Check if this release already exists
        existing_release = self.existing_releases.get(short_name)
        release_id = existing_release["uuid"] if existing_release else newnewid.uuid7()

        # Create available files list and download items
        available_files = []
        download_items = []

        # Get already downloaded files for this release (if any)
        downloaded_files = existing_release["downloaded_files"] if existing_release else set()

        # Add all gallery files to available_files
        for df in download_files:
            gallery_file = AvailableGalleryZipFile(
                file_type="zip",
                content_type="gallery",
                variant=df["variant"],
                url=df["url"],
                resolution_width=df["resolution_width"],
                file_size=df["file_size"],
            )
            available_files.append(gallery_file)

        # Add only the highest quality (Original) for download
        # TEMPORARY: Only download if this release has NO gallery/zip downloads at all
        has_any_gallery_download = any(
            ft == "zip" for (ft, ct, v) in downloaded_files
        )

        original_download = next((df for df in download_files if df["variant"] == "Original"), None)
        if original_download and not has_any_gallery_download:
            gallery_file = AvailableGalleryZipFile(
                file_type="zip",
                content_type="gallery",
                variant=original_download["variant"],
                url=original_download["url"],
                resolution_width=original_download["resolution_width"],
                file_size=original_download["file_size"],
            )

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
        elif has_any_gallery_download:
            self.logger.info(f"Skipping gallery download for {short_name} - already has gallery downloads")

        # Create post data for json_document
        post_data = {
            "external_id": short_name,
            "title": title,
            "performers": [
                {"name": p.name, "short_name": p.short_name, "url": p.url} for p in performer_items
            ],
            "tags": [{"name": t.name, "short_name": t.short_name} for t in tag_items],
            "release_date": release_date,
            "image_count": image_count,
            "download_files": download_files,
        }

        # Create and yield the ReleaseItem
        release_item = ReleaseItem(
            id=release_id,
            release_date=release_date,
            short_name=short_name,
            name=title,
            url=response.url,
            description="",
            duration=-1,  # Galleries don't have duration
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
        yield from download_items

    def _create_performer_items(self, performers, performer_urls):
        """Create performer items from names and URLs."""
        performer_items = []
        for i, performer_name in enumerate(performers):
            performer_url = performer_urls[i] if i < len(performer_urls) else None

            # Extract short_name from URL: /girl/{id}/{slug} -> {id}/{slug}
            performer_short_name = None
            if performer_url:
                match = re.match(r"/girl/(\w+/[\w-]+)", performer_url)
                if match:
                    performer_short_name = match.group(1)

            full_url = performer_url  # Keep as relative URL like existing data

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
            # Tags use the tag name as short_name (matching existing data)
            tag_short_name = tag_name

            # Create or get tag from database
            tag = get_or_create_tag(self.site.id, tag_short_name, tag_name.strip(), None)
            tag_items.append(tag)
        return tag_items

    def parse_performers_page(self, response):
        """Parse a page of performers/models."""
        page_num = response.meta.get("page", 1)
        self.logger.info(f"Parsing performers page {page_num}: {response.url}")

        # Check if we've been redirected to login page
        if "/login" in response.url or "auth.wowgirls.com" in response.url:
            raise CloseSpider(
                "Session expired: Redirected to login page. "
                "Please update the WOWGIRLS_COOKIES environment variable with fresh cookies."
            )

        # Extract all performer cards from the grid
        # Only select links that have an image (actual performer cards, not genre tags)
        performer_cards = response.css('a[href*="/girl/"]:has(img)')

        seen_urls = set()
        for card in performer_cards:
            performer_url = card.css("::attr(href)").get()
            if (
                not performer_url
                or performer_url in seen_urls
                or not performer_url.startswith("/girl/")
                or "/genre" in performer_url  # Skip genre filter links
            ):
                continue
            seen_urls.add(performer_url)

            performer_name = card.css("::text").get() or card.css("img::attr(alt)").get()

            if performer_url and performer_name:
                # Extract short_name from URL: /girl/{hex_id}/{slug}
                # Hex IDs have letters, genre IDs are purely numeric
                match = re.match(r"/girl/([a-z0-9]+/[\w-]+)", performer_url)
                if not match:
                    continue
                performer_short_name = match.group(1)

                self.logger.info(
                    f"Found performer: {performer_name.strip()} (short_name: {performer_short_name})"
                )

                # Visit detail page to get higher quality profile image
                yield scrapy.Request(
                    url=f"{self.base_url}{performer_url}",
                    callback=self.parse_performer_detail,
                    cookies=self.cookies,
                    meta={
                        "performer_name": performer_name.strip(),
                        "performer_short_name": performer_short_name,
                    },
                )

        # Handle pagination using AJAX POST requests
        next_page = self._get_next_page(response, page_num)
        if next_page:
            # The site uses POST requests to /girls/cf with form data for pagination
            yield scrapy.FormRequest(
                url=f"{self.base_url}/girls/cf",
                formdata={
                    "__operation": "modify",
                    "__state": f"paginator.page={next_page}",
                },
                callback=self.parse_performers_page,
                cookies=self.cookies,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                },
                meta={"page": next_page},
                priority=-page_num,
            )

    def parse_performer_detail(self, response):
        """Parse a performer detail page to extract the high-quality profile image."""
        performer_name = response.meta["performer_name"]
        performer_short_name = response.meta["performer_short_name"]

        self.logger.info(
            f"Parsing performer detail page: {performer_short_name} - {performer_name}"
        )

        # Get the main profile image (higher quality than list page)
        # Look for the image in content-models2 domain with icon_ prefix
        profile_image = response.css('img[src*="content-models2"][src*="icon_"]::attr(src)').get()

        # Create or get performer from database
        performer = get_or_create_performer(
            self.site.id,
            performer_short_name,
            performer_name,
            response.url,
        )

        # Build image URLs list (just the main profile image)
        image_urls = []
        if profile_image:
            image_urls.append({"url": profile_image, "type": "profile"})

        # Create PerformerItem
        performer_item = PerformerItem(
            performer=performer,
            image_urls=image_urls,
        )

        self.logger.info(f"Created performer item for {performer_name} with profile image")

        yield performer_item
