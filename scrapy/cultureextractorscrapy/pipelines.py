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

            release = Release(
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

            try:
                self.session.add(release)
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                spider.logger.warning(f"Release with short_name {item.short_name} already exists. Skipping.")

        return item

    def close_spider(self, spider):
        self.session.close()


class AvailableFilesPipeline(FilesPipeline):
    def get_media_requests(self, item, info):
        if isinstance(item, ReleaseItem):
            available_files = json.loads(item.available_files)
            for file in available_files:
                if file['file_type'] in ['video', 'image', 'gallery']:
                    yield Request(file['url'], meta={'item': item, 'file_info': file})

    def file_path(self, request, response=None, info=None, *, item=None):
        item = request.meta['item']
        file_info = request.meta['file_info']
        
        # Extract file extension from the URL
        url_path = urlparse(request.url).path
        file_extension = os.path.splitext(url_path)[1]
        
        # If the extension is .php, extract the real extension from the 'file' parameter
        if file_extension.lower() == '.php':
            query = urlparse(request.url).query
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
            if downloaded_files:
                available_files = json.loads(item.available_files)
                for file in available_files:
                    matching_downloads = [x for x in downloaded_files if x['url'] == file['url']]
                    if matching_downloads:
                        file['local_path'] = matching_downloads[0]['path']
                item.available_files = json.dumps(available_files)
                logging.info(f"Updated item with local paths for {len(downloaded_files)} files")
            else:
                logging.warning(f"No files were successfully downloaded for item: {item.short_name}")
        return item
