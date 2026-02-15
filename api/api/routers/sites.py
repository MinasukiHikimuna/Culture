"""Sites API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_ce_client
from api.schemas.sites import (
    CreateSiteRequest,
    CreateSiteResponse,
    LinkSiteRequest,
    Site,
    SiteDetail,
    SiteExternalIds,
    SiteWithLinkStatus,
)
from libraries.client_culture_extractor import ClientCultureExtractor


router = APIRouter()


@router.get("")
def list_sites(
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
    linked: Annotated[
        bool | None,
        Query(description="Filter by link status: true=linked, false=unlinked, null=all"),
    ] = None,
) -> list[Site] | list[SiteWithLinkStatus]:
    """List all sites.

    Optionally filter by link status (linked to Stashapp/StashDB or not).
    """
    sites_df = client.get_sites()

    if linked is None:
        return [Site(**row) for row in sites_df.to_dicts()]

    site_uuids = sites_df["ce_sites_uuid"].to_list()
    link_status = []

    for uuid in site_uuids:
        external_ids = client.get_site_external_ids(uuid)
        has_stashapp = "stashapp" in external_ids
        has_stashdb = "stashdb" in external_ids
        link_status.append({
            "has_stashapp_link": has_stashapp,
            "has_stashdb_link": has_stashdb,
            "is_linked": has_stashapp or has_stashdb,
        })

    results = []
    for row, status in zip(sites_df.to_dicts(), link_status, strict=True):
        if (linked and status["is_linked"]) or (not linked and not status["is_linked"]):
            results.append(SiteWithLinkStatus(**row, **status))

    return results


@router.post("", status_code=201)
def create_site(
    request: CreateSiteRequest,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> CreateSiteResponse:
    """Create a new site in the Culture Extractor database."""
    try:
        site_uuid = client.create_site(
            short_name=request.short_name,
            name=request.name,
            url=request.url,
            username=request.username,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create site") from None

    return CreateSiteResponse(
        message=f"Created site '{request.name}'",
        uuid=site_uuid,
        short_name=request.short_name,
        name=request.name,
        url=request.url,
    )


@router.get("/{uuid}")
def get_site(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> SiteDetail:
    """Get a specific site by UUID."""
    site_df = client.get_site_by_uuid(uuid)

    if site_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Site with UUID '{uuid}' not found")

    site_data = site_df.to_dicts()[0]
    external_ids_dict = client.get_site_external_ids(uuid)

    return SiteDetail(
        **site_data,
        external_ids=SiteExternalIds(
            stashapp=external_ids_dict.get("stashapp"),
            stashdb=external_ids_dict.get("stashdb"),
        ),
    )


@router.post("/{uuid}/link")
def link_site(
    uuid: str,
    request: LinkSiteRequest,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> dict:
    """Link a site to an external system."""
    # Validate target system
    valid_targets = {"stashapp", "stashdb"}
    if request.target not in valid_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target system. Must be one of: {', '.join(valid_targets)}",
        )

    # Verify site exists
    site_df = client.get_site_by_uuid(uuid)
    if site_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Site with UUID '{uuid}' not found")

    site_name = site_df["ce_sites_name"][0]

    try:
        client.set_site_external_id(uuid, request.target, request.external_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "message": f"Linked site '{site_name}' to {request.target}",
        "site_uuid": uuid,
        "target": request.target,
        "external_id": request.external_id,
    }
