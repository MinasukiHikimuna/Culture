# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import os
from urllib.parse import urlparse
from scrapy.pipelines.files import FilesPipeline
from scrapy import Request

from .spiders.database import get_session, Site, Release
from .items import ReleaseItem, AvailableVideoFile, AvailableImageFile, AvailableGalleryZipFile
from datetime import datetime
import json
from sqlalchemy.exc import IntegrityError

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import logging


class PostgresPipeline:
    def __init__(self):
        self.session = get_session()

    def process_item(self, item, spider):
        if isinstance(item, ReleaseItem):
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

        return item

    def close_spider(self, spider):
        self.session.close()


class AvailableFilesPipeline(FilesPipeline):
    def get_media_requests(self, item, info):
        if isinstance(item, ReleaseItem):
            available_files = json.loads(item.available_files)
            for file in available_files:
                if file['file_type'] in ['video', 'image', 'gallery']:
                    file_path = self.file_path(None, None, info, item=item, file_info=file)
                    full_path = os.path.join(self.store.basedir, file_path)
                    if not os.path.exists(full_path):
                        yield Request(file['url'], meta={'item': item, 'file_info': file})
                    else:
                        logging.info(f"File already exists, skipping download: {full_path}")
                        file['local_path'] = file_path

    def file_path(self, request, response=None, info=None, *, item=None, file_info=None):
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
            filename = f"{item.site.name} - {date_str} - {item.name} - {item.id} - {file_info['resolution_width']}x{file_info['resolution_height']}{file_extension}"
        else:
            filename = f"{item.site.name} - {date_str} - {item.name} - {item.id}{file_extension}"
        
        # Remove path separators from filename
        filename = filename.replace('/', '').replace('\\', '')
        
        # Create a folder structure based on release ID
        folder = f"{item.site.name}/Metadata/{item.id}"
        
        path = f'{folder}/{filename}'
        logging.info(f"File will be saved to: {path}")
        return path

    def item_completed(self, results, item, info):
        if isinstance(item, ReleaseItem):
            downloaded_files = [x for ok, x in results if ok]
            available_files = json.loads(item.available_files)
            for file in available_files:
                if 'local_path' not in file:
                    matching_downloads = [x for x in downloaded_files if x['url'] == file['url']]
                    if matching_downloads:
                        file['local_path'] = matching_downloads[0]['path']
            item.available_files = json.dumps(available_files)
            logging.info(f"Updated item with local paths for {len([f for f in available_files if 'local_path' in f])} files")
        return item
