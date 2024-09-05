# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class ScrapyticklingPipeline:
    def process_item(self, item, spider):
        return item

from .spiders.database import get_session, Site, Release
from .items import ReleaseItem
from datetime import datetime
import json

class PostgresPipeline:
    def __init__(self):
        self.session = get_session()

    def process_item(self, item, spider):
        if isinstance(item, ReleaseItem):
            site = self.session.query(Site).filter_by(uuid=str(item.site_uuid)).first()
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

            self.session.add(release)
            self.session.commit()

        return item

    def close_spider(self, spider):
        self.session.close()
