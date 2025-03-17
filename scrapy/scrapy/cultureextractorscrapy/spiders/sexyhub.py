import os
import json
import newnewid
from datetime import datetime, timezone
from dotenv import load_dotenv
import scrapy
from scrapy.exceptions import CloseSpider
from cultureextractorscrapy.spiders.database import (
    get_site_item,
    get_or_create_performer,
    get_or_create_tag,
    get_existing_releases_with_status,
    get_or_create_sub_site,
)
from cultureextractorscrapy.items import (
    AvailableGalleryZipFile,
    AvailableImageFile,
    AvailableVideoFile,
    AvailableFileEncoder,
    ReleaseItem,
    DirectDownloadItem,
    SubSiteItem,
)
from cultureextractorscrapy.utils import (
    parse_resolution_height,
    parse_resolution_width,
    get_log_filename,
)
from itemadapter import ItemAdapter
from urllib.parse import parse_qs, urlparse
import uuid
import re

load_dotenv()

# Load and format cookies properly
raw_cookies = json.loads(os.getenv("SEXYHUB_COOKIES", "[]"))
cookies = {}
if isinstance(raw_cookies, list):
    for cookie in raw_cookies:
        if isinstance(cookie, dict) and "name" in cookie and "value" in cookie:
            cookies[cookie["name"]] = cookie["value"]

base_url = os.getenv("SEXYHUB_BASE_URL")

girlfriends_id = 289
dane_jones_id = 290
lesbea_id = 291
massage_rooms_id = 292
mom_id = 293
fitness_rooms_id = 294

remote_site_id = girlfriends_id


class SexyHubSpider(scrapy.Spider):
    name = "sexyhub"
    allowed_domains = os.getenv("SEXYHUB_ALLOWED_DOMAINS").split(",")
    start_urls = [base_url]
    site_short_name = "sexyhub"

    def __init__(self, *args, **kwargs):
        super(SexyHubSpider, self).__init__(*args, **kwargs)
        self.handle_httpstatus_list = [401]  # Add 401 to handled status codes

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(SexyHubSpider, cls).from_crawler(crawler, *args, **kwargs)

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
        headers = {
            "authority": "site-api.project1service.com",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",  # Simplified to just gzip
            "accept-language": "en-US,en;q=0.9",
            "authorization": os.getenv("SEXYHUB_AUTH_TOKEN"),
            "cache-control": "no-cache",
            "instance": os.getenv("SEXYHUB_INSTANCE_TOKEN"),
            "origin": "https://site-ma.sexyhub.com",
            "pragma": "no-cache",
            "referer": "https://site-ma.sexyhub.com/",
            "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Microsoft Edge";v="134"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
        }

        # Scrapy will automatically handle gzip decompression
        per_page = 20
        offset = 0
        yield scrapy.Request(
            url=f"{base_url}/v2/releases?adaptiveStreamingOnly=false&dateReleased=%3C2025-03-13&orderBy=dateReleased&type=scene&groupFilter=primary&collectionId={remote_site_id}&limit={per_page}&offset={offset}",
            callback=self.parse,
            headers=headers,
            dont_filter=True,
            meta={
                "dont_redirect": True,
                "handle_httpstatus_list": [302, 401],  # Add 401 to handled status codes
                "headers": headers,
            },
            errback=self.handle_error,
        )

    def handle_error(self, failure):
        """Handle request errors."""
        if failure.value.response.status == 401:
            self.logger.error(
                "Received 401 Unauthorized response. Authentication failed. Stopping spider."
            )
            raise CloseSpider("authentication_failed")

    def parse(self, response):
        """Parse the response."""
        # Check for 401 response
        if response.status == 401:
            yield from self.handle_401_response(response)
            return

        # Continue with normal parsing if status is 200
        data = json.loads(response.text)

        # Process each release in the listing
        for release in data["result"]:
            external_id = f"scene-{release['id']}"

            # Check if we have this release in database
            existing_release = self.existing_releases.get(external_id)
            if existing_release and not self.force_update:
                # Compare available files with downloaded files
                available_files = existing_release["available_files"]
                downloaded_files = existing_release["downloaded_files"]

                needed_files = set(
                    (f["file_type"], f["content_type"], f["variant"])
                    for f in available_files
                )

                if not needed_files.issubset(downloaded_files):
                    # We have missing files - yield DirectDownloadItems
                    missing_files = [
                        f
                        for f in available_files
                        if (f["file_type"], f["content_type"], f["variant"])
                        not in downloaded_files
                    ]

                    for file in missing_files:
                        yield DirectDownloadItem(
                            release_id=existing_release["uuid"],
                            file_info=file,
                            url=file["url"],
                        )
                    self.logger.info(
                        f"Release {external_id} exists but missing {len(missing_files)} files. Downloading them."
                    )
                else:
                    self.logger.info(
                        f"Release {external_id} already exists with all files downloaded. Skipping."
                    )
                continue

            # Get detailed information for new releases
            yield scrapy.Request(
                url=f"{base_url}/v2/releases/{release['id']}",
                callback=self.parse_scene_detail,
                headers=response.meta["headers"],
                meta={
                    "release_data": release,
                    "headers": response.meta["headers"],
                    "dont_redirect": True,
                    "handle_httpstatus_list": [302, 401],
                },
                errback=self.handle_error,
            )

        # Handle pagination
        total = data["meta"]["total"]
        current_offset = int(
            parse_qs(urlparse(response.url).query).get("offset", [0])[0]
        )
        per_page = int(parse_qs(urlparse(response.url).query).get("limit", [4])[0])

        if current_offset + per_page < total:
            next_offset = current_offset + per_page
            next_url = f"{base_url}/v2/releases?adaptiveStreamingOnly=false&dateReleased=%3C2025-03-13&orderBy=dateReleased&type=scene&groupFilter=primary&collectionId={remote_site_id}&limit={per_page}&offset={next_offset}"

            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                headers=response.meta["headers"],
                meta={
                    "headers": response.meta["headers"],
                    "dont_redirect": True,
                    "handle_httpstatus_list": [302, 401],
                },
                errback=self.handle_error,
            )

    def parse_scene_detail(self, response):
        """Parse the scene detail response."""
        # Check for 401 response
        if response.status == 401:
            yield from self.handle_401_response(response)
            return

        data = json.loads(response.text)
        result = data["result"]
        release_data = response.meta["release_data"]

        external_id = f"scene-{release_data['id']}"
        release_id = str(newnewid.uuid7())

        # Process performers
        performers = []
        for actor in release_data.get("actors", []):
            performer = get_or_create_performer(
                self.site.id,
                str(actor["id"]),
                actor["name"],
                "",
            )
            performers.append(performer)

        # Process tags
        tags = []
        for tag in release_data.get("tags", []):
            tag_obj = get_or_create_tag(
                self.site.id,
                str(tag["id"]),
                tag["name"],
                "",
            )
            tags.append(tag_obj)

        # Extract subsite from collections
        sub_site = None
        sub_site_uuid = None
        if "collections" in release_data and release_data["collections"]:
            valid_collections = [
                c for c in release_data["collections"] if c.get("id") and c.get("name")
            ]
            if len(valid_collections) > 1:
                raise ValueError(
                    f"Found multiple subsites in release {release_data.get('id', 'unknown')}: "
                    f"{[c['name'] for c in valid_collections]}"
                )
            elif len(valid_collections) == 1:
                collection = valid_collections[0]
                sub_site = get_or_create_sub_site(
                    site_uuid=str(self.site.id),
                    short_name=str(collection["id"]),
                    name=collection["name"],
                )
                sub_site_uuid = sub_site.id

        available_files = []
        download_items = []

        # Process poster images
        if "images" in result and "poster" in result["images"]:
            poster_images = result["images"]["poster"]
            # Get the highest quality poster (usually "xx" which is 1920x1080)
            for image_key in ["xx", "xl", "lg", "md", "sm", "xs"]:
                if image_key in poster_images.get("0", {}):
                    image_data = poster_images["0"][image_key]
                    if "url" in image_data:
                        poster_file = AvailableImageFile(
                            file_type="image",
                            content_type="poster",
                            variant=image_key,
                            url=image_data["url"],
                            resolution_width=image_data["width"],
                            resolution_height=image_data["height"],
                        )
                        available_files.append(poster_file)
                        download_items.append(
                            DirectDownloadItem(
                                release_id=release_id,
                                file_info=ItemAdapter(poster_file).asdict(),
                                url=poster_file.url,
                            )
                        )
                        break  # Only get highest quality poster

        # Prepare the release metadata
        release_date = datetime.fromisoformat(
            release_data["dateReleased"].replace("Z", "+00:00")
        ).date()

        release_meta = {
            "id": release_id,
            "release_date": release_date.isoformat(),
            "short_name": external_id,
            "name": release_data.get("title", ""),
            "url": f"https://site-ma.sexyhub.com/scene/{release_data['id']}",
            "description": release_data.get("description", ""),
            "duration": 0,  # Duration not provided in API
            "created": datetime.now(tz=timezone.utc).astimezone(),
            "last_updated": datetime.now(tz=timezone.utc).astimezone(),
            "performers": performers,
            "tags": tags,
            "available_files": available_files,
            "json_document": release_data,
            "site_uuid": self.site.id,
            "site": self.site,
            "sub_site_uuid": sub_site_uuid,
            "sub_site": sub_site,
        }

        # Get video download info - video always exists
        video_id = str(release_data["id"])
        video_download_url = f"{base_url}/v1/video-download/{video_id}"
        self.logger.info(f"Requesting video download info from: {video_download_url}")

        # Check if there's a gallery to process
        has_gallery = any(
            child["type"] == "gallery" for child in result.get("children", [])
        )

        # Pass all metadata to video download parser
        yield scrapy.Request(
            url=video_download_url,
            callback=self.parse_video_download,
            headers=response.meta["headers"],
            meta={
                "release_meta": release_meta,
                "download_items": download_items,
                "headers": response.meta["headers"],
                "has_gallery": has_gallery,
                "result": result,
                "dont_redirect": True,
                "handle_httpstatus_list": [302, 401],
            },
            errback=self.handle_error,
            dont_filter=True,
        )

    def parse_video_download(self, response):
        """Parse the video download API response and add video files to metadata."""
        # Check for 401 response
        if response.status == 401:
            yield from self.handle_401_response(response)
            return

        self.logger.info("Parsing video download response")
        data = json.loads(response.text)
        release_meta = response.meta["release_meta"]
        download_items = response.meta["download_items"]
        result = response.meta["result"]
        has_gallery = response.meta["has_gallery"]

        # Find the highest quality MP4 download
        highest_quality = None
        highest_resolution = 0

        for video_file in data.get("files", []):
            if "urls" in video_file and "download" in video_file["urls"]:
                resolution = int(video_file["format"].replace("p", ""))
                # Only prefer h264 over av1 at the same resolution
                if resolution > highest_resolution or (
                    resolution == highest_resolution
                    and video_file.get("codec") == "h264"
                    and highest_quality.get("codec") != "h264"
                ):
                    highest_resolution = resolution
                    highest_quality = video_file
                    self.logger.info(
                        f"New highest quality video found: {resolution}p ({video_file.get('codec', 'unknown')} codec)"
                    )
                elif (
                    resolution == highest_resolution
                    and highest_quality.get("codec") != "h264"
                ):
                    # If we don't have h264 at this resolution, use AV1
                    highest_quality = video_file
                    self.logger.info(f"Using AV1 codec at {resolution}p resolution")

        if highest_quality:
            video_url = highest_quality["urls"]["download"]  # Use download URL
            width = parse_resolution_width(highest_quality["format"])
            height = parse_resolution_height(highest_quality["format"])

            self.logger.info(f"Creating video file object with URL: {video_url}")
            video_file = AvailableVideoFile(
                file_type="video",
                content_type="scene",
                variant=highest_quality["format"],
                url=video_url,
                resolution_width=width,
                resolution_height=height,
                file_size=highest_quality.get("sizeBytes"),
                fps=highest_quality.get("fps"),
                codec=highest_quality.get("codec"),
            )
            release_meta["available_files"].append(video_file)

            # Create DirectDownloadItem for video
            download_items.append(
                DirectDownloadItem(
                    release_id=release_meta["id"],
                    file_info=ItemAdapter(video_file).asdict(),
                    url=video_url,
                )
            )
            self.logger.info(f"Added video file for download: {video_url}")

        # If there's a gallery, chain to gallery processing
        if has_gallery:
            for child in result.get("children", []):
                if child["type"] == "gallery":
                    yield scrapy.Request(
                        url=f"{base_url}/v2/releases/{child['id']}",
                        callback=self.parse_gallery_detail,
                        headers=response.meta["headers"],
                        meta={
                            "release_meta": release_meta,
                            "download_items": download_items,
                            "headers": response.meta["headers"],
                            "dont_redirect": True,
                            "handle_httpstatus_list": [302, 401],
                        },
                        errback=self.handle_error,
                    )
                    return

        # If no gallery, yield the release item here
        yield self._create_release_item(release_meta)
        for download_item in download_items:
            yield download_item

    def parse_gallery_detail(self, response):
        """Parse the gallery details and yield the final release item with all files."""
        # Check for 401 response
        if response.status == 401:
            yield from self.handle_401_response(response)
            return

        data = json.loads(response.text)
        result = data["result"]
        release_meta = response.meta["release_meta"]
        download_items = response.meta["download_items"]

        # Process gallery downloads
        for gallery in result.get("galleries", []):
            if (
                gallery["format"] == "download"
                and "urls" in gallery
                and "download" in gallery["urls"]
            ):
                # Transform the media URL to the correct download URL format
                media_url = gallery["urls"]["download"]
                # Extract the path components from the media URL
                path_parts = media_url.split("/")
                if len(path_parts) >= 8:
                    # Reconstruct the download URL with the correct format
                    download_url = f"https://download-private-ht.project1content.com/{'/'.join(path_parts[3:])}"

                    gallery_file = AvailableGalleryZipFile(
                        file_type="zip",
                        content_type="gallery",
                        variant="original",
                        url=download_url,
                    )
                    release_meta["available_files"].append(gallery_file)

                    download_items.append(
                        DirectDownloadItem(
                            release_id=release_meta["id"],
                            file_info=ItemAdapter(gallery_file).asdict(),
                            url=gallery_file.url,
                        )
                    )

        # This is always the final step, yield the complete release item
        yield self._create_release_item(release_meta)
        for download_item in download_items:
            yield download_item

    def _create_release_item(self, release_meta):
        """Helper method to create a ReleaseItem from metadata."""
        return ReleaseItem(
            id=release_meta["id"],
            release_date=release_meta["release_date"],
            short_name=release_meta["short_name"],
            name=release_meta["name"],
            url=release_meta["url"],
            description=release_meta["description"],
            duration=release_meta["duration"],
            created=release_meta["created"],
            last_updated=release_meta["last_updated"],
            performers=release_meta["performers"],
            tags=release_meta["tags"],
            available_files=json.dumps(
                release_meta["available_files"], cls=AvailableFileEncoder
            ),
            json_document=json.dumps(release_meta["json_document"]),
            site_uuid=release_meta["site_uuid"],
            site=release_meta["site"],
            sub_site_uuid=release_meta.get("sub_site_uuid"),
            sub_site=release_meta.get("sub_site"),
        )
