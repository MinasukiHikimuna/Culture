# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import newnewid
from scrapy import Request

# useful for handling different item types with a single interface
from scrapy.pipelines.files import FilesPipeline
from twisted.internet import defer

from .items import (
    DirectDownloadItem,
    DownloadedFileItem,
    M3u8DownloadItem,
    PerformerItem,
    ReleaseAndDownloadsItem,
    ReleaseItem,
)
from .spiders.database import DownloadedFile, Performer, Release, Site, Tag, get_session
from .utils import check_available_disk_space


class PostgresPipeline:
    def __init__(self):
        self.session = get_session()

    def process_item(self, item, spider):
        if isinstance(item, ReleaseAndDownloadsItem):
            return self.process_release_and_downloads(item, spider)
        if isinstance(item, ReleaseItem):
            try:
                site = self.session.query(Site).filter_by(uuid=item.site_uuid).first()
                if not site:
                    spider.logger.error(f"Site not found for UUID: {item.site_uuid}")
                    return item

                existing_release = self.session.query(Release).filter_by(uuid=item.id).first()

                if existing_release:
                    # Update existing release
                    available_files = (
                        json.loads(item.available_files)
                        if isinstance(item.available_files, str)
                        else item.available_files
                    )
                    json_document = (
                        json.loads(item.json_document)
                        if isinstance(item.json_document, str)
                        else item.json_document
                    )
                    existing_release.release_date = (
                        datetime.fromisoformat(item.release_date) if item.release_date else None
                    )
                    existing_release.short_name = item.short_name
                    existing_release.name = item.name
                    existing_release.url = item.url
                    existing_release.description = item.description
                    existing_release.duration = item.duration
                    existing_release.last_updated = item.last_updated
                    existing_release.available_files = available_files
                    existing_release.json_document = json_document
                    existing_release.sub_site_uuid = (
                        str(item.sub_site_uuid) if item.sub_site_uuid else None
                    )

                    # Clear existing relationships
                    existing_release.performers = []
                    existing_release.tags = []
                    spider.logger.info(f"Updating existing release with ID: {item.id}")
                    release = existing_release
                else:
                    # Create new release
                    available_files = (
                        json.loads(item.available_files)
                        if isinstance(item.available_files, str)
                        else item.available_files
                    )
                    json_document = (
                        json.loads(item.json_document)
                        if isinstance(item.json_document, str)
                        else item.json_document
                    )
                    release = Release(
                        uuid=item.id,
                        release_date=(
                            datetime.fromisoformat(item.release_date) if item.release_date else None
                        ),
                        short_name=item.short_name,
                        name=item.name,
                        url=item.url,
                        description=item.description,
                        duration=item.duration,
                        created=item.created,
                        last_updated=item.last_updated,
                        available_files=available_files,
                        json_document=json_document,
                        site_uuid=item.site_uuid,
                        sub_site_uuid=item.sub_site_uuid,
                    )
                    self.session.add(release)
                    spider.logger.info(f"Creating new release with ID: {item.id}")

                # Add performers
                if item.performers:
                    for performer_item in item.performers:
                        performer = (
                            self.session.query(Performer).filter_by(uuid=performer_item.id).first()
                        )
                        if performer:
                            release.performers.append(performer)
                            spider.logger.info(
                                "Added performer %s to release %s",
                                performer.name,
                                item.id,
                            )

                # Add tags
                if item.tags:
                    for tag_item in item.tags:
                        tag = self.session.query(Tag).filter_by(uuid=tag_item.id).first()
                        if tag:
                            release.tags.append(tag)
                            spider.logger.info("Added tag %s to release %s", tag.name, item.id)

                # Commit the transaction
                self.session.commit()
                spider.logger.info("Successfully processed release with ID: %s", item.id)

            except Exception as e:
                self.session.rollback()
                spider.logger.error("Error processing release with ID: %s", item.id)
                spider.logger.error(str(e))
                raise

            return defer.succeed(item)
        if isinstance(item, DownloadedFileItem):
            try:
                spider.logger.info(
                    "[PostgresPipeline] Processing DownloadedFileItem: %s",
                    item["saved_filename"],
                )
                # Create new downloaded file record
                downloaded_file = DownloadedFile(
                    uuid=(
                        item["uuid"]
                        if isinstance(item["uuid"], uuid.UUID)
                        else uuid.UUID(str(item["uuid"]))
                    ),
                    downloaded_at=item["downloaded_at"],
                    file_type=item["file_type"],
                    content_type=item["content_type"],
                    variant=item["variant"] or "",  # Ensure variant is never null
                    available_file=item["available_file"],
                    original_filename=item["original_filename"],
                    saved_filename=item["saved_filename"],
                    release_uuid=(
                        item["release_uuid"]
                        if isinstance(item["release_uuid"], uuid.UUID)
                        else uuid.UUID(str(item["release_uuid"]))
                    ),
                    file_metadata=item["file_metadata"],
                )
                self.session.add(downloaded_file)
                self.session.commit()
                spider.logger.info(
                    "[PostgresPipeline] Successfully stored download record for file: %s",
                    item["saved_filename"],
                )
            except Exception as e:
                self.session.rollback()
                spider.logger.error("[PostgresPipeline] Error storing download record: %s", str(e))
                raise
            return item
        return item

    def close_spider(self, spider):
        self.session.close()


class BaseDownloadPipeline:
    """Base class for download pipelines with shared file path and existence logic"""

    def __init__(self, store_uri, settings=None):
        self.store_uri = store_uri
        self.settings = settings
        self._ffmpeg_dir = None
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

    @property
    def ffmpeg_dir(self):
        """Lazily resolve the directory containing ffmpeg."""
        if self._ffmpeg_dir is None:
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                raise RuntimeError(
                    "ffmpeg not found in PATH. Install it with: brew install ffmpeg"
                )
            self._ffmpeg_dir = str(Path(ffmpeg_path).parent)
        return self._ffmpeg_dir

    def file_path(self, request, response=None, info=None, *, item=None):
        """Standard Scrapy FilesPipeline file_path method - extracts data from request"""
        if request is not None and hasattr(request, "meta"):
            release_id = request.meta.get("release_id")
            file_info = request.meta.get("file_info")
            if release_id and file_info:
                return self._generate_file_path(release_id, file_info)

        raise ValueError("Request must contain release_id and file_info in meta")

    def get_file_path(self, release_id, file_info):
        """Custom method for direct file path generation without request objects"""
        return self._generate_file_path(release_id, file_info)

    def _generate_file_path(self, release_id, file_info):
        """Generate file path from release_id and file_info without needing Request objects"""
        # Get release info from database
        session = get_session()
        try:
            release = session.query(Release).filter_by(uuid=release_id).first()
            if release is None:
                try:
                    release = (
                        session.query(Release).filter_by(uuid=uuid.UUID(str(release_id))).first()
                    )
                except ValueError:
                    release = None
            if not release:
                raise ValueError(f"Release with ID {release_id} not found")
            site = session.query(Site).filter_by(uuid=release.site_uuid).first()
            if not site:
                raise ValueError(f"Site with ID {release.site_uuid} not found")
            release_date = release.release_date.isoformat()
            release_name = release.name  # Original name from database
            release_short_name = release.short_name  # Site's video ID
            site_name = site.name
            # Format site name with subsite if available
            formatted_site_name = site_name
            if release.sub_site_uuid is not None:
                formatted_site_name = f"{site_name}꞉ {release.sub_site.name}"
            # Extract file extension from the URL or use original filename from json_document
            url_path = urlparse(file_info["url"]).path
            file_extension = Path(url_path).suffix

            # Convert .m3u8 to .mp4 since ffmpeg downloads HLS streams as MP4
            if file_extension == ".m3u8":
                file_extension = ".mp4"
            elif not file_extension:
                if file_info["file_type"] == "video":
                    file_extension = ".mp4"  # Default to .mp4 for video files
                elif file_info["file_type"] == "image":
                    file_extension = ".jpg"  # Default to .jpg for image files
                elif file_info["file_type"] == "zip":
                    file_extension = ".zip"  # Default to .zip for gallery zip files
                else:
                    file_extension = ""  # No extension for other types
            # Create filename in the specified format
            if file_info["file_type"] == "video":
                # Include variant to prevent overwriting when multiple quality versions exist
                variant_part = f" [{file_info['variant']}]" if file_info.get("variant") else ""
                # Only include resolution if both width and height are present and not None
                if file_info.get("resolution_width") and file_info.get("resolution_height"):
                    resolution_part = (
                        f" - {file_info['resolution_width']}x{file_info['resolution_height']}"
                    )
                else:
                    resolution_part = ""
                filename = (
                    f"{formatted_site_name} - {release_date} - {release_short_name}"
                    f" - {release_name}{resolution_part}{variant_part} - {release_id}{file_extension}"
                )
            else:
                filename = (
                    f"{formatted_site_name} - {release_date} - {release_short_name}"
                    f" - {release_name} - {file_info['variant']} - {release_id}{file_extension}"
                )
            # Sanitize each component separately to maintain structure
            sanitized_site = self.sanitize_component(formatted_site_name)
            sanitized_filename = self.sanitize_component(filename)
            # Combine into final path
            file_path = f"{sanitized_site}/Metadata/{release_id}/{sanitized_filename}"

            # Debug logging
            print(f"[DEBUG file_path] Generated path: {file_path}")
            print(f"[DEBUG file_path] URL: {file_info['url']}")
            print(f"[DEBUG file_path] File extension extracted: {file_extension}")
            print(f"[DEBUG file_path] File type: {file_info['file_type']}")
            print(f"[DEBUG file_path] Release ID: {release_id}")

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
        return text

    def _calculate_sha256(self, file_path):
        """Calculate SHA-256 hash of a file using chunked reading."""
        try:
            sha256 = hashlib.sha256()
            with Path(file_path).open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except OSError:
            return None

    def file_exists_check(self, file_path):
        """Check if file already exists at the given path"""
        full_path = str(Path(self.store_uri) / file_path)
        return Path(full_path).exists()

    def create_downloaded_item_from_path(self, item, file_path, spider):
        """Create DownloadedFileItem from a file path"""
        from datetime import datetime

        file_info = item["file_info"]

        # Process file metadata
        full_path = str(Path(self.store_uri) / file_path)
        file_metadata = self.process_file_metadata(full_path, file_info["file_type"])

        # Create DownloadedFileItem
        downloaded_item = DownloadedFileItem(
            uuid=newnewid.uuid7(),
            downloaded_at=datetime.now(),
            file_type=file_info["file_type"],
            content_type=file_info["content_type"],
            variant=file_info["variant"],
            available_file=file_info,
            original_filename=Path(file_info["url"]).name,
            saved_filename=Path(file_path).name,
            release_uuid=item["release_id"],
            file_metadata=file_metadata,
        )

        spider.logger.info(
            "[BaseDownloadPipeline] Created DownloadedFileItem: %s",
            downloaded_item["saved_filename"],
        )
        return downloaded_item

    def process_file_metadata(self, file_path, file_type):
        """Process file metadata with proper video hashes and ffprobe data"""
        try:
            if file_type == "video":
                return self.process_video_metadata(file_path)
            if file_type == "audio":
                return self.process_audio_metadata(file_path)
            return self.process_generic_metadata(file_path, file_type)
        except Exception as e:
            return {"error": f"Failed to process metadata: {e!s}"}

    def process_video_metadata(self, file_path):
        """Process video file metadata with both video hashes and ffprobe data"""
        import json as json_lib

        metadata = {"$type": "VideoFileMetadata"}

        # Get video hashes (phash, oshash, md5, duration)
        try:
            videohashes_cmd = [
                "/Users/thardas/Code/videohashes/dist/videohashes-arm64-macos",
                "-json",
                "-md5",
                file_path,
            ]
            logging.info(
                f"[process_video_metadata] Running videohashes command: {' '.join(videohashes_cmd)}"
            )
            logging.info(f"[process_video_metadata] File path: {file_path}")
            logging.info(f"[process_video_metadata] File exists: {Path(file_path).exists()}")
            if Path(file_path).exists():
                file_size = Path(file_path).stat().st_size
                logging.info(f"[process_video_metadata] File size: {file_size} bytes")

            result = subprocess.run(
                videohashes_cmd,
                check=False, capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for video hash calculation
                cwd=self.ffmpeg_dir,  # videohashes looks for ffmpeg/ffprobe in cwd
            )

            logging.info(f"[process_video_metadata] videohashes return code: {result.returncode}")
            logging.info(f"[process_video_metadata] videohashes stdout: {result.stdout}")
            logging.info(f"[process_video_metadata] videohashes stderr: {result.stderr}")

            if result.returncode == 0:
                video_hashes = json_lib.loads(result.stdout)
                logging.info(f"[process_video_metadata] Parsed video hashes: {video_hashes}")
                # Add video hashes at root level for compatibility
                metadata["duration"] = video_hashes.get("duration")
                metadata["phash"] = video_hashes.get("phash")
                metadata["oshash"] = video_hashes.get("oshash")
                metadata["md5"] = video_hashes.get("md5")
                logging.info(
                    f"[process_video_metadata] Added hashes to metadata: duration={metadata['duration']}, phash={metadata['phash']}"
                )
            else:
                logging.error(f"Failed to get video hashes: {result.stderr}")
                metadata["video_hashes_error"] = result.stderr
        except Exception as e:
            logging.error(f"Video hashes calculation failed: {e!s}")
            metadata["video_hashes_error"] = str(e)

        # Get ffprobe metadata for additional technical details
        try:
            ffprobe_command = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                file_path,
            ]

            result = subprocess.run(ffprobe_command, check=False, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                ffprobe_data = json_lib.loads(result.stdout)
                metadata["ffprobe"] = ffprobe_data
            else:
                logging.error(f"ffprobe failed: {result.stderr}")
                metadata["ffprobe_error"] = result.stderr
        except Exception as e:
            logging.error(f"ffprobe failed: {e!s}")
            metadata["ffprobe_error"] = str(e)

        return metadata

    def process_audio_metadata(self, file_path):
        """Process audio file metadata including SHA-256 hash."""
        file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
        sha256_sum = self._calculate_sha256(file_path)
        metadata = {"$type": "AudioFileMetadata", "file_size": file_size}
        if sha256_sum:
            metadata["sha256Sum"] = sha256_sum
        return metadata

    def process_generic_metadata(self, file_path, file_type):
        """Process generic file metadata including SHA-256 hash."""
        file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
        sha256_sum = self._calculate_sha256(file_path)
        metadata = {
            "$type": "GenericFileMetadata",
            "file_type": file_type,
            "file_size": file_size,
        }
        if sha256_sum:
            metadata["sha256Sum"] = sha256_sum
        return metadata


class AvailableFilesPipeline(BaseDownloadPipeline, FilesPipeline):
    def __init__(self, store_uri, download_func=None, settings=None, crawler=None):
        BaseDownloadPipeline.__init__(self, store_uri, settings)
        FilesPipeline.__init__(self, store_uri, download_func, crawler=crawler)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings["FILES_STORE"], settings=crawler.settings, crawler=crawler)

    def get_media_requests(self, item, info):
        if isinstance(item, DirectDownloadItem):
            spider = info.spider
            spider.logger.info(
                "[AvailableFilesPipeline] Processing DirectDownloadItem for URL: %s",
                item["url"],
            )

            file_path = self.get_file_path(item["release_id"], item["file_info"])

            full_path = str(Path(self.store.basedir) / file_path)
            # Use %s formatting to avoid encoding issues in logging
            spider.logger.info("[AvailableFilesPipeline] Full file path: %s", full_path)
            spider.logger.info("[AvailableFilesPipeline] File info: %s", item["file_info"])

            if not self.file_exists_check(file_path):
                # Check disk space before downloading
                has_space, available_gb = check_available_disk_space(self.store_uri)
                if not has_space:
                    spider.logger.error(
                        "[AvailableFilesPipeline] Insufficient disk space (%.2fGB available, 50GB required). Skipping download: %s",
                        available_gb,
                        full_path,
                    )
                    from scrapy.exceptions import DropItem

                    raise DropItem(
                        f"Insufficient disk space: {available_gb:.2f}GB available, 50GB required"
                    )

                spider.logger.info(
                    "[AvailableFilesPipeline] File does not exist, requesting download (%.2fGB available): %s",
                    available_gb,
                    full_path,
                )

                return [
                    Request(
                        item["url"],
                        meta={
                            "release_id": item["release_id"],
                            "file_info": item["file_info"],
                            "dont_redirect": True,
                        },
                    )
                ]
            spider.logger.info(
                "[AvailableFilesPipeline] File already exists, skipping download: %s",
                full_path,
            )
        return []

    def item_completed(self, results, item, info):
        if isinstance(item, DirectDownloadItem):
            spider = info.spider
            spider.logger.info("[AvailableFilesPipeline] Item completed for URL: %s", item["url"])
            spider.logger.info("[AvailableFilesPipeline] Download results: %s", results)

            # Log detailed failure information
            for ok, result in results:
                if not ok:
                    spider.logger.error(
                        "[AvailableFilesPipeline] Download failed for URL %s: %s",
                        item["url"],
                        result,
                    )
                    # Try to extract more detailed error information
                    if hasattr(result, "value"):
                        spider.logger.error(
                            "[AvailableFilesPipeline] Failure value: %s", result.value
                        )
                    if hasattr(result, "getErrorMessage"):
                        spider.logger.error(
                            "[AvailableFilesPipeline] Error message: %s", result.getErrorMessage()
                        )
                else:
                    spider.logger.info("[AvailableFilesPipeline] Download successful: %s", result)

            file_paths = [x["path"] for ok, x in results if ok]
            spider.logger.info("[AvailableFilesPipeline] File paths from results: %s", file_paths)
            if file_paths:
                # Get full path by combining store_uri with relative path
                full_path = str(Path(self.store_uri) / file_paths[0])
                spider.logger.info("[AvailableFilesPipeline] Processing file: %s", full_path)
                return self.create_downloaded_item_from_path(item, file_paths[0], spider)
            spider.logger.warning(
                "[AvailableFilesPipeline] No successful downloads for URL: %s", item["url"]
            )
        return item


class M3u8DownloadPipeline(BaseDownloadPipeline):
    """Pipeline for downloading M3U8/HLS streams using yt-dlp with robust progress monitoring and timeout detection"""

    def __init__(self, store_uri, settings=None):
        super().__init__(store_uri, settings)
        # Configuration for timeout detection and retry behavior
        self.progress_timeout = 300  # 5 minutes without progress = timeout
        self.max_retries = 2  # Try up to 3 times total
        self.retry_delay = 30  # Wait 30 seconds between retries

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings["FILES_STORE"], settings=crawler.settings)

    def process_item(self, item, spider):
        if isinstance(item, M3u8DownloadItem):
            spider.logger.info(
                "[M3u8DownloadPipeline] Processing M3u8DownloadItem for URL: %s",
                item["url"],
            )
            spider.logger.info("[M3u8DownloadPipeline] DEBUG: Release ID: %s", item["release_id"])
            spider.logger.info("[M3u8DownloadPipeline] DEBUG: File info: %s", item["file_info"])

            # Generate file path using base class method
            file_path = self.get_file_path(item["release_id"], item["file_info"])

            # Check if file already exists
            spider.logger.info(
                "[M3u8DownloadPipeline] DEBUG: Checking file existence for path: %s", file_path
            )
            full_path_check = str(Path(self.store_uri) / file_path)
            spider.logger.info(
                "[M3u8DownloadPipeline] DEBUG: Full path for existence check: %s", full_path_check
            )
            spider.logger.info(
                "[M3u8DownloadPipeline] DEBUG: File exists result: %s",
                Path(full_path_check).exists(),
            )

            if self.file_exists_check(file_path):
                spider.logger.info("[M3u8DownloadPipeline] File already exists: %s", file_path)
                # Don't create a new DownloadedFileItem - just return the original item
                # This prevents duplicate records in the downloaded_files table
                return item

            # Check disk space before downloading
            has_space, available_gb = check_available_disk_space(self.store_uri)
            if not has_space:
                spider.logger.error(
                    "[M3u8DownloadPipeline] Insufficient disk space (%.2fGB available, 50GB required). Skipping download: %s",
                    available_gb,
                    file_path,
                )
                from scrapy.exceptions import DropItem

                raise DropItem(
                    f"Insufficient disk space: {available_gb:.2f}GB available, 50GB required"
                )

            # File doesn't exist, download with yt-dlp
            full_path = str(Path(self.store_uri) / file_path)
            spider.logger.info(
                "[M3u8DownloadPipeline] Downloading with yt-dlp to (%.2fGB available): %s",
                available_gb,
                full_path,
            )

            actual_path = self.download_hls_with_ytdlp(item["url"], full_path, spider)
            if actual_path:
                spider.logger.info(
                    "[M3u8DownloadPipeline] Download completed successfully: %s",
                    actual_path,
                )
                # Convert full path back to relative path for create_downloaded_item_from_path
                relative_path = os.path.relpath(actual_path, self.store_uri)
                return self.create_downloaded_item_from_path(item, relative_path, spider)
            spider.logger.error("[M3u8DownloadPipeline] Download failed: %s", item["url"])
            from scrapy.exceptions import DropItem

            raise DropItem(f"M3U8 download failed: {item['url']}")

        return item

    def download_hls_with_ytdlp(self, url, output_path, spider):
        """Download HLS stream using yt-dlp with timeout detection and retry logic"""
        import time

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                spider.logger.info(
                    "[M3u8DownloadPipeline] Retry attempt %d/%d after %d seconds delay",
                    attempt,
                    self.max_retries,
                    self.retry_delay,
                )
                time.sleep(self.retry_delay)

            try:
                # Ensure the directory exists
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                # Configure yt-dlp command with robust options
                cmd = [
                    "yt-dlp",
                    "--progress",  # Show progress bar
                    "--newline",  # Each progress update on new line
                    "--no-warnings",  # Reduce noise
                    "--fragment-retries",
                    "3",  # Retry fragments up to 3 times (reduced from 10)
                    "--retry-sleep",
                    "fragment:exp=1:5",  # Exponential backoff for fragment retries (reduced from 20)
                    "--abort-on-unavailable-fragment",  # Abort download if fragments are unavailable
                    "--concurrent-fragments",
                    "3",  # Download 3 fragments concurrently
                    "--throttled-rate",
                    "100K",  # Detect throttling if below 100KB/s
                    "--socket-timeout",
                    "30",  # 30 second socket timeout
                    "--no-continue",  # Don't resume partial downloads (avoid corruption)
                    "-f",
                    "best",  # Select best quality
                    "-o",
                    output_path,  # Output path
                    url,
                ]

                spider.logger.info(
                    "[M3u8DownloadPipeline] Starting yt-dlp download (attempt %d): %s",
                    attempt + 1,
                    " ".join(cmd),
                )

                # Track progress for timeout detection
                last_progress_time = time.time()
                last_downloaded_bytes = 0
                last_fragment = 0
                stall_count = 0

                # Use Popen to capture output in real-time
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    universal_newlines=True,
                )

                # Monitor progress with timeout detection
                while True:
                    output = process.stdout.readline()
                    if output == "" and process.poll() is not None:
                        break

                    if output:
                        current_time = time.time()
                        progress_info = self.parse_ytdlp_progress(output)

                        if progress_info:
                            downloaded_bytes = progress_info.get("downloaded_bytes", 0)
                            current_fragment = progress_info.get("current_fragment", 0)

                            # Check for progress (fragment or bytes advancing)
                            has_progress = (
                                current_fragment > last_fragment
                                or downloaded_bytes > last_downloaded_bytes
                            )

                            if has_progress:
                                last_progress_time = current_time
                                last_downloaded_bytes = downloaded_bytes
                                last_fragment = current_fragment
                                stall_count = 0

                                # Log progress every 30 seconds or when fragment changes significantly
                                if (
                                    current_time - getattr(self, "last_log_time", 0) > 30
                                    or current_fragment - getattr(self, "last_logged_fragment", 0)
                                    >= 10
                                ):
                                    spider.logger.info(
                                        "[M3u8DownloadPipeline] Progress: %s", output.strip()
                                    )
                                    self.last_log_time = current_time
                                    self.last_logged_fragment = current_fragment
                            else:
                                # No progress detected (neither fragments nor bytes advancing)
                                time_since_progress = current_time - last_progress_time
                                if time_since_progress > 30:  # Log stall every 30s
                                    stall_count += 1
                                    spider.logger.warning(
                                        "[M3u8DownloadPipeline] No progress for %.1f seconds (stall #%d) - fragment %d, bytes %d: %s",
                                        time_since_progress,
                                        stall_count,
                                        current_fragment,
                                        downloaded_bytes,
                                        output.strip(),
                                    )

                                # Timeout if no progress for too long (reduced to 3 minutes for fragment-level detection)
                                fragment_timeout = 180  # 3 minutes for fragment stalls
                                if time_since_progress > fragment_timeout:
                                    spider.logger.error(
                                        "[M3u8DownloadPipeline] Download stalled for %.1f seconds, killing process",
                                        time_since_progress,
                                    )
                                    process.terminate()
                                    try:
                                        process.wait(timeout=10)
                                    except subprocess.TimeoutExpired:
                                        process.kill()
                                    break
                        else:
                            # Non-progress output, log occasionally
                            spider.logger.debug("[M3u8DownloadPipeline] yt-dlp: %s", output.strip())

                # Check final result
                return_code = process.wait()

                if return_code == 0 and Path(output_path).exists():
                    file_size = Path(output_path).stat().st_size
                    spider.logger.info(
                        "[M3u8DownloadPipeline] Download successful: %s (%.1f MB)",
                        output_path,
                        file_size / (1024 * 1024),
                    )
                    return output_path
                # Get any remaining stderr output
                stderr_output = process.stderr.read()
                spider.logger.error(
                    "[M3u8DownloadPipeline] yt-dlp failed with return code %s (attempt %d): %s",
                    return_code,
                    attempt + 1,
                    stderr_output,
                )

                # Clean up partial file
                if Path(output_path).exists():
                    try:
                        Path(output_path).unlink()
                        spider.logger.info("[M3u8DownloadPipeline] Cleaned up partial file")
                    except OSError:
                        pass

                # Don't retry on certain permanent failures
                if return_code in [1, 2] and "not available" in stderr_output.lower():
                    spider.logger.error(
                        "[M3u8DownloadPipeline] Permanent failure, not retrying"
                    )
                    break

            except subprocess.TimeoutExpired:
                spider.logger.error(
                    "[M3u8DownloadPipeline] yt-dlp process timed out (attempt %d)", attempt + 1
                )
                try:
                    process.kill()
                except Exception as e:
                    spider.logger.debug(
                        "[M3u8DownloadPipeline] Failed to kill timed-out process: %s", e
                    )
            except FileNotFoundError:
                spider.logger.error(
                    "[M3u8DownloadPipeline] yt-dlp not found in PATH. Please install yt-dlp."
                )
                break  # Don't retry if yt-dlp is missing
            except Exception as e:
                spider.logger.error(
                    "[M3u8DownloadPipeline] yt-dlp download error (attempt %d): %s",
                    attempt + 1,
                    str(e),
                )

        spider.logger.error(
            "[M3u8DownloadPipeline] All %d attempts failed for URL: %s", self.max_retries + 1, url
        )
        return False

    def parse_ytdlp_progress(self, output_line):
        """Parse yt-dlp progress output to extract download statistics including fragment info"""
        import re

        # Enhanced regex to capture fragment info: [download] 32.9% of ~ 3.18GiB at 30.49MiB/s ETA 01:14 (frag 86/262)
        fragment_progress_match = re.search(
            r"\[download\]\s+(\d+\.?\d*)%\s+of\s+~?\s*([\d.]+\w+)(?:\s+at\s+([\d.]+\w+/s))?\s+ETA\s+([\d:]+)\s+\(frag\s+(\d+)/(\d+)\)",
            output_line,
        )

        if fragment_progress_match:
            percent = float(fragment_progress_match.group(1))
            total_size_str = fragment_progress_match.group(2)
            speed_str = fragment_progress_match.group(3) or "0B/s"
            eta_str = fragment_progress_match.group(4) or "unknown"
            current_frag = int(fragment_progress_match.group(5))
            total_frags = int(fragment_progress_match.group(6))

            # Convert size strings to bytes (rough estimation)
            total_bytes = self.parse_size_string(total_size_str)
            downloaded_bytes = int(total_bytes * percent / 100) if total_bytes else 0

            return {
                "downloaded_bytes": downloaded_bytes,
                "total_bytes": total_bytes,
                "percent": percent,
                "speed": speed_str,
                "eta": eta_str,
                "current_fragment": current_frag,
                "total_fragments": total_frags,
            }

        # Fallback to original regex for non-fragment downloads: [download] 12.5% of 1.23GB at 156.78KB/s ETA 00:45
        basic_progress_match = re.search(
            r"\[download\]\s+(\d+\.?\d*)%\s+of\s+~?\s*([\d.]+\w+)(?:\s+at\s+([\d.]+\w+/s))?(?:\s+ETA\s+([\d:]+))?",
            output_line,
        )

        if basic_progress_match:
            percent = float(basic_progress_match.group(1))
            total_size_str = basic_progress_match.group(2)
            speed_str = basic_progress_match.group(3) or "0B/s"
            eta_str = basic_progress_match.group(4) or "unknown"

            # Convert size strings to bytes (rough estimation)
            total_bytes = self.parse_size_string(total_size_str)
            downloaded_bytes = int(total_bytes * percent / 100) if total_bytes else 0

            return {
                "downloaded_bytes": downloaded_bytes,
                "total_bytes": total_bytes,
                "percent": percent,
                "speed": speed_str,
                "eta": eta_str,
                "current_fragment": 0,  # No fragment info available
                "total_fragments": 0,
            }

        return None

    def parse_size_string(self, size_str):
        """Convert size string like '1.23GB' to bytes"""
        import re

        match = re.match(r"([\d.]+)(\w+)", size_str)
        if not match:
            return 0

        size = float(match.group(1))
        unit = match.group(2).upper()

        multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

        return int(size * multipliers.get(unit, 1))


class FfmpegDownloadPipeline(BaseDownloadPipeline):
    """Legacy pipeline for downloading M3U8/HLS streams using ffmpeg (kept for backward compatibility)"""

    def __init__(self, store_uri, settings=None):
        super().__init__(store_uri, settings)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings["FILES_STORE"], settings=crawler.settings)

    def process_item(self, item, spider):
        if isinstance(item, M3u8DownloadItem):
            spider.logger.info(
                "[FfmpegDownloadPipeline] Processing M3u8DownloadItem for URL: %s",
                item["url"],
            )
            spider.logger.info("[FfmpegDownloadPipeline] DEBUG: Release ID: %s", item["release_id"])
            spider.logger.info("[FfmpegDownloadPipeline] DEBUG: File info: %s", item["file_info"])

            # Generate file path using base class method
            file_path = self.get_file_path(item["release_id"], item["file_info"])

            # Check if file already exists
            spider.logger.info(
                "[FfmpegDownloadPipeline] DEBUG: Checking file existence for path: %s", file_path
            )
            full_path_check = str(Path(self.store_uri) / file_path)
            spider.logger.info(
                "[FfmpegDownloadPipeline] DEBUG: Full path for existence check: %s", full_path_check
            )
            spider.logger.info(
                "[FfmpegDownloadPipeline] DEBUG: File exists result: %s",
                Path(full_path_check).exists(),
            )

            if self.file_exists_check(file_path):
                spider.logger.info("[FfmpegDownloadPipeline] File already exists: %s", file_path)
                # Don't create a new DownloadedFileItem - just return the original item
                # This prevents duplicate records in the downloaded_files table
                return item

            # Check disk space before downloading
            has_space, available_gb = check_available_disk_space(self.store_uri)
            if not has_space:
                spider.logger.error(
                    "[FfmpegDownloadPipeline] Insufficient disk space (%.2fGB available, 50GB required). Skipping download: %s",
                    available_gb,
                    file_path,
                )
                from scrapy.exceptions import DropItem

                raise DropItem(
                    f"Insufficient disk space: {available_gb:.2f}GB available, 50GB required"
                )

            # File doesn't exist, download with ffmpeg
            full_path = str(Path(self.store_uri) / file_path)
            spider.logger.info(
                "[FfmpegDownloadPipeline] Downloading with ffmpeg to (%.2fGB available): %s",
                available_gb,
                full_path,
            )

            actual_path = self.download_hls_with_ffmpeg(item["url"], full_path, spider)
            if actual_path:
                spider.logger.info(
                    "[FfmpegDownloadPipeline] Download completed successfully: %s",
                    actual_path,
                )
                # Convert full path back to relative path for create_downloaded_item_from_path
                relative_path = os.path.relpath(actual_path, self.store_uri)
                return self.create_downloaded_item_from_path(item, relative_path, spider)
            spider.logger.error("[FfmpegDownloadPipeline] Download failed: %s", item["url"])
            from scrapy.exceptions import DropItem

            raise DropItem(f"FFmpeg download failed: {item['url']}")

        return item

    def download_hls_with_ffmpeg(self, url, output_path, spider):
        """Download HLS stream using ffmpeg"""
        try:
            # Ensure the directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Run ffmpeg command to download HLS stream
            cmd = [
                "ffmpeg",
                "-i",
                url,
                "-c",
                "copy",  # Copy streams without re-encoding
                "-progress",
                "pipe:2",  # Send progress to stderr
                "-y",  # Overwrite output file if it exists
                output_path,
            ]

            spider.logger.info(
                "[FfmpegDownloadPipeline] Starting ffmpeg download: %s", " ".join(cmd)
            )

            # Use Popen to capture output in real-time
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
            )

            # Monitor progress
            last_progress_log = 0
            while True:
                output = process.stderr.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    # Log progress every 30 seconds or on important messages
                    import time

                    current_time = time.time()
                    if (
                        "time=" in output
                        or "speed=" in output
                        or current_time - last_progress_log > 30
                    ):
                        spider.logger.info(
                            "[FfmpegDownloadPipeline] ffmpeg progress: %s", output.strip()
                        )
                        last_progress_log = current_time

            # Wait for process to complete
            return_code = process.wait()

            if return_code == 0:
                spider.logger.info(
                    "[FfmpegDownloadPipeline] ffmpeg download successful: %s", output_path
                )
                return output_path
            # Get any remaining stderr output
            remaining_stderr = process.stderr.read()
            spider.logger.error(
                "[FfmpegDownloadPipeline] ffmpeg failed with return code %s: %s",
                return_code,
                remaining_stderr,
            )
            return False

        except subprocess.TimeoutExpired:
            spider.logger.error("[FfmpegDownloadPipeline] ffmpeg download timed out for: %s", url)
            return False
        except FileNotFoundError:
            spider.logger.error(
                "[FfmpegDownloadPipeline] ffmpeg not found in PATH. Please install ffmpeg."
            )
            return False
        except Exception as e:
            spider.logger.error("[FfmpegDownloadPipeline] ffmpeg download error: %s", str(e))
            return False


class Aria2DownloadPipeline(BaseDownloadPipeline):
    """Pipeline for downloading files using aria2c with multi-connection support.

    This pipeline provides faster downloads for large files by using aria2c's
    multi-connection capabilities, resume support, and better error handling.
    """

    def __init__(self, store_uri, settings=None):
        super().__init__(store_uri, settings)
        self.logger = logging.getLogger(self.__class__.__name__)
        # Default aria2c settings
        self.max_connections = 16
        self.split = 16
        self.min_split_size = "1M"
        self.max_retries = 3
        self.timeout = 60

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings["FILES_STORE"], settings=crawler.settings)

    def process_item(self, item, spider):
        if isinstance(item, DirectDownloadItem):
            self.logger.info(
                "[Aria2DownloadPipeline] Processing DirectDownloadItem for URL: %s",
                item["url"],
            )

            file_path = self.get_file_path(item["release_id"], item["file_info"])
            full_path = str(Path(self.store_uri) / file_path)

            self.logger.info("[Aria2DownloadPipeline] Full file path: %s", full_path)

            if self.file_exists_check(file_path):
                self.logger.info(
                    "[Aria2DownloadPipeline] File already exists, skipping download: %s",
                    full_path,
                )
                # Don't create a new DownloadedFileItem - just return the original item
                # This prevents duplicate records in the downloaded_files table
                return item

            # Check disk space before downloading
            has_space, available_gb = check_available_disk_space(self.store_uri)
            if not has_space:
                self.logger.error(
                    "[Aria2DownloadPipeline] Insufficient disk space (%.2fGB available, 50GB required). Skipping download: %s",
                    available_gb,
                    full_path,
                )
                from scrapy.exceptions import DropItem

                raise DropItem(
                    f"Insufficient disk space: {available_gb:.2f}GB available, 50GB required"
                )

            self.logger.info(
                "[Aria2DownloadPipeline] Starting download with aria2c (%.2fGB available): %s",
                available_gb,
                full_path,
            )

            # Download with aria2c
            success = self.download_with_aria2(item["url"], full_path, spider)

            if success:
                self.logger.info(
                    "[Aria2DownloadPipeline] Download completed successfully: %s",
                    full_path,
                )
                return self.create_downloaded_item_from_path(item, file_path, spider)
            self.logger.error("[Aria2DownloadPipeline] Download failed: %s", item["url"])
            from scrapy.exceptions import DropItem

            raise DropItem(f"aria2c download failed: {item['url']}")

        return item

    def download_with_aria2(self, url, output_path, spider):
        """Download file using aria2c with multi-connection support"""
        try:
            # Ensure the directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Get cookies from spider if available
            cookie_header = None
            if hasattr(spider, "cookies") and spider.cookies:
                # Convert cookies dict to header format
                cookie_pairs = [f"{name}={value}" for name, value in spider.cookies.items()]
                cookie_header = "; ".join(cookie_pairs)

            # Build aria2c command
            cmd = [
                "aria2c",
                "--console-log-level=notice",  # Show important messages
                "--summary-interval=5",  # Show progress summary every 5 seconds
                "--user-agent",
                self.settings.get("USER_AGENT", "Mozilla/5.0"),
                "--max-connection-per-server",
                str(self.max_connections),
                "--split",
                str(self.split),
                "--min-split-size",
                self.min_split_size,
                "--continue=true",
                "--max-tries",
                str(self.max_retries),
                "--retry-wait",
                "3",
                "--timeout",
                str(self.timeout),
                "--allow-overwrite=false",
                "--auto-file-renaming=false",
                "--dir",
                str(Path(output_path).parent),
                "--out",
                Path(output_path).name,
            ]

            # Add cookie header if available
            if cookie_header:
                cmd.extend(["--header", f"Cookie: {cookie_header}"])

            # Add referer header based on URL domain
            from urllib.parse import urlparse

            parsed_url = urlparse(url)
            referer = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            cmd.extend(["--header", f"Referer: {referer}"])

            # Add the URL as the last argument
            cmd.append(url)

            self.logger.info(
                "[Aria2DownloadPipeline] Running aria2c command: %s",
                " ".join(cmd),
            )

            # Run aria2c with real-time output streaming
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Redirect stderr to stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
            )

            # Stream output in real-time
            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    # Log aria2c output (strip trailing whitespace)
                    line = output.rstrip()
                    if line:  # Only log non-empty lines
                        self.logger.info("[aria2c] %s", line)

            # Wait for process to complete
            return_code = process.wait()

            if return_code == 0 and Path(output_path).exists():
                file_size = Path(output_path).stat().st_size
                self.logger.info(
                    "[Aria2DownloadPipeline] Download successful: %s (%.1f MB)",
                    output_path,
                    file_size / (1024 * 1024),
                )
                return True
            self.logger.error(
                "[Aria2DownloadPipeline] aria2c failed with return code %s",
                return_code,
            )

            # Clean up partial file if exists
            if Path(output_path).exists():
                try:
                    Path(output_path).unlink()
                    self.logger.info("[Aria2DownloadPipeline] Cleaned up partial file")
                except OSError:
                    pass

            return False

        except subprocess.TimeoutExpired:
            self.logger.error("[Aria2DownloadPipeline] aria2c download timed out for: %s", url)
            return False
        except FileNotFoundError:
            self.logger.error(
                "[Aria2DownloadPipeline] aria2c not found in PATH. Please install aria2."
            )
            return False
        except Exception as e:
            self.logger.error("[Aria2DownloadPipeline] aria2c download error: %s", str(e))
            return False


class PerformerImagePipeline:
    """Pipeline to download performer images directly to disk.

    Downloads images to: /Volumes/Ripping/{SiteName}/Performers/{performer_uuid}/

    Respects FORCE_UPDATE setting:
    - False (default): Only download if file doesn't exist
    - True: Re-download all images, overwriting existing files
    """

    def __init__(self, files_store):
        self.files_store = files_store
        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def from_crawler(cls, crawler):
        files_store = crawler.settings.get("FILES_STORE", "/Volumes/Ripping/")
        return cls(files_store)

    def process_item(self, item, spider):
        if not isinstance(item, PerformerItem):
            return item

        performer = item.performer
        performer_uuid = str(performer.id)
        site_name = spider.site.name

        # Get force_update setting from spider
        force_update = getattr(spider, "force_update", False)

        # Create base path for this performer
        performer_dir = str(Path(self.files_store) / site_name / "Performers" / performer_uuid)
        Path(performer_dir).mkdir(parents=True, exist_ok=True)

        self.logger.info(f"[PerformerImagePipeline] Processing {performer.name} ({performer_uuid})")

        # Download each image
        for idx, img_info in enumerate(item.image_urls):
            url = img_info["url"]
            img_type = img_info.get("type", "profile")

            # Determine filename based on type
            if img_type == "profile" and idx == 0:
                # Main profile image uses performer UUID
                ext = self._get_extension(url)
                filename = f"{performer_uuid}{ext}"
            elif img_type == "profile-alt":
                # Alternative profile image
                ext = self._get_extension(url)
                filename = f"{performer_uuid}-alt{ext}"
            else:
                # Other images get numbered
                ext = self._get_extension(url)
                filename = f"{performer_uuid}-{idx + 1}{ext}"

            filepath = str(Path(performer_dir) / filename)

            # Check if file exists (unless force_update is True)
            if not force_update and Path(filepath).exists():
                self.logger.info(f"[PerformerImagePipeline] Skipping {filename} (already exists)")
                continue

            # Download the image
            try:
                self._download_image(url, filepath, spider)
                self.logger.info(f"[PerformerImagePipeline] Downloaded {filename} from {url}")
            except Exception as e:
                self.logger.error(f"[PerformerImagePipeline] Failed to download {filename}: {e}")

        return item

    def _get_extension(self, url):
        """Extract file extension from URL."""
        parsed = urlparse(url)
        path = parsed.path
        # Remove query parameters
        path = path.split("?")[0]
        ext = Path(path).suffix
        return ext if ext else ".jpg"

    def _download_image(self, url, filepath, spider):
        """Download an image from URL to filepath."""
        import requests

        # Use cookies if available from spider
        cookies = {}
        if hasattr(spider, "cookies"):
            cookies = spider.cookies

        response = requests.get(url, cookies=cookies, timeout=30)
        response.raise_for_status()

        with Path(filepath).open("wb") as f:
            f.write(response.content)


class StashDbImagePipeline:
    """Pipeline to download StashDB images (scenes, performers, studios) to disk.

    Downloads images to: data/stashdb/images/{type}/{entity_id}.jpg
    """

    def __init__(self, images_store):
        self.images_store = images_store
        self.logger = logging.getLogger(self.__class__.__name__)
        self.downloaded_ids = {"scene": set(), "performer": set(), "studio": set()}

    @classmethod
    def from_crawler(cls, crawler):
        images_store = crawler.settings.get("IMAGES_STORE", "data/stashdb/images")
        return cls(images_store)

    def process_item(self, item, spider):
        # Import here to avoid circular imports
        from .spiders.stashdb import StashDbImageItem

        if not isinstance(item, StashDbImageItem):
            return item

        image_type = item["image_type"]
        entity_id = item["entity_id"]
        image_urls = item.get("image_urls", [])

        if not image_urls:
            return item

        # Skip if already downloaded in this session
        if entity_id in self.downloaded_ids[image_type]:
            return item

        # Create directory for this image type
        type_dir = str(Path(self.images_store) / f"{image_type}s")
        Path(type_dir).mkdir(parents=True, exist_ok=True)

        # Download first image
        url = image_urls[0]
        ext = self._get_extension(url)
        filename = f"{entity_id}{ext}"
        filepath = str(Path(type_dir) / filename)

        # Skip if file already exists
        if Path(filepath).exists():
            self.logger.debug(
                f"[StashDbImagePipeline] Skipping {image_type} {entity_id} (already exists)"
            )
            self.downloaded_ids[image_type].add(entity_id)
            return item

        # Download the image
        try:
            self._download_image(url, filepath)
            self.logger.info(
                f"[StashDbImagePipeline] Downloaded {image_type} image for {entity_id}"
            )
            self.downloaded_ids[image_type].add(entity_id)
        except Exception as e:
            self.logger.error(
                f"[StashDbImagePipeline] Failed to download {image_type} {entity_id}: {e}"
            )

        return item

    def _get_extension(self, url):
        """Extract file extension from URL."""
        parsed = urlparse(url)
        path = parsed.path
        path = path.split("?")[0]
        ext = Path(path).suffix
        return ext if ext else ".jpg"

    def _download_image(self, url, filepath):
        """Download an image from URL to filepath."""
        import requests

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with Path(filepath).open("wb") as f:
            f.write(response.content)
