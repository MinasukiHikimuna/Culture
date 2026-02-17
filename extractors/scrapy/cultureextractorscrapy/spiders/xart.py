import json
import os
import re
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
    PerformerItem,
    ReleaseItem,
)
from cultureextractorscrapy.spiders.database import (
    get_existing_releases_with_status,
    get_or_create_performer,
    get_site_item,
)
from cultureextractorscrapy.utils import get_log_filename

load_dotenv()

BASE_URL = "https://www.x-art.com/members"

# Category slugs to skip when parsing performers (these are category pages, not individual models)
CATEGORY_SLUGS = {
    "blondes",
    "brunettes",
    "redheads",
    "all+models",
    "all-models",
}


def get_cookies():
    """Load cookies from environment variable.

    Returns tuple of (scrapy_cookies, requests_cookies_dict)
    """
    cookies_json = os.getenv("XART_COOKIES")
    if not cookies_json:
        raise ValueError("XART_COOKIES environment variable is required")
    cookies_list = json.loads(cookies_json)
    # Convert to dict format for requests library
    cookies_dict = {c["name"]: c["value"] for c in cookies_list}
    return cookies_list, cookies_dict


class XArtSpider(scrapy.Spider):
    name = "xart"
    allowed_domains = ["x-art.com"]
    site_short_name = "xart"

    def __init__(self, mode="performers", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = mode
        self.seen_slugs: set[str] = set()
        cookies_list, cookies_dict = get_cookies()
        self.cookies_list = cookies_list  # For Scrapy requests
        self.cookies = cookies_dict  # For requests library (used by pipelines)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)

        # Set the log file
        crawler.settings.set("LOG_FILE", get_log_filename(spider.name))

        # Get force_update setting
        spider.force_update = crawler.settings.getbool("FORCE_UPDATE", False)

        # Load site from database
        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(
                f"Site with short_name '{spider.site_short_name}' not found in the database. "
                "Create it first with: uv run culture ce sites create xart 'X-Art' https://www.x-art.com/members/"
            )
        spider.site = site_item

        # Get existing releases with their download status
        spider.existing_releases = get_existing_releases_with_status(site_item.id)

        return spider

    MAX_PAGES = 200

    def _follow_next_page(self, response, callback):
        """Follow the next pagination link if one exists."""
        current_page = response.meta.get("page", 1)
        if current_page >= self.MAX_PAGES:
            self.logger.warning(f"Reached max page limit ({self.MAX_PAGES}), stopping pagination")
            return None
        next_page_link = response.xpath(
            f'//nav[@aria-label="Page navigation"]//a[normalize-space(text())="{current_page + 1}"]/@href'
        ).get()
        if next_page_link:
            self.logger.info(f"Found next page: {current_page + 1} -> {next_page_link}")
            return scrapy.Request(
                url=response.urljoin(next_page_link),
                callback=callback,
                cookies=self.cookies_list,
                meta={"page": current_page + 1},
            )
        return None

    async def start(self):
        if self.mode == "performers":
            # Start at the models page
            yield scrapy.Request(
                url=f"{BASE_URL}/models",
                callback=self.parse_models_page,
                cookies=self.cookies_list,
                meta={"page": 1},
            )
        elif self.mode == "releases":
            # Start at the updates page (videos + galleries)
            yield scrapy.Request(
                url=f"{BASE_URL}/updates",
                callback=self.parse_updates_page,
                cookies=self.cookies_list,
                meta={"page": 1},
            )
        else:
            self.logger.error(f"Unknown mode: {self.mode}")

    def parse_models_page(self, response):
        """Parse the models list page and extract model links."""
        # Extract model cards using XPath - links that contain a figure with h1
        # This filters out category links like "blondes", "brunettes" etc.
        model_cards = response.xpath("//a[.//figure//h1]")

        for card in model_cards:
            href = card.attrib.get("href", "")
            if "/members/models/" not in href:
                continue

            # Extract slug from URL
            slug = href.rstrip("/").split("/")[-1]
            # Skip pagination links and category slugs
            if "+" in slug or slug in CATEGORY_SLUGS:
                continue

            model_url = f"{BASE_URL}/models/{slug}"
            self.logger.info(f"Found model: {slug} -> {model_url}")

            yield scrapy.Request(
                url=model_url,
                callback=self.parse_model,
                cookies=self.cookies_list,
                meta={"slug": slug},
            )

        # Handle pagination
        next_req = self._follow_next_page(response, self.parse_models_page)
        if next_req:
            yield next_req

    def parse_model(self, response):
        """Parse a model detail page and extract performer data."""
        slug = response.meta["slug"]

        # Extract name from h1
        name = response.css("h1::text").get()
        name = name.strip() if name else slug.replace("-", " ").title()

        # Extract age - look for "Age: X" pattern
        age_text = response.css('h2:contains("Age:")::text').get()
        age = None
        if age_text:
            age = age_text.replace("Age:", "").strip()

        # Extract country - look for "Country: X" pattern
        country_text = response.css('h2:contains("Country:")::text').get()
        country = None
        if country_text:
            country = country_text.replace("Country:", "").strip()

        # Extract bio/description
        bio_text = ""
        # Look for the description in various possible locations
        description_elements = response.css("div > p::text, div.record-models + div::text").getall()
        if description_elements:
            bio_text = " ".join(description_elements).strip()

        # Try alternative: look for text after the rating section
        if not bio_text:
            # The bio appears to be in a generic div after ratings
            all_text = response.css("div::text").getall()
            for text in all_text:
                text = text.strip()
                if len(text) > 50 and "vote" not in text.lower():
                    bio_text = text
                    break

        # Extract profile image URL
        profile_img = response.css('img[alt="thumb"]::attr(src)').get()
        if not profile_img:
            profile_img = response.css("img::attr(src)").get()

        self.logger.info(f"Parsed model: {name}")
        self.logger.info(f"  Slug: {slug}")
        self.logger.info(f"  Age: {age}")
        self.logger.info(f"  Country: {country}")
        self.logger.info(f"  Bio: {bio_text[:100] if bio_text else 'N/A'}...")
        self.logger.info(f"  Profile image: {profile_img}")

        # Create or get performer from database
        performer_url = f"{BASE_URL}/models/{slug}"
        performer = get_or_create_performer(
            self.site.id,
            slug,
            name,
            performer_url,
        )

        # Prepare image URLs for download
        image_urls = []
        if profile_img:
            image_urls.append({"url": profile_img, "type": "profile"})

        # Yield PerformerItem to trigger image download
        yield PerformerItem(
            performer=performer,
            image_urls=image_urls,
        )

    def parse_updates_page(self, response):
        """Parse the updates list page and extract video/gallery links."""
        # Find all release links (videos and galleries)
        release_links = response.xpath("//a[contains(@href, '/members/videos/') or contains(@href, '/members/galleries/')]")

        for link in release_links:
            href = link.attrib.get("href", "")

            # Determine content type from URL
            if "/members/videos/" in href:
                content_type = "video"
                callback = self.parse_video
            elif "/members/galleries/" in href:
                content_type = "gallery"
                callback = self.parse_gallery
            else:
                continue

            # Extract slug from URL and append content type suffix
            raw_slug = href.rstrip("/").split("/")[-1]
            if not raw_slug or "+" in raw_slug:
                continue
            slug = f"{raw_slug}-{content_type}"

            # Skip if we already yielded a request for this slug in this crawl
            if slug in self.seen_slugs:
                continue

            # Check if we already have this release
            existing_release = self.existing_releases.get(slug)
            has_no_downloads = existing_release and not existing_release["downloaded_files"]
            if existing_release and not self.force_update and not has_no_downloads:
                self.logger.info(f"Skipping existing release: {slug}")
                continue
            if has_no_downloads:
                self.logger.info(f"Re-processing release with no downloads: {slug}")

            # Build URL from the raw slug (without suffix)
            url_path = "galleries" if content_type == "gallery" else f"{content_type}s"
            release_url = f"{BASE_URL}/{url_path}/{raw_slug}"
            self.logger.info(f"Found {content_type}: {slug} -> {release_url}")

            self.seen_slugs.add(slug)
            yield scrapy.Request(
                url=release_url,
                callback=callback,
                cookies=self.cookies_list,
                meta={"slug": slug, "content_type": content_type},
            )

        # Handle pagination
        next_req = self._follow_next_page(response, self.parse_updates_page)
        if next_req:
            yield next_req

    def parse_video(self, response):
        """Parse a video detail page and extract release data."""
        slug = response.meta["slug"]

        # Check if this release already exists
        existing_release = self.existing_releases.get(slug)
        release_id = existing_release["uuid"] if existing_release else newnewid.uuid7()

        # Extract title from h1
        title = response.css("h1::text").get()
        title = title.strip() if title else slug.replace("-", " ").title()

        # Extract date - format "Feb 05, 2026"
        date_text = response.xpath("//h2[re:match(text(), '(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)')]/text()").get()
        release_date = None
        if date_text:
            try:
                release_date = datetime.strptime(date_text.strip(), "%b %d, %Y").date()
            except ValueError:
                self.logger.warning(f"Could not parse date: {date_text}")

        # Extract description
        description = ""
        # The description is in a paragraph after the rating section
        desc_paragraphs = response.css("div > p::text").getall()
        for p in desc_paragraphs:
            p = p.strip()
            if len(p) > 50:
                description = p
                break

        # Extract performers
        performers = []
        performer_links = response.xpath("//h2[contains(text(), 'featuring')]/a")
        for plink in performer_links:
            performer_name = plink.css("::text").get()
            performer_href = plink.attrib.get("href", "")
            if performer_name and "/members/models/" in performer_href:
                performer_slug = performer_href.rstrip("/").split("/")[-1]
                # Skip category slugs (blondes, brunettes, etc.)
                if performer_slug in CATEGORY_SLUGS:
                    self.logger.warning(
                        f"Skipping category slug '{performer_slug}' for performer '{performer_name}'"
                    )
                    continue
                performer = get_or_create_performer(
                    self.site.id,
                    performer_slug,
                    performer_name.strip(),
                    f"{BASE_URL}/models/{performer_slug}",
                )
                performers.append(performer)

        # Parse video download URLs from the page HTML
        available_files = []
        download_items = []

        # Find all video download links (they're in the download modal)
        video_links = response.css('a[href*=".mp4"]')
        best_video = None
        best_resolution = 0

        for link in video_links:
            url = link.attrib.get("href", "")
            text = link.css("::text").getall()
            text = " ".join(t.strip() for t in text if t.strip())

            # Parse resolution from text like "3840x2160" or "1920x1080"
            width, height = 0, 0
            resolution_match = re.search(r"(\d+)x(\d+)", text)
            if resolution_match:
                width = int(resolution_match.group(1))
                height = int(resolution_match.group(2))

            # Determine variant from resolution
            if height >= 2160:
                variant = "4k"
            elif height >= 1080:
                variant = "1080"
            elif height >= 720:
                variant = "720"
            elif height >= 540:
                variant = "540"
            else:
                variant = "360"

            # Track the highest resolution video
            if height > best_resolution:
                best_resolution = height
                best_video = {
                    "url": url,
                    "variant": variant,
                    "width": width,
                    "height": height,
                }

        # Use the highest resolution video found
        if best_video:
            video_file = AvailableVideoFile(
                file_type="video",
                content_type="scene",
                variant=best_video["variant"],
                url=best_video["url"],
                resolution_width=best_video["width"],
                resolution_height=best_video["height"],
            )
            available_files.append(video_file)

            download_items.append(
                DirectDownloadItem(
                    release_id=release_id,
                    file_info=ItemAdapter(video_file).asdict(),
                    url=best_video["url"],
                )
            )
            video_url = best_video["url"]
        else:
            self.logger.warning(f"No video download links found for {slug}")
            video_url = None

        # Extract cover image URL from jwplayer script
        cover_url = None
        scripts = response.css("script::text").getall()
        for script in scripts:
            if "jwplayer" in script and "image:" in script:
                match = re.search(r'image:\s*"([^"]+)"', script)
                if match:
                    cover_url = match.group(1)
                    break

        if cover_url:
            cover_file = AvailableImageFile(
                file_type="image",
                content_type="cover",
                variant="cover",
                url=cover_url,
            )
            available_files.append(cover_file)

            download_items.append(
                DirectDownloadItem(
                    release_id=release_id,
                    file_info=ItemAdapter(cover_file).asdict(),
                    url=cover_file.url,
                )
            )

        self.logger.info(f"Parsed video: {title}")
        self.logger.info(f"  Slug: {slug}")
        self.logger.info(f"  Date: {release_date}")
        self.logger.info(f"  Performers: {[p.name for p in performers]}")
        self.logger.info(f"  Video URL: {video_url}")
        self.logger.info(f"  Cover URL: {cover_url}")

        # Create release item
        release_item = ReleaseItem(
            id=release_id,
            release_date=release_date.isoformat() if release_date else None,
            short_name=slug,
            name=title,
            url=response.url,
            description=description,
            duration=0,  # Deprecated field
            created=datetime.now(tz=UTC).astimezone(),
            last_updated=datetime.now(tz=UTC).astimezone(),
            performers=performers,
            tags=[],
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps({"slug": slug, "title": title}),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item

        # Filter download items to only yield missing files
        if existing_release and not self.force_update:
            downloaded_files = existing_release["downloaded_files"]
            missing_items = [
                item
                for item, af in zip(download_items, available_files, strict=True)
                if (af.file_type, af.content_type, af.variant) not in downloaded_files
            ]
            if missing_items:
                self.logger.info(f"Release {slug} exists but missing {len(missing_items)} files. Downloading them.")
            else:
                self.logger.info(f"Release {slug} already has all files downloaded. Skipping downloads.")
            yield from missing_items
        else:
            yield from download_items

    def parse_gallery(self, response):
        """Parse a gallery detail page and extract release data."""
        slug = response.meta["slug"]

        # Check if this release already exists
        existing_release = self.existing_releases.get(slug)
        release_id = existing_release["uuid"] if existing_release else newnewid.uuid7()

        # Extract title from h1
        title = response.css("h1::text").get()
        title = title.strip() if title else slug.replace("-", " ").title()

        # Extract date - format "<span>Date:</span> Feb 09, 2026"
        # The "Date:" label is in a span, so we use contains(., 'Date:') to match the whole element text
        date_h2 = response.xpath("//h2[contains(., 'Date:')]")
        release_date = None
        if date_h2:
            # Get all text content and extract the date part
            full_text = date_h2.xpath("string(.)").get()
            if full_text:
                try:
                    date_str = full_text.replace("Date:", "").strip()
                    release_date = datetime.strptime(date_str, "%b %d, %Y").date()
                except ValueError:
                    self.logger.warning(f"Could not parse date: {full_text}")

        # Extract description
        description = ""
        # The description is in a paragraph after the rating section
        desc_paragraphs = response.css("div > p::text").getall()
        for p in desc_paragraphs:
            p = p.strip()
            if len(p) > 50:
                description = p
                break

        # Extract performers - galleries use "Model(s):" (in a span) instead of "featuring"
        performers = []
        performer_links = response.xpath("//h2[contains(., 'Model(s):')]/a")
        for plink in performer_links:
            performer_name = plink.css("::text").get()
            performer_href = plink.attrib.get("href", "")
            if performer_name and "/members/models/" in performer_href:
                performer_slug = performer_href.rstrip("/").split("/")[-1]
                # Skip category slugs (blondes, brunettes, etc.)
                if performer_slug in CATEGORY_SLUGS:
                    self.logger.warning(
                        f"Skipping category slug '{performer_slug}' for performer '{performer_name}'"
                    )
                    continue
                performer = get_or_create_performer(
                    self.site.id,
                    performer_slug,
                    performer_name.strip(),
                    f"{BASE_URL}/models/{performer_slug}",
                )
                performers.append(performer)

        # Parse gallery ZIP download URLs from the page HTML
        available_files = []
        download_items = []

        # Find all ZIP download links
        zip_links = response.css('a[href*=".zip"]')
        best_zip = None
        best_resolution = 0

        for link in zip_links:
            url = link.attrib.get("href", "")
            text = link.css("::text").getall()
            text = " ".join(t.strip() for t in text if t.strip())

            # Parse resolution from text like "4000 pixels ZIP" or "2000 pixels ZIP"
            resolution_match = re.search(r"(\d+)\s*pixels?", text, re.IGNORECASE)
            width = int(resolution_match.group(1)) if resolution_match else 0

            # Determine variant from URL or resolution
            if "lrg" in url or width >= 4000:
                variant = "lrg"
            elif "med" in url or width >= 2000:
                variant = "med"
            else:
                variant = "sml"

            # Track the highest resolution ZIP
            if width > best_resolution:
                best_resolution = width
                best_zip = {
                    "url": url,
                    "variant": variant,
                    "width": width,
                }

        # Use the highest resolution ZIP found
        zip_url = None
        if best_zip:
            zip_file = AvailableGalleryZipFile(
                file_type="gallery",
                content_type="gallery",
                variant=best_zip["variant"],
                url=best_zip["url"],
                resolution_width=best_zip["width"],
            )
            available_files.append(zip_file)

            download_items.append(
                DirectDownloadItem(
                    release_id=release_id,
                    file_info=ItemAdapter(zip_file).asdict(),
                    url=best_zip["url"],
                )
            )
            zip_url = best_zip["url"]
        else:
            self.logger.warning(f"No ZIP download links found for {slug}")

        # Extract cover image URL from img.info-img
        cover_url = response.css("img.info-img::attr(src)").get()

        # For high-res cover, try to convert gsml to lrg in the URL
        if cover_url and "-gsml." in cover_url:
            cover_url = cover_url.replace("-gsml.", "-lrg.")

        if cover_url:
            cover_file = AvailableImageFile(
                file_type="image",
                content_type="cover",
                variant="cover",
                url=cover_url,
            )
            available_files.append(cover_file)

            download_items.append(
                DirectDownloadItem(
                    release_id=release_id,
                    file_info=ItemAdapter(cover_file).asdict(),
                    url=cover_file.url,
                )
            )

        self.logger.info(f"Parsed gallery: {title}")
        self.logger.info(f"  Slug: {slug}")
        self.logger.info(f"  Date: {release_date}")
        self.logger.info(f"  Performers: {[p.name for p in performers]}")
        self.logger.info(f"  ZIP URL: {zip_url}")
        self.logger.info(f"  Cover URL: {cover_url}")

        # Create release item
        release_item = ReleaseItem(
            id=release_id,
            release_date=release_date.isoformat() if release_date else None,
            short_name=slug,
            name=title,
            url=response.url,
            description=description,
            duration=0,  # Deprecated field
            created=datetime.now(tz=UTC).astimezone(),
            last_updated=datetime.now(tz=UTC).astimezone(),
            performers=performers,
            tags=[],
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps({"slug": slug, "title": title}),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item

        # Filter download items to only yield missing files
        if existing_release and not self.force_update:
            downloaded_files = existing_release["downloaded_files"]
            missing_items = [
                item
                for item, af in zip(download_items, available_files, strict=True)
                if (af.file_type, af.content_type, af.variant) not in downloaded_files
            ]
            if missing_items:
                self.logger.info(f"Release {slug} exists but missing {len(missing_items)} files. Downloading them.")
            else:
                self.logger.info(f"Release {slug} already has all files downloaded. Skipping downloads.")
            yield from missing_items
        else:
            yield from download_items
