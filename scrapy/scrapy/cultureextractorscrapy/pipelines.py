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
                        sub_site_uuid=(
                            str(item.sub_site_uuid) if item.sub_site_uuid else None
                        ),
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
                                "Added performer %s to release %s",
                                performer.name,
                                item.id,
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
                                "Added tag %s to release %s", tag.name, item.id
                            )

                # Commit the transaction
                self.session.commit()
                spider.logger.info(
                    "Successfully processed release with ID: %s", item.id
                )

            except Exception as e:
                self.session.rollback()
                spider.logger.error("Error processing release with ID: %s", item.id)
                spider.logger.error(str(e))
                raise

            return defer.succeed(item)
        elif isinstance(item, DownloadedFileItem):
            try:
                spider.logger.info(
                    "[PostgresPipeline] Processing DownloadedFileItem: %s",
                    item["saved_filename"],
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
                    "[PostgresPipeline] Successfully stored download record for file: %s",
                    item["saved_filename"],
                )
            except Exception as e:
                self.session.rollback()
                spider.logger.error(
                    "[PostgresPipeline] Error storing download record: %s", str(e)
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
                "[AvailableFilesPipeline] Processing DirectDownloadItem for URL: %s",
                item["url"],
            )

            file_path = self.file_path(
                None,
                None,
                info,
                release_id=item["release_id"],
                file_info=item["file_info"],
            )

            full_path = os.path.join(self.store.basedir, file_path)
            # Use %s formatting to avoid encoding issues in logging
            spider.logger.info("[AvailableFilesPipeline] Full file path: %s", full_path)
            spider.logger.info(
                "[AvailableFilesPipeline] File info: %s", item["file_info"]
            )

            if not os.path.exists(full_path):
                spider.logger.info(
                    "[AvailableFilesPipeline] File does not exist, requesting download: %s",
                    full_path,
                )
                
                # Check if this is an HLS m3u8 file that needs ffmpeg
                if item["url"].endswith('.m3u8') or '.m3u8' in item["url"]:
                    spider.logger.info(
                        "[AvailableFilesPipeline] Detected HLS stream, using ffmpeg for download"
                    )
                    # Handle ffmpeg download directly here
                    actual_path = self.download_hls_with_ffmpeg(item["url"], full_path, spider)
                    if actual_path:
                        spider.logger.info(
                            "[AvailableFilesPipeline] HLS download completed successfully: %s",
                            actual_path,
                        )
                        # Mark that we handled this with ffmpeg (we'll create DownloadedFileItem in item_completed)
                        item["_m3u8_downloaded_path"] = actual_path
                    else:
                        spider.logger.error(
                            "[AvailableFilesPipeline] HLS download failed: %s",
                            full_path,
                        )
                    return []  # Don't use standard downloader
                
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
                    "[AvailableFilesPipeline] File already exists, skipping: %s",
                    full_path,
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

            # Format site name with subsite if available
            formatted_site_name = site_name
            if release.sub_site_uuid is not None:
                formatted_site_name = f"{site_name}꞉ {release.sub_site.name}"

            # Extract file extension from the URL or use original filename from json_document
            url_path = urlparse(file_info["url"]).path
            file_extension = os.path.splitext(url_path)[1]
            if not file_extension:
                if file_info["file_type"] == "video":
                    file_extension = ".mp4"  # Default to .mp4 for video files
                elif file_info["file_type"] == "image":
                    file_extension = ".jpg"  # Default to .jpg for image files
                else:
                    file_extension = ""  # No extension for other types

            # Create filename in the specified format
            if file_info["file_type"] == "video":
                # Only include resolution if both width and height are present and not None
                if file_info.get('resolution_width') and file_info.get('resolution_height'):
                    resolution_part = f" - {file_info['resolution_width']}x{file_info['resolution_height']}"
                else:
                    resolution_part = ""
                filename = f"{formatted_site_name} - {release_date} - {release_name}{resolution_part} - {release_id}{file_extension}"
            else:
                filename = f"{formatted_site_name} - {release_date} - {release_name} - {file_info['variant']} - {release_id}{file_extension}"

            # Create a folder structure based on site and release ID
            folder = f"{formatted_site_name}/Metadata/{release_id}"

            # Sanitize each component separately to maintain structure
            sanitized_site = self.sanitize_component(formatted_site_name)
            sanitized_filename = self.sanitize_component(filename)

            # Combine into final path
            file_path = f"{sanitized_site}/Metadata/{release_id}/{sanitized_filename}"

            info.spider.logger.info(
                "[AvailableFilesPipeline] Generated file path: %s", file_path
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
                "[AvailableFilesPipeline] Item completed for URL: %s", item["url"]
            )
            spider.logger.info("[AvailableFilesPipeline] Download results: %s", results)

            # Check if this was downloaded with ffmpeg
            if "_m3u8_downloaded_path" in item:
                spider.logger.info(
                    "[AvailableFilesPipeline] Processing m3u8-downloaded file: %s", 
                    item["_m3u8_downloaded_path"]
                )
                return self.create_downloaded_item_from_path(item, item["_m3u8_downloaded_path"], spider)

            file_paths = [x["path"] for ok, x in results if ok]
            spider.logger.info(
                "[AvailableFilesPipeline] File paths from results: %s", file_paths
            )

            if file_paths:
                file_info = item["file_info"]
                # Get full path by combining store_uri with relative path
                full_path = os.path.join(self.store_uri, file_paths[0])
                spider.logger.info(
                    "[AvailableFilesPipeline] Processing completed file: %s", full_path
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
                    "[AvailableFilesPipeline] Created DownloadedFileItem for: %s",
                    downloaded_item["saved_filename"],
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
        elif file_type == "audio":
            return self.process_audio_metadata(file_path)
        else:
            return self.process_generic_metadata(file_path, file_type)

    def process_video_metadata(self, file_path):
        result = subprocess.run(
            ["/Users/thardas/Code/videohashes/dist/videohashes-arm64-macos", "-json", "-md5", file_path],
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

    def process_audio_metadata(self, file_path):
        """Process audio file metadata using ffprobe and calculate hashes."""
        metadata = {"$type": "AudioFileMetadata"}

        # Calculate file hashes
        sha256_hash = hashlib.sha256()
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                md5_hash.update(byte_block)

        metadata["sha256Sum"] = sha256_hash.hexdigest()
        metadata["md5Sum"] = md5_hash.hexdigest()

        # Extract audio metadata using ffprobe
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_streams",
                    "-select_streams",
                    "a:0",  # Select first audio stream
                    file_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])

                if streams:
                    audio_stream = streams[0]

                    # Extract metadata
                    metadata["duration"] = float(audio_stream.get("duration", 0))

                    bit_rate = audio_stream.get("bit_rate")
                    if bit_rate:
                        metadata["bitrate"] = int(bit_rate) // 1000  # Convert to kbps

                    sample_rate = audio_stream.get("sample_rate")
                    if sample_rate:
                        metadata["sampleRate"] = int(sample_rate)

                    channels = audio_stream.get("channels")
                    if channels:
                        metadata["channels"] = int(channels)

                    codec = audio_stream.get("codec_name")
                    if codec:
                        metadata["codec"] = codec

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            logging.warning(f"Could not extract audio metadata from {file_path}: {e}")

        return metadata

    def process_generic_metadata(self, file_path, file_type):
        if file_type == "zip":
            type = "GalleryZipFileMetadata"
        elif file_type == "image":
            type = "ImageFileMetadata"
        elif file_type == "audio":
            type = "AudioFileMetadata"
        elif file_type == "vtt":
            type = "VttFileMetadata"
        else:
            type = "GenericFileMetadata"

        sha256_hash = hashlib.sha256()
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                md5_hash.update(byte_block)
        sha256_sum = sha256_hash.hexdigest()
        md5_sum = md5_hash.hexdigest()

        return {"$type": type, "sha256Sum": sha256_sum, "md5Sum": md5_sum}
    
    def download_hls_with_ffmpeg(self, url, output_path, spider):
        """Download HLS stream using ffmpeg"""
        import subprocess
        import os
        
        try:
            # Ensure output path has .mp4 extension for HLS downloads
            if not output_path.endswith('.mp4'):
                output_path = os.path.splitext(output_path)[0] + '.mp4'
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Run ffmpeg command to download HLS stream
            cmd = [
                'ffmpeg',
                '-i', url,
                '-c', 'copy',  # Copy streams without re-encoding
                '-progress', 'pipe:2',  # Send progress to stderr
                '-y',  # Overwrite output file if it exists
                output_path
            ]
            
            spider.logger.info(
                "[AvailableFilesPipeline] Starting ffmpeg download: %s", 
                ' '.join(cmd)
            )
            
            # Use Popen to capture output in real-time
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Monitor progress
            last_progress_log = 0
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Log progress every 30 seconds or on important messages
                    import time
                    current_time = time.time()
                    if ('time=' in output or 'speed=' in output or 
                        current_time - last_progress_log > 30):
                        spider.logger.info(
                            "[AvailableFilesPipeline] ffmpeg progress: %s", 
                            output.strip()
                        )
                        if current_time - last_progress_log > 30:
                            last_progress_log = current_time
            
            return_code = process.poll()
            
            if return_code == 0:
                spider.logger.info(
                    "[AvailableFilesPipeline] ffmpeg download successful: %s", 
                    output_path
                )
                return output_path
            else:
                # Get any remaining stderr output
                remaining_stderr = process.stderr.read()
                spider.logger.error(
                    "[AvailableFilesPipeline] ffmpeg failed with return code %s: %s", 
                    return_code, remaining_stderr
                )
                return False
                
        except subprocess.TimeoutExpired:
            spider.logger.error(
                "[AvailableFilesPipeline] ffmpeg download timed out for: %s", 
                url
            )
            return False
        except FileNotFoundError:
            spider.logger.error(
                "[AvailableFilesPipeline] ffmpeg not found in PATH. Please install ffmpeg."
            )
            return False
        except Exception as e:
            spider.logger.error(
                "[AvailableFilesPipeline] ffmpeg download error: %s", 
                str(e)
            )
            return False
    
    def create_downloaded_item_from_path(self, item, full_path, spider):
        """Create DownloadedFileItem for HLS downloads that bypass standard pipeline"""
        from datetime import datetime
        import newnewid
        import os
        
        file_info = item["file_info"]
        
        # Process file metadata
        file_metadata = self.process_file_metadata(full_path, file_info["file_type"])
        
        # Create DownloadedFileItem
        downloaded_item = DownloadedFileItem(
            uuid=newnewid.uuid7(),
            downloaded_at=datetime.now(),
            file_type=file_info["file_type"],
            content_type=file_info.get("content_type"),
            variant=file_info.get("variant"),
            available_file=file_info,
            original_filename=os.path.basename(item["url"].split("?")[0]),
            saved_filename=os.path.basename(full_path),
            release_uuid=item["release_id"],
            file_metadata=file_metadata,
        )
        
        spider.logger.info(
            "[AvailableFilesPipeline] Created DownloadedFileItem: %s",
            downloaded_item["saved_filename"],
        )
        
        return downloaded_item
