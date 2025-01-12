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
from .items import ReleaseAndDownloadsItem, ReleaseItem, AvailableVideoFile, AvailableImageFile, AvailableGalleryZipFile, DownloadedFileItem
from datetime import datetime
import json
from sqlalchemy.exc import IntegrityError

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import subprocess
import hashlib

from .spiders.database import Site, Release, DownloadedFile


class PostgresPipeline:
    def __init__(self):
        self.session = get_session()

    def process_item(self, item, spider):
        if isinstance(item, ReleaseAndDownloadsItem):
            return self.process_release_and_downloads(item, spider)
        return item

    def process_release_and_downloads(self, item, spider):
        release_item = item.release
        downloaded_files = item.downloaded_files

        try:
            site = self.session.query(Site).filter_by(uuid=release_item.site_uuid).first()
            if not site:
                spider.logger.error(f"Site not found for UUID: {release_item.site_uuid}")
                return item

            existing_release = self.session.query(Release).filter_by(uuid=str(release_item.id)).first()

            if existing_release:
                # Update existing release
                existing_release.release_date = datetime.fromisoformat(release_item.release_date) if release_item.release_date else None
                existing_release.short_name = release_item.short_name
                existing_release.name = release_item.name
                existing_release.url = release_item.url
                existing_release.description = release_item.description
                existing_release.duration = release_item.duration
                existing_release.last_updated = release_item.last_updated
                existing_release.available_files = release_item.available_files
                existing_release.json_document = release_item.json_document
                spider.logger.info(f"Updating existing release with ID: {release_item.id}")
            else:
                # Create new release
                new_release = Release(
                    uuid=str(release_item.id),
                    release_date=datetime.fromisoformat(release_item.release_date) if release_item.release_date else None,
                    short_name=release_item.short_name,
                    name=release_item.name,
                    url=release_item.url,
                    description=release_item.description,
                    duration=release_item.duration,
                    created=release_item.created,
                    last_updated=release_item.last_updated,
                    available_files=release_item.available_files,
                    json_document=release_item.json_document,
                    site_uuid=str(release_item.site_uuid)
                )
                self.session.add(new_release)
                spider.logger.info(f"Creating new release with ID: {release_item.id}")

            # Process downloaded files
            for file_item in downloaded_files:
                existing_file = self.session.query(DownloadedFile).filter_by(
                    release_uuid=str(release_item.id),
                    file_type=file_item['file_type'],
                    content_type=file_item['content_type'],
                    variant=file_item['variant']
                ).first()

                if existing_file:
                    # Existing file, do nothing
                    pass
                else:
                    # Create new file
                    new_file = DownloadedFile(
                        uuid=newnewid.uuid7(),
                        downloaded_at=datetime.now(),
                        file_type=file_item['file_type'],
                        content_type=file_item['content_type'],
                        variant=file_item['variant'],
                        available_file=file_item['available_file'],
                        original_filename=file_item['original_filename'],
                        saved_filename=file_item['saved_filename'],
                        release_uuid=str(file_item['release_uuid']),
                        file_metadata=file_item['file_metadata']
                    )
                    self.session.add(new_file)
                    spider.logger.info(f"Creating new downloaded file: {file_item['saved_filename']}")

            # Commit the transaction
            self.session.commit()
            spider.logger.info(f"Successfully processed release and downloads for ID: {release_item.id}")

        except IntegrityError as e:
            self.session.rollback()
            spider.logger.error(f"IntegrityError while processing release and downloads with ID: {release_item.id}")
            spider.logger.error(str(e))
        except Exception as e:
            self.session.rollback()
            spider.logger.error(f"Error processing release and downloads with ID: {release_item.id}")
            spider.logger.error(str(e))
        finally:
            self.session.close()

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
                        yield Request(file['url'], meta={'item': item, 'file_info': file})
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
        elif file_info['file_type'] == 'image':
            filename = f"{item.site.name} - {date_str} - {item.name} - {file_info['variant']} - {item.id}{file_extension}"
        else:
            filename = f"{item.site.name} - {date_str} - {item.name} - {item.id}{file_extension}"
        
        # Remove path separators from filename
        filename = filename.replace('/', '').replace('\\', '')
        
        # Create a folder structure based on release ID
        folder = f"{item.site.name}/Metadata/{item.id}"
        
        relative_path = f'{folder}/{filename}'
        
        # Get the FILES_STORE setting
        settings = get_project_settings()
        files_store = settings.get('FILES_STORE')
        
        # Create the absolute path
        absolute_path = os.path.join(files_store, relative_path)
        
        logging.info(f"File will be saved to: {absolute_path}")
        return absolute_path

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
            
            result_files = [x for ok, x in results if ok]
            logging.info(f"Downloaded files: {result_files}")
            available_files = json.loads(item.available_files)
            for file in available_files:
                logging.info(f"Processing file: {file}")
                
                matching_downloads = [x for x in result_files if x['url'] == file['url']]
                if matching_downloads:
                    # Process file metadata
                    file_info = matching_downloads[0]
                    file_metadata = self.process_file_metadata(file_info['path'], file['file_type'])
                    
                    # Extract the original filename from the URL
                    parsed_url = urlparse(file['url'])
                    original_filename = os.path.basename(parsed_url.path)
                    # Remove query parameters if present
                    original_filename = original_filename.split('?')[0]
                  
                    saved_filename = os.path.basename(file_info['path'])
                    
                    # Create DownloadedFileItem
                    downloaded_file_item = DownloadedFileItem(
                        uuid=newnewid.uuid7(),
                        downloaded_at=datetime.now(),
                        file_type=file['file_type'],
                        content_type=file.get('content_type'),
                        variant=file.get('variant'),
                        available_file=file,
                        original_filename=original_filename,
                        saved_filename=saved_filename,  # This is now an absolute path
                        release_uuid=str(item.id),
                        file_metadata=file_metadata
                    )
                    downloaded_files.append(downloaded_file_item)
        
        return ReleaseAndDownloadsItem(release=item, downloaded_files=downloaded_files)

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