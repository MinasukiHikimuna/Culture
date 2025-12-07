"""Performers API router."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from api.config import get_metadata_base_path
from api.dependencies import get_ce_client
from api.schemas.performers import (
    LinkPerformerRequest,
    PerformerDetail,
    PerformerExternalIds,
    PerformerWithLinkStatus,
)
from libraries.client_culture_extractor import ClientCultureExtractor


router = APIRouter()


@router.get("")
def list_performers(
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
    site: Annotated[
        str,
        Query(description="Site identifier (UUID, short_name, or name)"),
    ],
    name: Annotated[
        str | None,
        Query(description="Filter by performer name (case-insensitive)"),
    ] = None,
    unmapped_only: Annotated[
        bool,
        Query(description="Only show performers without external IDs"),
    ] = False,
    target_system: Annotated[
        str,
        Query(description="Target system to check for unmapped filter"),
    ] = "stashapp",
    limit: Annotated[
        int | None,
        Query(description="Limit number of results", ge=1),
    ] = None,
) -> list[PerformerWithLinkStatus]:
    """List performers for a site with optional filtering."""
    site_uuid, site_name = _resolve_site(client, site)

    if unmapped_only:
        performers_df = client.get_performers_unmapped(
            site_uuid, target_system_name=target_system, name_filter=name
        )
    else:
        performers_df = client.get_performers(site_uuid, name_filter=name)

    if performers_df.is_empty():
        return []

    if limit and limit > 0:
        performers_df = performers_df.head(limit)

    # Enrich with link status
    performers = []
    for row in performers_df.to_dicts():
        performer_uuid = row["ce_performers_uuid"]
        external_ids = client.get_performer_external_ids(performer_uuid)

        performers.append(
            PerformerWithLinkStatus(
                ce_performers_uuid=row["ce_performers_uuid"],
                ce_performers_short_name=row.get("ce_performers_short_name"),
                ce_performers_name=row["ce_performers_name"],
                ce_performers_url=row.get("ce_performers_url"),
                ce_site_uuid=site_uuid,
                ce_site_name=site_name,
                has_stashapp_link="stashapp" in external_ids,
                has_stashdb_link="stashdb" in external_ids,
            )
        )

    return performers


@router.get("/{uuid}/image")
def get_performer_image(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> FileResponse:
    """Get the image for a performer.

    Returns the performer's image file if it exists on disk.
    """
    metadata_base = get_metadata_base_path()
    if not metadata_base:
        raise HTTPException(
            status_code=503,
            detail="Metadata storage not configured (CE_METADATA_BASE_PATH not set)",
        )

    performer_df = client.get_performer_by_uuid(uuid)
    if performer_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Performer with UUID '{uuid}' not found")

    site_name = performer_df["ce_sites_name"][0]

    # Try different path patterns
    file_path = _find_performer_image(metadata_base, site_name, uuid)

    if not file_path:
        raise HTTPException(status_code=404, detail="Performer image not found on disk")

    return FileResponse(
        path=file_path,
        media_type="image/jpeg",
        filename=f"{uuid}.jpg",
    )


@router.get("/{uuid}")
def get_performer(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> PerformerDetail:
    """Get detailed information about a specific performer."""
    performer_df = client.get_performer_by_uuid(uuid)

    if performer_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Performer with UUID '{uuid}' not found")

    performer_data = performer_df.to_dicts()[0]
    external_ids_dict = client.get_performer_external_ids(uuid)

    return PerformerDetail(
        ce_performers_uuid=performer_data["ce_performers_uuid"],
        ce_performers_short_name=performer_data.get("ce_performers_short_name"),
        ce_performers_name=performer_data["ce_performers_name"],
        ce_performers_url=performer_data.get("ce_performers_url"),
        ce_sites_short_name=performer_data.get("ce_sites_short_name"),
        ce_sites_name=performer_data.get("ce_sites_name"),
        external_ids=PerformerExternalIds(
            stashapp=external_ids_dict.get("stashapp"),
            stashdb=external_ids_dict.get("stashdb"),
        ),
    )


@router.post("/{uuid}/link")
def link_performer(
    uuid: str,
    request: LinkPerformerRequest,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> dict:
    """Link a performer to an external system."""
    valid_targets = {"stashapp", "stashdb"}
    if request.target not in valid_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target system. Must be one of: {', '.join(valid_targets)}",
        )

    performer_df = client.get_performer_by_uuid(uuid)
    if performer_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Performer with UUID '{uuid}' not found")

    performer_name = performer_df["ce_performers_name"][0]

    try:
        client.set_performer_external_id(uuid, request.target, request.external_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "message": f"Linked performer '{performer_name}' to {request.target}",
        "performer_uuid": uuid,
        "target": request.target,
        "external_id": request.external_id,
    }


def _resolve_site(client: ClientCultureExtractor, site: str) -> tuple[str, str]:
    """Resolve site identifier to UUID and name."""
    sites_df = client.get_sites()
    site_match = sites_df.filter(
        (sites_df["ce_sites_short_name"] == site)
        | (sites_df["ce_sites_uuid"] == site)
        | (sites_df["ce_sites_name"] == site)
    )

    if site_match.is_empty():
        raise HTTPException(status_code=404, detail=f"Site '{site}' not found")

    return site_match["ce_sites_uuid"][0], site_match["ce_sites_name"][0]


def _find_performer_image(metadata_base: Path, site_name: str, performer_uuid: str) -> Path | None:
    """Find performer image trying different path patterns.

    Tries patterns in order:
    1. {base}/{site_name}/Performers/{uuid}/{uuid}.jpg
    2. Various case variations of site_name
    """
    patterns = [
        metadata_base / site_name / "Performers" / performer_uuid / f"{performer_uuid}.jpg",
        metadata_base / site_name.title() / "Performers" / performer_uuid / f"{performer_uuid}.jpg",
        metadata_base / site_name.upper() / "Performers" / performer_uuid / f"{performer_uuid}.jpg",
        metadata_base / site_name.lower() / "Performers" / performer_uuid / f"{performer_uuid}.jpg",
    ]

    for path in patterns:
        if path.exists():
            return path

    return None
