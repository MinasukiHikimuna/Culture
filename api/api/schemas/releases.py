"""Pydantic schemas for releases endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class Release(BaseModel):
    """Basic release response model for list endpoints."""

    ce_site_uuid: str = Field(description="Site UUID")
    ce_site_name: str = Field(description="Site name")
    ce_release_uuid: str = Field(description="Release UUID")
    ce_release_date: date | None = Field(description="Release date")
    ce_release_short_name: str = Field(description="Short name identifier")
    ce_release_name: str = Field(description="Release title")
    ce_release_url: str = Field(description="Release URL")
    ce_release_description: str | None = Field(default=None, description="Release description")
    ce_release_created: datetime = Field(description="When the release was created in CE")
    ce_release_last_updated: datetime = Field(description="When the release was last updated")
    ce_release_available_files: str | None = Field(default=None, description="Available files JSON")
    ce_release_json_document: str | None = Field(default=None, description="Raw JSON document")


class ReleaseExternalIds(BaseModel):
    """External IDs for a release."""

    stashapp: str | None = Field(default=None, description="Stashapp scene ID")
    stashdb: str | None = Field(default=None, description="StashDB scene ID")


class ReleasePerformer(BaseModel):
    """Performer associated with a release."""

    ce_performers_uuid: str = Field(description="Performer UUID")
    ce_performers_short_name: str = Field(description="Short name identifier")
    ce_performers_name: str = Field(description="Performer name")
    ce_performers_url: str | None = Field(default=None, description="Performer URL")
    ce_performers_stashapp_id: str | None = Field(default=None, description="Stashapp performer ID")
    ce_performers_stashdb_id: str | None = Field(default=None, description="StashDB performer ID")


class ReleaseTag(BaseModel):
    """Tag associated with a release."""

    ce_tags_uuid: str = Field(description="Tag UUID")
    ce_tags_short_name: str = Field(description="Short name identifier")
    ce_tags_name: str = Field(description="Tag name")
    ce_tags_url: str | None = Field(default=None, description="Tag URL")


class ReleaseDownload(BaseModel):
    """Downloaded file for a release."""

    ce_downloads_uuid: str = Field(description="Download UUID")
    ce_downloads_downloaded_at: datetime = Field(description="When the file was downloaded")
    ce_downloads_file_type: str = Field(description="File type (video, image, zip)")
    ce_downloads_content_type: str = Field(description="Content type (scene, cover, gallery)")
    ce_downloads_variant: str | None = Field(default=None, description="Quality variant")
    ce_downloads_available_file: str | None = Field(default=None, description="Available file JSON")
    ce_downloads_original_filename: str | None = Field(default=None, description="Original filename")
    ce_downloads_saved_filename: str | None = Field(default=None, description="Saved filename")
    ce_downloads_file_metadata: str | None = Field(default=None, description="File metadata JSON")
    ce_downloads_hash_oshash: str | None = Field(default=None, description="OSHash")
    ce_downloads_hash_phash: str | None = Field(default=None, description="PHash")
    ce_downloads_hash_sha256: str | None = Field(default=None, description="SHA256 hash")


class ReleaseDetail(Release):
    """Detailed release information including related data."""

    external_ids: ReleaseExternalIds = Field(description="External system IDs")
    performers: list[ReleasePerformer] = Field(default_factory=list, description="Performers in the release")
    tags: list[ReleaseTag] = Field(default_factory=list, description="Tags for the release")
    downloads: list[ReleaseDownload] = Field(default_factory=list, description="Downloaded files")


class LinkReleaseRequest(BaseModel):
    """Request body for linking a release to external systems."""

    target: str = Field(description="Target system name (stashapp or stashdb)")
    external_id: str = Field(description="External ID value")


class DeletedDownload(BaseModel):
    """Information about a deleted download."""

    uuid: str = Field(description="Download UUID")
    saved_filename: str | None = Field(default=None, description="Saved filename")


class DeleteReleaseResponse(BaseModel):
    """Response from deleting a release."""

    message: str = Field(description="Success message")
    release_uuid: str = Field(description="Deleted release UUID")
    release_name: str = Field(description="Deleted release name")
    site_name: str = Field(description="Site name")
    downloads: list[DeletedDownload] = Field(default_factory=list, description="Deleted download records")
