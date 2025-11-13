# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import json
import uuid
from abc import ABC
from dataclasses import dataclass
from datetime import datetime

import scrapy


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
    resolution_width: int | None = None
    resolution_height: int | None = None
    file_size: float | None = None


@dataclass
class AvailableImageFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str
    resolution_width: int | None = None
    resolution_height: int | None = None
    file_size: float | None = None


@dataclass
class AvailableVideoFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str
    resolution_width: int | None = None
    resolution_height: int | None = None
    file_size: float | None = None
    fps: float | None = None
    codec: str | None = None


@dataclass
class AvailableAudioFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str
    file_size: float | None = None
    duration: float | None = None  # Duration in seconds
    bitrate: int | None = None  # Bitrate in kbps
    sample_rate: int | None = None  # Sample rate in Hz
    channels: int | None = None  # Number of audio channels
    codec: str | None = None  # Audio codec (mp3, aac, ogg, etc.)
    sha256_hash: str | None = None  # SHA-256 hash for integrity checking


@dataclass
class AvailableVttFile(IAvailableFile):
    file_type: str
    content_type: str
    variant: str
    url: str


AvailableFileType = (
    AvailableGalleryZipFile
    | AvailableImageFile
    | AvailableVideoFile
    | AvailableAudioFile
    | AvailableVttFile
)


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


class M3u8DownloadItem(scrapy.Item):
    release_id = scrapy.Field()
    file_info = scrapy.Field()
    url = scrapy.Field()
    output_path = scrapy.Field()


# Backward compatibility alias
FfmpegDownloadItem = M3u8DownloadItem
