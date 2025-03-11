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

# Load and format cookies properly
raw_cookies = json.loads(os.getenv("LEZKISS_COOKIES", "[]"))
cookies = {}
if isinstance(raw_cookies, list):
    for cookie in raw_cookies:
        if isinstance(cookie, dict) and "name" in cookie and "value" in cookie:
            cookies[cookie["name"]] = cookie["value"]

base_url = os.getenv("LEZKISS_BASE_URL")


class LezKissSpider(scrapy.Spider):
    name = "lezkiss"
    allowed_domains = os.getenv("LEZKISS_ALLOWED_DOMAINS").split(",")
    start_urls = [base_url]
    site_short_name = "lezkiss"

    def __init__(self, *args, **kwargs):
        super(LezKissSpider, self).__init__(*args, **kwargs)
        self.performer_image_path = "F:\\Ripping\\LezKiss\\Performers"
        os.makedirs(self.performer_image_path, exist_ok=True)

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

    def start_requests(self):
        """Override start_requests to handle enter declaration."""
        # First visit the enter.php page to handle age verification
        yield scrapy.Request(
            url=f"{base_url}/enter.php",
            callback=self.handle_enter_declaration,
            dont_filter=True,
            meta={"dont_redirect": True, "handle_httpstatus_list": [302]},
        )

    def handle_enter_declaration(self, response):
        """Handle the enter declaration page and set necessary cookies."""
        # Set cookies for age verification
        cookies_dict = {
            "enter_declaration": "ok",  # This matches the localStorage requirement
        }
        cookies_dict.update(cookies)  # Add any other cookies from .env

        # Now start the main crawl with proper cookies
        yield scrapy.Request(
            url=f"{base_url}/videos/",
            callback=self.parse_videos,
            cookies=cookies_dict,
            meta={"page": 1},
            dont_filter=True,
        )

        # yield scrapy.Request(
        #     url=f"{base_url}/photos/",
        #     callback=self.parse_photos,
        #     cookies=cookies_dict,
        #     meta={"page": 1},
        #     dont_filter=True
        # )

    def parse(self, response):
        """Initial parse method - entry point for the spider."""
        # This is now handled by start_requests
        pass

    def parse_videos(self, response):
        """Parse the videos listing page."""
        # Extract video entries - each video is in a div.item-col
        video_entries = response.css("div.item-col")

        for entry in video_entries[0:2]:
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
        # if next_page:
        #     current_page = response.meta["page"]
        #     yield scrapy.Request(
        #         url=response.urljoin(next_page),
        #         callback=self.parse_videos,
        #         cookies=cookies,
        #         meta={"page": current_page + 1},
        #     )

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
        external_id = response.meta["external_id"]
        title = response.meta["title"]
        duration_seconds = response.meta.get("duration", 0)

        # Get release date from the stats container
        release_date_text = response.css(
            "div.stats-container span.icon.i-calendar + span.sub-label::text"
        ).get()
        if release_date_text:
            try:
                release_date = (
                    datetime.strptime(release_date_text.strip(), "%Y-%m-%d %H:%M:%S")
                    .date()
                    .isoformat()
                )
            except ValueError:
                release_date = None
        else:
            release_date = None

        # Extract performers from the models section
        performers = []
        performer_downloads = []  # Store performer image downloads for later
        performer_elements = response.css("div.tags-block ul.models-list li a")
        for performer_element in performer_elements:
            performer_name = performer_element.css("span.sub-label::text").get()
            performer_url = performer_element.css("::attr(href)").get()
            if performer_url and performer_name:
                performer_short_name = performer_url.split("/")[-1].replace(".html", "")
                performer = get_or_create_performer(
                    self.site.id,
                    performer_short_name,
                    performer_name,
                    response.urljoin(performer_url),
                )
                performers.append(performer)

                # Create performer image download info but don't yield yet
                image_url = self.get_performer_image_url(performer_short_name)
                if image_url:
                    file_info = {
                        "file_type": "image",
                        "content_type": "performer",
                        "variant": f"profile_{performer_name.replace(' ', '_')}",
                        "url": image_url,
                    }
                    performer_downloads.append(file_info)

        # Extract tags
        tags = []
        tag_elements = response.css("div.tags-block a[href*='search']")
        for tag_element in tag_elements:
            tag_name = tag_element.css("::text").get()
            if tag_name:
                tag_name = tag_name.strip()
                tag_short_name = tag_name.lower().replace(" ", "-")
                tag_url = tag_element.css("::attr(href)").get()
                if tag_url:
                    tag = get_or_create_tag(
                        self.site.id,
                        tag_short_name,
                        tag_name,
                        response.urljoin(tag_url),
                    )
                    tags.append(tag)

        # Get cover image URL from meta tags
        cover_url = response.css("meta[property='og:image']::attr(content)").get()

        # Extract video download links
        available_files = []

        # Add cover image if available
        if cover_url:
            available_files.append(
                AvailableImageFile(
                    file_type="image",
                    content_type="cover",
                    variant="cover",
                    url=cover_url,
                )
            )

        # Extract video files - look for download links in the tabs section
        video_links = response.css(
            'div.item-tabs-col ul.tabs-list li a[href*="/videos/"], div.item-tabs-col ul.tabs-list li a[href*="/files/"]'
        )
        self.logger.info(f"Found {len(video_links)} video links")

        # Sort links by quality preference (1080p first, then 720p, then others)
        video_urls = []
        for link in video_links:
            url = link.css("::attr(href)").get()
            if not url:
                continue

            # Skip non-video links (like favorites, reports etc)
            if not ("videos" in url or "files" in url):
                continue

            # Get quality from either the sub-label or the URL
            quality_text = link.css("span.sub-label::text").get() or url
            quality_text = quality_text.lower()

            self.logger.info(
                f"Processing video link: {url} with quality: {quality_text}"
            )

            # Determine priority (higher number = higher priority)
            # Base priority on resolution
            priority = 0
            if "1080" in quality_text:
                priority = 30  # Base priority for 1080p
                width, height = 1920, 1080
            elif "720" in quality_text:
                priority = 20  # Base priority for 720p
                width, height = 1280, 720
            elif "480" in quality_text:
                priority = 10  # Base priority for 480p
                width, height = 854, 480
            else:
                # Try to extract resolution from URL
                if "1080" in url:
                    priority = 30
                    width, height = 1920, 1080
                elif "720" in url:
                    priority = 20
                    width, height = 1280, 720
                elif "480" in url:
                    priority = 10
                    width, height = 854, 480
                else:
                    width = height = None

            # Add format bonus - prefer MP4 over WMV at the same resolution
            if url.endswith(".mp4"):
                priority += 1

            # Get the format for the variant name
            format_suffix = "mp4" if url.endswith(".mp4") else "wmv"

            video_urls.append(
                {
                    "url": url,
                    "priority": priority,
                    "width": width,
                    "height": height,
                    "variant": (
                        f"{height}p_{format_suffix}"
                        if height
                        else f"default_{format_suffix}"
                    ),
                }
            )

        # Sort by priority (highest first) and take the best quality
        if video_urls:
            self.logger.info(f"Found {len(video_urls)} valid video URLs")
            best_video = sorted(video_urls, key=lambda x: x["priority"], reverse=True)[
                0
            ]
            self.logger.info(
                f"Selected best video: {best_video['url']} ({best_video['variant']})"
            )
            video_file = AvailableVideoFile(
                file_type="video",
                content_type="scene",
                variant=best_video["variant"],
                url=best_video["url"],
                resolution_width=best_video["width"],
                resolution_height=best_video["height"],
            )
            available_files.append(video_file)
        else:
            self.logger.warning(f"No valid video URLs found for {external_id}")

        # Add performer images to available files
        for file_info in performer_downloads:
            image = AvailableImageFile(
                file_type=file_info["file_type"],
                content_type=file_info["content_type"],
                variant=file_info["variant"],
                url=file_info["url"],
            )
            available_files.append(image)

        # Create the release item
        release_id = self.existing_releases.get(external_id, {}).get(
            "uuid", newnewid.uuid7()
        )

        release_item = ReleaseItem(
            id=release_id,
            release_date=release_date,
            short_name=external_id,
            name=title,
            url=response.url,
            description="",
            duration=duration_seconds,
            created=datetime.now(tz=timezone.utc).astimezone(),
            last_updated=datetime.now(tz=timezone.utc).astimezone(),
            performers=performers,
            tags=tags,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(
                {
                    "external_id": external_id,
                    "title": title,
                    "duration": duration_seconds,
                    "raw_html": response.text,
                }
            ),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item

        # Generate DirectDownloadItems for each file
        for file_info in available_files:
            yield DirectDownloadItem(
                release_id=release_id,
                file_info=ItemAdapter(file_info).asdict(),
                url=file_info.url,
            )

    def parse_gallery_detail(self, response):
        """Parse individual gallery detail page."""
        external_id = response.meta["external_id"]
        title = response.meta["title"]

        # Get release date from the stats container
        release_date_text = response.css(
            "div.stats-container ul.stats-list li span.icon.i-calendar + span.sub-label::text"
        ).get()
        if release_date_text:
            try:
                release_date = (
                    datetime.strptime(release_date_text.strip(), "%Y-%m-%d %H:%M:%S")
                    .date()
                    .isoformat()
                )
            except ValueError:
                release_date = None
        else:
            release_date = None

        # Extract performers from the models section
        performers = []
        performer_downloads = []  # Store performer image downloads for later
        performer_elements = response.css("div.tags-block ul.models-list li a")
        for performer_element in performer_elements:
            performer_name = performer_element.css("span.sub-label::text").get()
            performer_url = performer_element.css("::attr(href)").get()
            if performer_url and performer_name:
                performer_short_name = performer_url.split("/")[-1].replace(".html", "")
                performer = get_or_create_performer(
                    self.site.id,
                    performer_short_name,
                    performer_name,
                    response.urljoin(performer_url),
                )
                performers.append(performer)

                # Create performer image download info but don't yield yet
                image_url = self.get_performer_image_url(performer_short_name)
                if image_url:
                    file_info = {
                        "file_type": "image",
                        "content_type": "performer",
                        "variant": f"profile_{performer_name.replace(' ', '_')}",
                        "url": image_url,
                    }
                    performer_downloads.append(file_info)

        # Extract tags
        tags = []
        tag_elements = response.css("div.tags-block a[href*='search']")
        for tag_element in tag_elements:
            tag_name = tag_element.css("::text").get()
            if tag_name:
                tag_name = tag_name.strip()
                tag_short_name = tag_name.lower().replace(" ", "-")
                tag_url = tag_element.css("::attr(href)").get()
                if tag_url:
                    tag = get_or_create_tag(
                        self.site.id,
                        tag_short_name,
                        tag_name,
                        response.urljoin(tag_url),
                    )
                    tags.append(tag)

        # Get cover image URL from meta tags
        cover_url = response.css("meta[property='og:image']::attr(content)").get()

        # Extract gallery images
        available_files = []

        # Add cover image if available
        if cover_url:
            available_files.append(
                AvailableImageFile(
                    file_type="image",
                    content_type="cover",
                    variant="cover",
                    url=cover_url,
                )
            )

        # Extract gallery images
        gallery_images = response.css(
            "div#galleryImages div.gallery-item-col a img::attr(src)"
        ).getall()
        for idx, image_url in enumerate(gallery_images, 1):
            available_files.append(
                AvailableImageFile(
                    file_type="image",
                    content_type="gallery",
                    variant=f"image_{idx}",
                    url=image_url,
                )
            )

        # Extract zip file download if available
        zip_download = response.css("ul.tabs-list li a[download]::attr(href)").get()
        if zip_download:
            zip_url = response.urljoin(zip_download)
            available_files.append(
                AvailableGalleryZipFile(
                    file_type="zip",
                    content_type="gallery",
                    variant="gallery_zip",
                    url=zip_url,
                )
            )

        # Add performer images to available files
        for file_info in performer_downloads:
            image = AvailableImageFile(
                file_type=file_info["file_type"],
                content_type=file_info["content_type"],
                variant=file_info["variant"],
                url=file_info["url"],
            )
            available_files.append(image)

        # Create the release item
        release_id = self.existing_releases.get(external_id, {}).get(
            "uuid", newnewid.uuid7()
        )

        release_item = ReleaseItem(
            id=release_id,
            release_date=release_date,
            short_name=external_id,
            name=title,
            url=response.url,
            description="",
            duration=0,
            created=datetime.now(tz=timezone.utc).astimezone(),
            last_updated=datetime.now(tz=timezone.utc).astimezone(),
            performers=performers,
            tags=tags,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(
                {
                    "external_id": external_id,
                    "title": title,
                    "raw_html": response.text,
                }
            ),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item

        # Generate DirectDownloadItems for each file
        for file_info in available_files:
            yield DirectDownloadItem(
                release_id=release_id,
                file_info=ItemAdapter(file_info).asdict(),
                url=file_info.url,
            )

    def get_performer_image_url(self, performer_short_name):
        """Get the performer image URL based on their short name."""
        try:
            # Split by hyphen and take the last part which should be the ID
            parts = performer_short_name.split("-")
            if not parts:
                self.logger.warning(
                    f"Could not extract model ID from performer short name: {performer_short_name}"
                )
                return None

            model_id = parts[-1]  # Take the last part after splitting
            if not model_id.isdigit():
                self.logger.warning(
                    f"Invalid model ID (not a number) from performer short name: {performer_short_name}"
                )
                return None

            self.logger.info(
                f"Extracted model ID {model_id} from performer short name: {performer_short_name}"
            )
            return f"{base_url}/media/misc/model{model_id}.jpg"
        except Exception as e:
            self.logger.error(
                f"Error extracting model ID from performer short name: {performer_short_name} - {str(e)}"
            )
            return None

    def create_performer_image_download(self, performer, image_url):
        """Create a DirectDownloadItem for a performer's image."""
        if not image_url:
            return None

        # Create a unique ID for the download
        download_id = newnewid.uuid7()

        # Create file info for the performer image
        file_info = {
            "file_type": "image",
            "content_type": "performer",
            "variant": "profile",
            "url": image_url,
            "target_path": os.path.join(
                self.performer_image_path, f"{performer.short_name}.jpg"
            ),
        }

        return DirectDownloadItem(
            release_id=download_id, file_info=file_info, url=image_url
        )
