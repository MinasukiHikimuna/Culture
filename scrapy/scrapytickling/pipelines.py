# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import os
from urllib.parse import urlparse
from scrapy.pipelines.files import FilesPipeline
from scrapy import Request

from .spiders.database import get_session, Site, Release
from .items import ReleaseItem
from datetime import datetime
import json
from sqlalchemy.exc import IntegrityError

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import logging

class ScrapyticklingPipeline:
    def process_item(self, item, spider):
        return item


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


class PreviewImagesPipeline(FilesPipeline):
    def get_media_requests(self, item, info):
        if isinstance(item, ReleaseItem):
            json_data = json.loads(item.json_document)
            preview_image_url = json_data.get('preview_image_url')
            if preview_image_url:
                logging.info(f"Requesting preview image: {preview_image_url}")
                yield Request(preview_image_url, meta={'item': item})
            else:
                logging.warning(f"No preview image URL found for item: {item.short_name}")

    def file_path(self, request, response=None, info=None, *, item=None):
        logging.info("file_path method called") 
        item = request.meta['item']
        filename = os.path.basename(urlparse(request.url).path)
        path = f'{item.site.name}/Metadata/{item.id}/{filename}'
        logging.info(f"File will be saved to: {path}")
        return path

    def item_completed(self, results, item, info):
        logging.info("item_completed method called")
        if isinstance(item, ReleaseItem):
            file_paths = [x['path'] for ok, x in results if ok]
            if file_paths:
                json_data = json.loads(item.json_document)
                json_data['preview_image_local_path'] = file_paths[0]
                item.json_document = json.dumps(json_data)
                logging.info(f"Updated item with local path: {file_paths[0]}")
            else:
                logging.warning(f"No files were successfully downloaded for item: {item.short_name}")
        return item
