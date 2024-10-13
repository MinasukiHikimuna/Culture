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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

class IAvailableFile(ABC):
    file_type: str
    content_type: str
    variant: str
    url: str

@dataclass
class AvailableGalleryZipFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    file_size: Optional[float] = None

@dataclass
class AvailableImageFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    file_size: Optional[float] = None

@dataclass
class AvailableVideoFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    file_size: Optional[float] = None
    fps: Optional[float] = None
    codec: Optional[str] = None

@dataclass
class AvailableVttFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str

import json
from typing import Union

AvailableFileType = Union[AvailableGalleryZipFile, AvailableImageFile, AvailableVideoFile, AvailableVttFile]

class AvailableFileEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, IAvailableFile):
            result = obj.__dict__.copy()
            result['__type__'] = obj.__class__.__name__
            return result
        return super().default(obj)

def available_file_decoder(dct):
    if '__type__' in dct:
        class_name = dct.pop('__type__')
        cls = globals()[class_name]
        return cls(**dct)
    return dct

class DownloadedFileItem(scrapy.Item):
    uuid = scrapy.Field()
    downloaded_at = scrapy.Field()
    file_type = scrapy.Field()
    content_type = scrapy.Field()
    variant = scrapy.Field()
    available_file = scrapy.Field()
    original_filename = scrapy.Field()
    saved_filename = scrapy.Field()
    release_uuid = scrapy.Field()
    file_metadata = scrapy.Field()
