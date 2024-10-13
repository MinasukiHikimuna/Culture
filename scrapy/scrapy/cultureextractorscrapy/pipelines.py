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

from .spiders.database import get_session, Site, Release, DownloadedFile
from .items import ReleaseAndDownloadsItem, ReleaseItem, AvailableVideoFile, AvailableImageFile, AvailableGalleryZipFile, DownloadedFileItem
from datetime import datetime
import json
from sqlalchemy.exc import IntegrityError

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import subprocess
import hashlib


class PostgresPipeline:
    def __init__(self):
        self.session = get_session()

    def process_item(self, item, spider):
        if isinstance(item, ReleaseItem):
            return self.process_release(item, spider)
        elif isinstance(item, DownloadedFileItem):
            return self.process_downloaded_file(item, spider)
        return item

    def process_release(self, item, spider):
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

        try:
            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            import traceback
            spider.logger.error(f"IntegrityError while processing release with ID: {item.id}")
            spider.logger.error(traceback.format_exc())
            spider.logger.error(f"IntegrityError details: {str(e)}")

    def process_downloaded_file(self, item, spider):
        existing_file = self.session.query(DownloadedFile).filter_by(
            release_uuid=str(item.release_id),
            file_url=item.file_url
        ).first()

        if existing_file:
            # Update existing file
            existing_file.file_path = item.file_path
            existing_file.file_type = item.file_type
            existing_file.content_type = item.content_type
            existing_file.variant = item.variant
            existing_file.resolution_width = item.resolution_width
            existing_file.resolution_height = item.resolution_height
            spider.logger.info(f"Updating existing downloaded file: {item.file_path}")
        else:
            # Create new file
            new_file = DownloadedFile(
                release_uuid=str(item.release_id),
                file_path=item.file_path,
                file_url=item.file_url,
                file_type=item.file_type,
                content_type=item.content_type,
                variant=item.variant,
                resolution_width=item.resolution_width,
                resolution_height=item.resolution_height
            )
            self.session.add(new_file)
            spider.logger.info(f"Creating new downloaded file: {item.file_path}")

        try:
            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            spider.logger.error(f"IntegrityError while processing downloaded file: {item.file_path}")
            spider.logger.error(str(e))

        return item

    def close_spider(self, spider):
        self.session.close()


class AvailableFilesPipeline(FilesPipeline):
    def get_media_requests(self, item, info):
        logging.info(f"get_media_requests called for item: {item}")
        if isinstance(item, ReleaseItem):
            available_files = json.loads(item.available_files)
            largest_zip_gallery = None
            largest_video = None
            largest_zip_size = 0
            largest_video_size = 0
            
            for file in available_files:
                if file['file_type'] == 'zip' and file.get('content_type') == 'gallery':
                    file_size = file.get('resolution_width', 0)
                    if file_size > largest_zip_size:
                        largest_zip_size = file_size
                        largest_zip_gallery = file
                elif file['file_type'] == 'video' and file.get('content_type') == 'scene':
                    file_size = file.get('resolution_width', 0) * file.get('resolution_height', 0)
                    if file_size > largest_video_size:
                        largest_video_size = file_size
                        largest_video = file
                else:
                    file_path = self.file_path(None, None, info, item=item, file_info=file)
                    full_path = os.path.join(self.store.basedir, file_path)
                    if not os.path.exists(full_path):
                        yield Request(file['url'], meta={'item': item, 'file_info': file})
                    else:
                        logging.info(f"File already exists, skipping download: {full_path}")
                        file['local_path'] = file_path
            
            for file in [largest_zip_gallery, largest_video]:
                if file:
                    file_path = self.file_path(None, None, info, item=item, file_info=file)
                    full_path = os.path.join(self.store.basedir, file_path)
                    if not os.path.exists(full_path):
                        # yield Request(file['url'], meta={'item': item, 'file_info': file})
                        pass
                    else:
                        logging.info(f"File already exists, skipping download: {full_path}")
                        file['local_path'] = file_path

    def file_path(self, request, response=None, info=None, *, item=None, file_info=None):
        logging.info(f"file_path called for request: {request}")
        if request:
            item = request.meta['item']
            file_info = request.meta['file_info']
        
        # Extract file extension from the URL
        url_path = urlparse(file_info['url']).path
        file_extension = os.path.splitext(url_path)[1]
        
        # If the extension is .php, extract the real extension from the 'file' parameter
        if file_extension.lower() == '.php':
            query = urlparse(file_info['url']).query
            query_params = dict(param.split('=') for param in query.split('&') if '=' in param)
            if 'file' in query_params:
                file_param = query_params['file']
                _, file_extension = os.path.splitext(file_param)
        
        # Create filename in the specified format
        date_str = item.release_date
        if file_info['file_type'] == 'video' and 'resolution_height' in file_info and file_info['resolution_height']:
            filename = f"{item.site.name} - {date_str} - {item.name} - {file_info['resolution_width']}x{file_info['resolution_height']} - {item.id}{file_extension}"
        elif file_info['file_type'] == 'zip':
            filename = f"{item.site.name} - {date_str} - {item.name} - {file_info['variant']} - {item.id}{file_extension}"
        else:
            filename = f"{item.site.name} - {date_str} - {item.name} - {item.id}{file_extension}"
        
        # Remove path separators from filename
        filename = filename.replace('/', '').replace('\\', '')
        
        # Create a folder structure based on release ID
        folder = f"{item.site.name}/Metadata/{item.id}"
        
        path = f'{folder}/{filename}'
        logging.info(f"File will be saved to: {path}")
        return path

    # def item_completed(self, results, item, info):
    #     file_paths = [x["path"] for ok, x in results if ok]
    #     if not file_paths:
    #         raise DropItem("Item contains no files")
    #     adapter = ItemAdapter(item)
    #     adapter["file_paths"] = file_paths
    #     return item

    def item_completed(self, results, item, info):
        logging.info(f"item_completed called for item: {item}")
        logging.info(f"Results: {results}")
        
        file_paths = [x['path'] for ok, x in results if ok]
        if not file_paths:
            raise DropItem("Item contains no files")
        
        downloaded_files = []
        if isinstance(item, ReleaseItem):
            logging.info(f"Processing release item {item.id}")
            
            downloaded_files = [x for ok, x in results if ok]
            logging.info(f"Downloaded files: {downloaded_files}")
            available_files = json.loads(item.available_files)
            for file in available_files:
                logging.info(f"Processing file: {file}")
                
                matching_downloads = [x for x in downloaded_files if x['url'] == file['url']]
                if matching_downloads:
                    file['local_path'] = matching_downloads[0]['path']
                    
                    # Process file metadata
                    file_info = matching_downloads[0]
                    file_metadata = self.process_file_metadata(file_info['path'], file['file_type'])
                    
                    # Create DownloadedFileItem
                    downloaded_file_item = DownloadedFileItem(
                        uuid=newnewid.uuid7(),
                        downloaded_at=datetime.now(),
                        file_type=file['file_type'],
                        content_type=file.get('content_type'),
                        variant=file.get('variant'),
                        available_file=file,
                        original_filename=file['url'],
                        saved_filename=file_info['path'],
                        release_uuid=str(item.id),
                        file_metadata=file_metadata
                    )
                    downloaded_files.append(downloaded_file_item)
        
        return ReleaseAndDownloadsItem(release=item, downloaded_files=downloaded_files)

    def process_file_metadata(self, file_path, file_type):
        if file_type == 'video':
            return self.process_video_metadata(file_path)
        else:
            return self.process_file_metadata(file_path, file_type)

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

    def process_file_metadata(self, file_path, file_type):
        if file_type == 'zip':
            type = "GalleryZipFileMetadata"
        elif file_type == 'image':
            type = "ImageFileMetadata"
        elif file_type == 'vtt':
            type = "VttFileMetadata"
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        sha256_sum = sha256_hash.hexdigest()

        return {
            "$type": type,
            "sha256Sum": sha256_sum
        }
