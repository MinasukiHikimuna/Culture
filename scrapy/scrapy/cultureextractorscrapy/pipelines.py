# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import os
from urllib.parse import urlparse
import newnewid
from scrapy.pipelines.files import FilesPipeline
from scrapy import Request
from scrapy.exceptions import DropItem
import logging
from scrapy.utils.project import get_project_settings

from .spiders.database import get_session, Site, Release, DownloadedFile, Performer, Tag
from .items import (
    ReleaseAndDownloadsItem,
    ReleaseItem,
    AvailableVideoFile,
    AvailableImageFile,
    AvailableGalleryZipFile,
    DownloadedFileItem,
    DirectDownloadItem,
)
from datetime import datetime
import json
from sqlalchemy.exc import IntegrityError

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import subprocess
import hashlib

from twisted.internet import defer


class PostgresPipeline:
    def __init__(self):
        self.session = get_session()

    def process_item(self, item, spider):
        if isinstance(item, ReleaseAndDownloadsItem):
            return self.process_release_and_downloads(item, spider)
        elif isinstance(item, ReleaseItem):
            try:
                site = self.session.query(Site).filter_by(uuid=item.site_uuid).first()
                if not site:
                    spider.logger.error(f"Site not found for UUID: {item.site_uuid}")
                    return item

                existing_release = (
                    self.session.query(Release).filter_by(uuid=str(item.id)).first()
                )

                if existing_release:
                    # Update existing release
                    existing_release.release_date = (
                        datetime.fromisoformat(item.release_date)
                        if item.release_date
                        else None
                    )
                    existing_release.short_name = item.short_name
                    existing_release.name = item.name
                    existing_release.url = item.url
                    existing_release.description = item.description
                    existing_release.duration = item.duration
                    existing_release.last_updated = item.last_updated
                    existing_release.available_files = item.available_files
                    existing_release.json_document = item.json_document

                    # Clear existing relationships
                    existing_release.performers = []
                    existing_release.tags = []
                    spider.logger.info(f"Updating existing release with ID: {item.id}")
                    release = existing_release
                else:
                    # Create new release
                    release = Release(
                        uuid=str(item.id),
                        release_date=(
                            datetime.fromisoformat(item.release_date)
                            if item.release_date
                            else None
                        ),
                        short_name=item.short_name,
                        name=item.name,
                        url=item.url,
                        description=item.description,
                        duration=item.duration,
                        created=item.created,
                        last_updated=item.last_updated,
                        available_files=item.available_files,
                        json_document=item.json_document,
                        site_uuid=str(item.site_uuid),
                    )
                    self.session.add(release)
                    spider.logger.info(f"Creating new release with ID: {item.id}")

                # Add performers
                if item.performers:
                    for performer_item in item.performers:
                        performer = (
                            self.session.query(Performer)
                            .filter_by(uuid=str(performer_item.id))
                            .first()
                        )
                        if performer:
                            release.performers.append(performer)
                            spider.logger.info(
                                f"Added performer {performer.name} to release {item.id}"
                            )

                # Add tags
                if item.tags:
                    for tag_item in item.tags:
                        tag = (
                            self.session.query(Tag)
                            .filter_by(uuid=str(tag_item.id))
                            .first()
                        )
                        if tag:
                            release.tags.append(tag)
                            spider.logger.info(
                                f"Added tag {tag.name} to release {item.id}"
                            )

                # Commit the transaction
                self.session.commit()
                spider.logger.info(f"Successfully processed release with ID: {item.id}")

            except Exception as e:
                self.session.rollback()
                spider.logger.error(f"Error processing release with ID: {item.id}")
                spider.logger.error(str(e))
                raise

            return defer.succeed(item)
        elif isinstance(item, DownloadedFileItem):
            try:
                spider.logger.info(
                    f"[PostgresPipeline] Processing DownloadedFileItem: {item['saved_filename']}"
                )
                # Create new downloaded file record
                downloaded_file = DownloadedFile(
                    uuid=str(item["uuid"]),
                    downloaded_at=item["downloaded_at"],
                    file_type=item["file_type"],
                    content_type=item["content_type"],
                    variant=item["variant"] or "",  # Ensure variant is never null
                    available_file=item["available_file"],
                    original_filename=item["original_filename"],
                    saved_filename=item["saved_filename"],
                    release_uuid=str(item["release_uuid"]),
                    file_metadata=item["file_metadata"],
                )
                self.session.add(downloaded_file)
                self.session.commit()
                spider.logger.info(
                    f"[PostgresPipeline] Successfully stored download record for file: {item['saved_filename']}"
                )
            except Exception as e:
                self.session.rollback()
                spider.logger.error(
                    f"[PostgresPipeline] Error storing download record: {str(e)}"
                )
                raise
            return item
        return item

    def close_spider(self, spider):
        self.session.close()


class AvailableFilesPipeline(FilesPipeline):
    def __init__(self, store_uri, download_func=None, settings=None):
        super().__init__(store_uri, download_func, settings)
        self.store_uri = store_uri  # This is the FILES_STORE setting
        # Add Windows invalid characters list
        self.INVALID_CHARS = r'<>:"/\|?*'
        self.INVALID_NAMES = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }

    def sanitize_path(self, path):
        """Sanitize the path to be Windows-compatible."""
        # Split path into parts
        parts = path.split(os.sep)

        # Sanitize each part
        sanitized_parts = []
        for part in parts:
            # Replace invalid characters with underscore
            for char in self.INVALID_CHARS:
                part = part.replace(char, "_")

            # Remove any leading/trailing spaces or dots
            part = part.strip(" .")

            # Check if this part is a reserved name
            if part.upper() in self.INVALID_NAMES:
                part = f"_{part}"

            sanitized_parts.append(part)

        # Rejoin path
        return os.sep.join(sanitized_parts)

    def get_media_requests(self, item, info):
        if isinstance(item, DirectDownloadItem):
            spider = info.spider
            spider.logger.info(
                f"[AvailableFilesPipeline] Processing DirectDownloadItem for URL: {item['url']}"
            )

            file_path = self.file_path(
                None,
                None,
                info,
                release_id=item["release_id"],
                file_info=item["file_info"],
            )

            full_path = os.path.join(self.store.basedir, file_path)
            spider.logger.info(f"[AvailableFilesPipeline] Full file path: {full_path}")
            spider.logger.info(
                f"[AvailableFilesPipeline] File info: {item['file_info']}"
            )

            if not os.path.exists(full_path):
                spider.logger.info(
                    f"[AvailableFilesPipeline] File does not exist, requesting download: {full_path}"
                )
                return [
                    Request(
                        item["url"],
                        meta={
                            "release_id": item["release_id"],
                            "file_info": item["file_info"],
                            "dont_redirect": True,
                            "handle_httpstatus_list": [302, 401],
                        },
                    )
                ]
            else:
                spider.logger.info(
                    f"[AvailableFilesPipeline] File already exists, skipping: {full_path}"
                )
        return []

    def file_path(
        self,
        request,
        response=None,
        info=None,
        *,
        item=None,
        release_id=None,
        file_info=None,
    ):
        if request:
            release_id = request.meta["release_id"]
            file_info = request.meta["file_info"]

        # Get release info from database
        session = get_session()
        try:
            release = session.query(Release).filter_by(uuid=release_id).first()
            if not release:
                raise ValueError(f"Release with ID {release_id} not found")

            site = session.query(Site).filter_by(uuid=release.site_uuid).first()
            if not site:
                raise ValueError(f"Site with ID {release.site_uuid} not found")

            release_date = release.release_date.isoformat()
            release_name = release.name  # Original name from database
            site_name = site.name

            # Extract file extension from the URL or use original filename from json_document
            url_path = urlparse(file_info["url"]).path
            file_extension = os.path.splitext(url_path)[1]
            if not file_extension:
                file_extension = ".mp4"  # Default to .mp4 for video files

            # Create filename in the specified format
            if file_info["file_type"] == "video":
                filename = f"{site_name} - {release_date} - {release_name} - {file_info['resolution_width']}x{file_info['resolution_height']} - {release_id}{file_extension}"
            else:
                filename = f"{site_name} - {release_date} - {release_name} - {file_info['variant']} - {release_id}{file_extension}"

            # Create a folder structure based on site and release ID
            folder = f"{site_name}/Metadata/{release_id}"

            # Sanitize each component separately to maintain structure
            sanitized_site = self.sanitize_component(site_name)
            sanitized_filename = self.sanitize_component(filename)

            # Combine into final path
            file_path = f"{sanitized_site}/Metadata/{release_id}/{sanitized_filename}"

            info.spider.logger.info(
                f"[AvailableFilesPipeline] Generated file path: {file_path}"
            )
            return file_path
        finally:
            session.close()

    def sanitize_component(self, text):
        """Sanitize a single component of a path to be Windows-compatible."""
        # Replace invalid characters with underscore
        for char in self.INVALID_CHARS:
            text = text.replace(char, "_")

        # Remove any leading/trailing spaces or dots
        text = text.strip(" .")

        # Check if this is a reserved name
        if text.upper() in self.INVALID_NAMES:
            text = f"_{text}"

        # Ensure component is not too long (Windows MAX_PATH is 260)
        if len(text) > 240:  # Leave some room for the path
            name, ext = os.path.splitext(text)
            text = name[:236] + ext  # 236 + 4 char extension

        return text

    def item_completed(self, results, item, info):
        if isinstance(item, DirectDownloadItem):
            spider = info.spider
            spider.logger.info(
                f"[AvailableFilesPipeline] Item completed for URL: {item['url']}"
            )
            spider.logger.info(f"[AvailableFilesPipeline] Download results: {results}")

            file_paths = [x["path"] for ok, x in results if ok]
            spider.logger.info(
                f"[AvailableFilesPipeline] File paths from results: {file_paths}"
            )

            if file_paths:
                file_info = item["file_info"]
                # Get full path by combining store_uri with relative path
                full_path = os.path.join(self.store_uri, file_paths[0])
                spider.logger.info(
                    f"[AvailableFilesPipeline] Processing completed file: {full_path}"
                )

                file_metadata = self.process_file_metadata(
                    full_path, file_info["file_type"]
                )

                downloaded_item = DownloadedFileItem(
                    uuid=newnewid.uuid7(),
                    downloaded_at=datetime.now(),
                    file_type=file_info["file_type"],
                    content_type=file_info.get("content_type"),
                    variant=file_info.get("variant"),
                    available_file=file_info,
                    original_filename=os.path.basename(item["url"].split("?")[0]),
                    saved_filename=os.path.basename(file_paths[0]),
                    release_uuid=item["release_id"],
                    file_metadata=file_metadata,
                )
                spider.logger.info(
                    f"[AvailableFilesPipeline] Created DownloadedFileItem for: {downloaded_item['saved_filename']}"
                )
                return downloaded_item
            else:
                spider.logger.info(
                    "[AvailableFilesPipeline] No file paths in results, skipping DownloadedFileItem creation"
                )
        return item

    def process_file_metadata(self, file_path, file_type):
        if file_type == "video":
            return self.process_video_metadata(file_path)
        else:
            return self.process_generic_metadata(file_path, file_type)

    def process_video_metadata(self, file_path):
        result = subprocess.run(
            ["C:\\Tools\\videohashes-windows-amd64.exe", "-json", "-md5", file_path],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            video_hashes = json.loads(result.stdout)
            return {
                "$type": "VideoHashes",
                "duration": video_hashes.get("duration"),
                "phash": video_hashes.get("phash"),
                "oshash": video_hashes.get("oshash"),
                "md5": video_hashes.get("md5"),
            }
        else:
            logging.error(f"Failed to get video hashes: {result.stderr}")
            return {}

    def process_generic_metadata(self, file_path, file_type):
        if file_type == "zip":
            type = "GalleryZipFileMetadata"
        elif file_type == "image":
            type = "ImageFileMetadata"
        elif file_type == "vtt":
            type = "VttFileMetadata"

        sha256_hash = hashlib.sha256()
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                md5_hash.update(byte_block)
        sha256_sum = sha256_hash.hexdigest()
        md5_sum = md5_hash.hexdigest()

        return {"$type": type, "sha256Sum": sha256_sum, "md5Sum": md5_sum}
