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

from .spiders.database import get_session, Site, Release, DownloadedFile
from .items import ReleaseAndDownloadsItem, ReleaseItem, AvailableVideoFile, AvailableImageFile, AvailableGalleryZipFile, DownloadedFileItem, DirectDownloadItem
from datetime import datetime
import json
from sqlalchemy.exc import IntegrityError

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import subprocess
import hashlib

from .spiders.database import Site, Release, DownloadedFile

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

                existing_release = self.session.query(Release).filter_by(uuid=str(item.id)).first()

                if existing_release:
                    # Update existing release
                    existing_release.release_date = datetime.fromisoformat(item.release_date) if item.release_date else None
                    existing_release.short_name = item.short_name
                    existing_release.name = item.name
                    existing_release.url = item.url
                    existing_release.description = item.description
                    existing_release.duration = item.duration
                    existing_release.last_updated = item.last_updated
                    existing_release.available_files = item.available_files
                    existing_release.json_document = item.json_document
                    spider.logger.info(f"Updating existing release with ID: {item.id}")
                else:
                    # Create new release
                    new_release = Release(
                        uuid=str(item.id),
                        release_date=datetime.fromisoformat(item.release_date) if item.release_date else None,
                        short_name=item.short_name,
                        name=item.name,
                        url=item.url,
                        description=item.description,
                        duration=item.duration,
                        created=item.created,
                        last_updated=item.last_updated,
                        available_files=item.available_files,
                        json_document=item.json_document,
                        site_uuid=str(item.site_uuid)
                    )
                    self.session.add(new_release)
                    spider.logger.info(f"Creating new release with ID: {item.id}")

                # Commit the transaction
                self.session.commit()
                spider.logger.info(f"Successfully processed release with ID: {item.id}")

            except Exception as e:
                self.session.rollback()
                spider.logger.error(f"Error processing release with ID: {item.id}")
                spider.logger.error(str(e))
                raise
            finally:
                self.session.close()

            # Return a deferred that has already fired
            return defer.succeed(item)
        return item

    def close_spider(self, spider):
        self.session.close()


class AvailableFilesPipeline(FilesPipeline):
    def get_media_requests(self, item, info):
        if isinstance(item, DirectDownloadItem):
            file_path = self.file_path(None, None, info, 
                release_id=item['release_id'], 
                file_info=item['file_info'])
            
            full_path = os.path.join(self.store.basedir, file_path)
            if not os.path.exists(full_path):
                return [Request(
                    item['url'], 
                    meta={
                        'release_id': item['release_id'],
                        'file_info': item['file_info']
                    }
                )]
            else:
                logging.info(f"File already exists, skipping download: {full_path}")
        return []

    def file_path(self, request, response=None, info=None, *, item=None, release_id=None, file_info=None):
        if request:
            release_id = request.meta['release_id']
            file_info = request.meta['file_info']

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
            release_name = release.name
            site_name = site.name
            
            # Extract file extension from the URL
            url_path = urlparse(file_info['url']).path
            file_extension = os.path.splitext(url_path)[1]
            
            # Create filename in the specified format
            if file_info['file_type'] == 'video':
                filename = f"{site_name} - {release_date} - {release_name} - {file_info['resolution_width']}x{file_info['resolution_height']} - {release_id}{file_extension}"
            else:
                filename = f"{site_name} - {release_date} - {release_name} - {file_info['variant']} - {release_id}{file_extension}"
            
            # Remove path separators from filename
            filename = filename.replace('/', '').replace('\\', '')
            
            # Create a folder structure based on site and release ID
            folder = f"{site_name}/Metadata/{release_id}"
            
            return f'{folder}/{filename}'
        finally:
            session.close()

    # def item_completed(self, results, item, info):
    #     file_paths = [x["path"] for ok, x in results if ok]
    #     if not file_paths:
    #         raise DropItem("Item contains no files")
    #     adapter = ItemAdapter(item)
    #     adapter["file_paths"] = file_paths
    #     return item

    def item_completed(self, results, item, info):
        if isinstance(item, DirectDownloadItem):
            file_paths = [x['path'] for ok, x in results if ok]
            if file_paths:
                file_info = item['file_info']
                file_metadata = self.process_file_metadata(file_paths[0], file_info['file_type'])
                
                return DownloadedFileItem(
                    uuid=newnewid.uuid7(),
                    downloaded_at=datetime.now(),
                    file_type=file_info['file_type'],
                    content_type=file_info.get('content_type'),
                    variant=file_info.get('variant'),
                    available_file=file_info,
                    original_filename=os.path.basename(item['url'].split('?')[0]),
                    saved_filename=os.path.basename(file_paths[0]),
                    release_uuid=item['release_id'],
                    file_metadata=file_metadata
                )
        return item

    def process_file_metadata(self, file_path, file_type):
        if file_type == 'video':
            return self.process_video_metadata(file_path)
        else:
            return self.process_generic_metadata(file_path, file_type)

    def process_video_metadata(self, file_path):
        result = subprocess.run(['C:\\Tools\\videohashes-windows-amd64.exe', '-json', '-md5', file_path], capture_output=True, text=True)
        
        if result.returncode == 0:
            video_hashes = json.loads(result.stdout)
            return {
                "$type": "VideoHashes",
                "duration": video_hashes.get("duration"),
                "phash": video_hashes.get("phash"),
                "oshash": video_hashes.get("oshash"),
                "md5": video_hashes.get("md5")
            }
        else:
            self.logger.error(f"Failed to get video hashes: {result.stderr}")
            return {}

    def process_generic_metadata(self, file_path, file_type):
        if file_type == 'zip':
            type = "GalleryZipFileMetadata"
        elif file_type == 'image':
            type = "ImageFileMetadata"
        elif file_type == 'vtt':
            type = "VttFileMetadata"
        
        sha256_hash = hashlib.sha256()
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                md5_hash.update(byte_block)
        sha256_sum = sha256_hash.hexdigest()
        md5_sum = md5_hash.hexdigest()

        return {
            "$type": type,
            "sha256Sum": sha256_sum,
            "md5Sum": md5_sum
        }