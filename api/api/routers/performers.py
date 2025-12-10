"""Performers API router."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from api.config import get_metadata_base_path
from api.dependencies import get_ce_client
from api.schemas.performers import (
    BatchLinkRequest,
    BatchLinkResponse,
    BatchLinkResult,
    GlobalPerformer,
    GlobalPerformerDetail,
    GlobalPerformerSiteRecord,
    LinkPerformerRequest,
    PaginatedGlobalPerformersResponse,
    PaginatedPerformersResponse,
    PerformerDetail,
    PerformerExternalIds,
    PerformerRelease,
    PerformerWithLinkStatus,
    SitePerformerInfo,
    StashappSearchResult,
    StashDBSearchResult,
)
from api.services.stashapp import StashappClient
from api.services.stashdb import StashDBClient
from libraries.client_culture_extractor import ClientCultureExtractor


router = APIRouter()


@router.get("/global")
def list_global_performers(
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
    name: Annotated[
        str | None,
        Query(description="Filter by performer name (case-insensitive)"),
    ] = None,
    page: Annotated[
        int,
        Query(description="Page number (1-indexed)", ge=1),
    ] = 1,
    page_size: Annotated[
        int,
        Query(description="Number of items per page", ge=1, le=100),
    ] = 50,
) -> PaginatedGlobalPerformersResponse:
    """List global performers grouped by external ID.

    Returns performers grouped across sites by their StashDB ID (preferred)
    or Stashapp ID (fallback). Performers without external IDs are excluded.
    """
    # Get count first to avoid unnecessary data query if no results
    total = client.get_global_performers_count(name_filter=name)

    if total == 0:
        return PaginatedGlobalPerformersResponse(
            items=[], total=0, page=page, page_size=page_size, total_pages=0
        )

    total_pages = (total + page_size - 1) // page_size

    df = client.get_global_performers(
        name_filter=name,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    items = [
        GlobalPerformer(
            grouping_id=row["grouping_id"],
            grouping_type=row["grouping_type"],
            display_name=row["display_name"],
            site_count=row["site_count"],
            total_release_count=row["total_release_count"],
            site_performers=[
                SitePerformerInfo(
                    site_uuid=sp["site_uuid"],
                    site_name=sp["site_name"],
                    performer_uuid=sp["performer_uuid"],
                    performer_name=sp["performer_name"],
                )
                for sp in row["site_performers"]
            ],
        )
        for row in df.to_dicts()
    ]

    return PaginatedGlobalPerformersResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/global/{external_id}")
def get_global_performer(
    external_id: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> GlobalPerformerDetail:
    """Get detailed information about a global performer.

    Returns all site-specific performer records that share the given
    external ID (StashDB or Stashapp).
    """
    df = client.get_global_performer_detail(external_id)

    if df.is_empty():
        raise HTTPException(
            status_code=404,
            detail=f"No performers found with external ID '{external_id}'",
        )

    rows = df.to_dicts()
    first_row = rows[0]

    # Determine grouping type based on which external ID matches
    if first_row["stashdb_id"] == external_id:
        grouping_type = "stashdb"
    elif first_row["stashapp_id"] == external_id:
        grouping_type = "stashapp"
    else:
        # Fallback: use whichever ID is present (stashdb preferred)
        grouping_type = "stashdb" if first_row["stashdb_id"] else "stashapp"

    site_records = [
        GlobalPerformerSiteRecord(
            performer_uuid=row["performer_uuid"],
            performer_name=row["performer_name"],
            performer_short_name=row["performer_short_name"],
            performer_url=row["performer_url"],
            site_uuid=row["site_uuid"],
            site_name=row["site_name"],
            site_short_name=row["site_short_name"],
            stashdb_id=row["stashdb_id"],
            stashapp_id=row["stashapp_id"],
            release_count=row["release_count"],
        )
        for row in rows
    ]

    total_release_count = sum(r.release_count for r in site_records)

    return GlobalPerformerDetail(
        grouping_id=external_id,
        grouping_type=grouping_type,
        display_name=first_row["performer_name"],
        site_records=site_records,
        total_release_count=total_release_count,
    )


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
    link_filter: Annotated[
        str | None,
        Query(
            description="Filter by link status: 'all', 'unlinked', 'unlinked_stashdb', 'unlinked_stashapp', 'linked'"
        ),
    ] = "all",
    page: Annotated[
        int,
        Query(description="Page number (1-indexed)", ge=1),
    ] = 1,
    page_size: Annotated[
        int,
        Query(description="Number of items per page", ge=1, le=100),
    ] = 50,
) -> PaginatedPerformersResponse:
    """List performers for a site with optional filtering and pagination."""
    site_uuid, site_name = _resolve_site(client, site)

    # Get base performers list based on filter
    if link_filter == "unlinked_stashdb":
        performers_df = client.get_performers_unmapped(
            site_uuid, target_system_name="stashdb", name_filter=name
        )
    elif link_filter == "unlinked_stashapp":
        performers_df = client.get_performers_unmapped(
            site_uuid, target_system_name="stashapp", name_filter=name
        )
    elif link_filter == "unlinked":
        # Unlinked to both - get unmapped for stashdb first, then filter by stashapp
        performers_df = client.get_performers_unmapped(
            site_uuid, target_system_name="stashdb", name_filter=name
        )
    else:
        # 'all' or 'linked' - get all performers first
        performers_df = client.get_performers(site_uuid, name_filter=name)

    if performers_df.is_empty():
        return PaginatedPerformersResponse(
            items=[], total=0, page=page, page_size=page_size, total_pages=0
        )

    # Enrich with link status and apply post-filters
    all_performers = []
    for row in performers_df.to_dicts():
        performer_uuid = row["ce_performers_uuid"]
        external_ids = client.get_performer_external_ids(performer_uuid)
        has_stashapp = "stashapp" in external_ids
        has_stashdb = "stashdb" in external_ids

        # Apply post-enrichment filters
        if link_filter == "unlinked" and has_stashapp:
            # Already filtered by stashdb unmapped, now filter out those with stashapp
            continue
        if link_filter == "linked" and not (has_stashapp or has_stashdb):
            # Only show performers linked to at least one system
            continue

        all_performers.append(
            PerformerWithLinkStatus(
                ce_performers_uuid=row["ce_performers_uuid"],
                ce_performers_short_name=row.get("ce_performers_short_name"),
                ce_performers_name=row["ce_performers_name"],
                ce_performers_url=row.get("ce_performers_url"),
                ce_site_uuid=site_uuid,
                ce_site_name=site_name,
                has_stashapp_link=has_stashapp,
                has_stashdb_link=has_stashdb,
            )
        )

    # Calculate pagination
    total = len(all_performers)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    items = all_performers[start_idx:end_idx]

    return PaginatedPerformersResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


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


@router.get("/{uuid}/releases")
def get_performer_releases(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> list[PerformerRelease]:
    """Get all releases linked to a performer."""
    performer_df = client.get_performer_by_uuid(uuid)

    if performer_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Performer with UUID '{uuid}' not found")

    releases_df = client.get_performer_releases(uuid)

    return [
        PerformerRelease(
            ce_release_uuid=row["ce_release_uuid"],
            ce_release_date=str(row["ce_release_date"]) if row["ce_release_date"] else None,
            ce_release_short_name=row["ce_release_short_name"],
            ce_release_name=row["ce_release_name"],
            ce_release_url=row.get("ce_release_url"),
            ce_site_uuid=row["ce_site_uuid"],
            ce_site_name=row["ce_site_name"],
        )
        for row in releases_df.to_dicts()
    ]


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


@router.post("/batch-link")
def batch_link_performers(
    request: BatchLinkRequest,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> BatchLinkResponse:
    """Link multiple performers to external systems in one request."""
    results = []
    successful = 0
    failed = 0

    for link in request.links:
        result = _process_batch_link_item(client, link)
        results.append(result)
        if result.success:
            successful += 1
        else:
            failed += 1

    return BatchLinkResponse(
        results=results,
        successful=successful,
        failed=failed,
    )


@router.get("/search/stashdb")
async def search_stashdb(
    query: Annotated[str, Query(description="Search query", min_length=1)],
    limit: Annotated[int, Query(description="Maximum results", ge=1, le=50)] = 10,
) -> list[StashDBSearchResult]:
    """Search StashDB for performers by name."""
    stashdb = StashDBClient()
    performers = await stashdb.search_performers(query, limit)

    return [
        StashDBSearchResult(
            id=p.id,
            name=p.name,
            disambiguation=p.disambiguation,
            aliases=p.aliases,
            country=p.country,
            image_url=p.image_url,
        )
        for p in performers
    ]


@router.get("/search/stashapp")
async def search_stashapp(
    query: Annotated[str, Query(description="Search query", min_length=1)],
    limit: Annotated[int, Query(description="Maximum results", ge=1, le=50)] = 10,
) -> list[StashappSearchResult]:
    """Search Stashapp for performers by name."""
    stashapp = StashappClient()
    performers = await stashapp.search_performers(query, limit)

    return [
        StashappSearchResult(
            id=p.id,
            name=p.name,
            disambiguation=p.disambiguation,
            aliases=p.aliases,
            stashdb_id=p.stashdb_id,
        )
        for p in performers
    ]


def _process_batch_link_item(
    client: ClientCultureExtractor,
    link,
) -> BatchLinkResult:
    """Process a single batch link item.

    Args:
        client: CE database client
        link: BatchLinkItem to process

    Returns:
        BatchLinkResult
    """
    performer_uuid = link.performer_uuid

    # Verify performer exists
    performer_df = client.get_performer_by_uuid(performer_uuid)
    if performer_df.is_empty():
        return BatchLinkResult(
            performer_uuid=performer_uuid,
            success=False,
            error=f"Performer '{performer_uuid}' not found",
        )

    # Link to stashapp if provided
    if link.stashapp_id:
        try:
            client.set_performer_external_id(performer_uuid, "stashapp", link.stashapp_id)
        except ValueError as e:
            return BatchLinkResult(
                performer_uuid=performer_uuid,
                success=False,
                error=f"Failed to link stashapp: {e}",
            )

    # Link to stashdb if provided
    if link.stashdb_id:
        try:
            client.set_performer_external_id(performer_uuid, "stashdb", link.stashdb_id)
        except ValueError as e:
            return BatchLinkResult(
                performer_uuid=performer_uuid,
                success=False,
                error=f"Failed to link stashdb: {e}",
            )

    return BatchLinkResult(performer_uuid=performer_uuid, success=True)


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

    Tries site name case variations and multiple image extensions.
    Prefers exact {uuid}.{ext} match over numbered variants.
    """
    site_variations = [site_name, site_name.title(), site_name.upper(), site_name.lower()]
    extensions = [".jpg", ".jpeg", ".png", ".webp"]

    for site in site_variations:
        performer_dir = metadata_base / site / "Performers" / performer_uuid
        if not performer_dir.exists():
            continue

        # Prefer exact {uuid}.{ext} match
        for ext in extensions:
            path = performer_dir / f"{performer_uuid}{ext}"
            if path.exists():
                return path

        # Fall back to any image file in the directory
        for ext in extensions:
            for path in performer_dir.glob(f"{performer_uuid}*{ext}"):
                return path

    return None
