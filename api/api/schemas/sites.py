"""Pydantic schemas for sites endpoints."""

from pydantic import BaseModel, Field


class Site(BaseModel):
    """Site response model."""

    ce_sites_uuid: str = Field(description="Site UUID")
    ce_sites_short_name: str = Field(description="Short name identifier")
    ce_sites_name: str = Field(description="Full site name")
    ce_sites_url: str = Field(description="Site URL")


class SiteWithLinkStatus(Site):
    """Site with link status information."""

    has_stashapp_link: bool = Field(description="Whether site is linked to Stashapp")
    has_stashdb_link: bool = Field(description="Whether site is linked to StashDB")


class SiteExternalIds(BaseModel):
    """External IDs for a site."""

    stashapp: str | None = Field(default=None, description="Stashapp studio ID")
    stashdb: str | None = Field(default=None, description="StashDB studio ID")


class SiteDetail(Site):
    """Detailed site information including external IDs."""

    external_ids: SiteExternalIds = Field(description="External system IDs")


class LinkSiteRequest(BaseModel):
    """Request body for linking a site to external systems."""

    target: str = Field(description="Target system name (stashapp or stashdb)")
    external_id: str = Field(description="External ID value")
