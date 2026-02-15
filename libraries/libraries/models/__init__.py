"""SQLAlchemy models for Culture platform."""

from .base import Base, get_engine, get_session
from .culture_extractor import (
    Download,
    Performer,
    PerformerExternalId,
    Release,
    ReleaseExternalId,
    Site,
    SiteExternalId,
    StorageState,
    SubSite,
    SubSiteExternalId,
    Tag,
    TagExternalId,
    TargetSystem,
    release_performer,
    release_tag,
)


__all__ = [
    # Base
    "Base",
    "get_engine",
    "get_session",
    # Models
    "Site",
    "SubSite",
    "Release",
    "Performer",
    "Tag",
    "Download",
    "StorageState",
    "TargetSystem",
    # External ID models
    "SiteExternalId",
    "SubSiteExternalId",
    "ReleaseExternalId",
    "PerformerExternalId",
    "TagExternalId",
    # Junction tables
    "release_performer",
    "release_tag",
]
