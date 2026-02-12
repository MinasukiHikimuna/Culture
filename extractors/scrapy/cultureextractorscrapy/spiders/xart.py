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

    def start_requests(self):
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

            # For now, only process the first model for testing
            self.logger.info("Stopping after first model (test mode)")
            return

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

            # Extract slug from URL
            slug = href.rstrip("/").split("/")[-1]
            # Skip if it's not a valid slug
            if not slug or "+" in slug:
                continue

            # Check if we already have this release
            if slug in self.existing_releases and not self.force_update:
                self.logger.info(f"Skipping existing release: {slug}")
                continue

            # Handle plural forms correctly (video→videos, gallery→galleries)
            url_path = "galleries" if content_type == "gallery" else f"{content_type}s"
            release_url = f"{BASE_URL}/{url_path}/{slug}"
            self.logger.info(f"Found {content_type}: {slug} -> {release_url}")

            yield scrapy.Request(
                url=release_url,
                callback=callback,
                cookies=self.cookies_list,
                meta={"slug": slug, "content_type": content_type},
            )

            # For testing, only process the first release
            self.logger.info("Stopping after first release (test mode)")
            return

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

        # Build available files - video download URLs
        # URL pattern: /members/videos/{slug}/xart_realty_erotica_{slug_underscored}_{resolution}.mp4
        slug_underscored = slug.replace("-", "_")
        available_files = []
        download_items = []

        # Video resolutions available on X-Art
        video_variants = [
            ("360", 640, 360),
            ("540", 960, 540),
            ("720", 1280, 720),
            ("1080", 1920, 1080),
            ("4k", 3840, 2160),
        ]

        # Only download the highest quality (4K)
        variant, width, height = video_variants[-1]  # 4K
        video_url = f"{BASE_URL}/videos/{slug}/xart_realty_erotica_{slug_underscored}_{variant}.mp4"

        video_file = AvailableVideoFile(
            file_type="video",
            content_type="scene",
            variant=variant,
            url=video_url,
            resolution_width=width,
            resolution_height=height,
        )
        available_files.append(video_file)

        download_items.append(
            DirectDownloadItem(
                release_id=release_id,
                file_info=ItemAdapter(video_file).asdict(),
                url=video_url,
            )
        )

        # Add cover image for preview
        cover_url = f"{BASE_URL}/videos/{slug}/{slug}-01-lrg.jpg"
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

        # Yield download items
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

        # Build available files - gallery ZIP download URLs
        # URL pattern: /members/galleries/{slug}/{slug}-{size}.zip
        available_files = []
        download_items = []

        # Gallery ZIP sizes available on X-Art
        # Only download the highest quality (lrg = 4000px)
        zip_file = AvailableGalleryZipFile(
            file_type="gallery",
            content_type="gallery",
            variant="lrg",
            url=f"{BASE_URL}/galleries/{slug}/{slug}-lrg.zip",
            resolution_width=4000,
        )
        available_files.append(zip_file)

        download_items.append(
            DirectDownloadItem(
                release_id=release_id,
                file_info=ItemAdapter(zip_file).asdict(),
                url=zip_file.url,
            )
        )

        # Add cover image for preview
        cover_url = f"{BASE_URL}/galleries/{slug}/{slug}-01-lrg.jpg"
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
        self.logger.info(f"  ZIP URL: {zip_file.url}")

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

        # Yield download items
        yield from download_items
