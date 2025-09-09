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
class SubSiteItem:
    id: uuid.UUID
    short_name: str
    name: str
    site_uuid: uuid.UUID


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
    sub_site_uuid: uuid.UUID = None  # Optional field for subsite UUID
    sub_site: SubSiteItem = None  # Optional field for subsite object


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
class AvailableAudioFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str
    file_size: Optional[float] = None
    duration: Optional[float] = None  # Duration in seconds
    bitrate: Optional[int] = None  # Bitrate in kbps
    sample_rate: Optional[int] = None  # Sample rate in Hz
    channels: Optional[int] = None  # Number of audio channels
    codec: Optional[str] = None  # Audio codec (mp3, aac, ogg, etc.)
    sha256_hash: Optional[str] = None  # SHA-256 hash for integrity checking


@dataclass
class AvailableVttFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str


import json
from typing import Union

AvailableFileType = Union[
    AvailableGalleryZipFile,
    AvailableImageFile,
    AvailableVideoFile,
    AvailableAudioFile,
    AvailableVttFile,
]


class AvailableFileEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, IAvailableFile):
            result = obj.__dict__.copy()
            result["__type__"] = obj.__class__.__name__
            return result
        return super().default(obj)


def available_file_decoder(dct):
    if "__type__" in dct:
        class_name = dct.pop("__type__")
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


@dataclass
class ReleaseAndDownloadsItem:
    release: ReleaseItem
    downloaded_files: list[DownloadedFileItem]


class DirectDownloadItem(scrapy.Item):
    release_id = scrapy.Field()
    file_info = scrapy.Field()
    url = scrapy.Field()


class FfmpegDownloadItem(scrapy.Item):
    release_id = scrapy.Field()
    file_info = scrapy.Field()
    url = scrapy.Field()
    output_path = scrapy.Field()
