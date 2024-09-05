# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

from datetime import datetime
import scrapy
import uuid
from dataclasses import dataclass

@dataclass
class SiteItem:
    id: uuid.UUID
    short_name: str
    name: str
    url: str

@dataclass
class SiteTagItem:
    id: uuid.UUID
    short_name: str
    name: str
    url: str
    site_uuid: uuid.UUID

@dataclass
class SitePerformerItem:
    id: uuid.UUID
    short_name: str
    name: str
    url: str
    site_uuid: uuid.UUID

@dataclass
class ReleaseItem:
    id: uuid.UUID
    release_date: str
    short_name: str
    name: str
    url: str
    description: str
    duration: float
    created: datetime
    last_updated: datetime
    performers: list[SitePerformerItem]
    tags: list[SiteTagItem]
    available_files: str
    json_document: str
    site_uuid: uuid.UUID
    site: SiteItem
