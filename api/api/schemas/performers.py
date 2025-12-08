"""Pydantic schemas for performers API."""

from pydantic import BaseModel


class Performer(BaseModel):
    """Basic performer information."""

    ce_performers_uuid: str
    ce_performers_short_name: str | None
    ce_performers_name: str
    ce_performers_url: str | None


class PerformerWithSite(Performer):
    """Performer with site information."""

    ce_site_uuid: str | None = None
    ce_site_name: str | None = None
    ce_sites_short_name: str | None = None
    ce_sites_name: str | None = None


class PerformerWithLinkStatus(PerformerWithSite):
    """Performer with external link status for list views."""

    has_stashapp_link: bool = False
    has_stashdb_link: bool = False


class PerformerExternalIds(BaseModel):
    """External IDs for a performer."""

    stashapp: str | None = None
    stashdb: str | None = None


class PerformerDetail(Performer):
    """Detailed performer information including external IDs."""

    ce_sites_short_name: str | None = None
    ce_sites_name: str | None = None
    external_ids: PerformerExternalIds


class LinkPerformerRequest(BaseModel):
    """Request to link a performer to an external system."""

    target: str
    external_id: str


class BatchLinkItem(BaseModel):
    """Single item in a batch link request."""

    performer_uuid: str
    stashapp_id: str | None = None
    stashdb_id: str | None = None


class BatchLinkRequest(BaseModel):
    """Request to link multiple performers at once."""

    links: list[BatchLinkItem]


class BatchLinkResult(BaseModel):
    """Result of a batch link operation."""

    performer_uuid: str
    success: bool
    error: str | None = None


class BatchLinkResponse(BaseModel):
    """Response from batch link operation."""

    results: list[BatchLinkResult]
    successful: int
    failed: int


class StashDBSearchResult(BaseModel):
    """StashDB performer search result."""

    id: str
    name: str
    disambiguation: str | None = None
    aliases: list[str] = []
    country: str | None = None
    image_url: str | None = None


class StashappSearchResult(BaseModel):
    """Stashapp performer search result."""

    id: int
    name: str
    disambiguation: str | None = None
    aliases: list[str] = []
    stashdb_id: str | None = None


# Phase 2: Face matching schemas (to be used later)


class FaceRecognitionMatch(BaseModel):
    """A single face recognition match result."""

    name: str
    confidence: int
    country: str | None = None
    performer_url: str | None = None
    image: str | None = None


class FaceRecognitionFace(BaseModel):
    """A detected face with its matches."""

    confidence: float
    area: int | None = None
    performers: list[FaceRecognitionMatch]


class FaceRecognitionResult(BaseModel):
    """Face recognition API result."""

    success: bool
    error: str | None = None
    results: list[FaceRecognitionFace] = []


class PerformerRelease(BaseModel):
    """A release linked to a performer."""

    ce_release_uuid: str
    ce_release_date: str | None = None
    ce_release_short_name: str
    ce_release_name: str
    ce_release_url: str | None = None
    ce_site_uuid: str
    ce_site_name: str
