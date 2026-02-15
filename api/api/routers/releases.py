"""Releases API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from api.config import get_metadata_base_path
from api.dependencies import get_ce_client
from api.routers.utils import resolve_site
from api.schemas.releases import (
    DeletedDownload,
    DeleteReleaseResponse,
    LinkReleaseRequest,
    Release,
    ReleaseDetail,
    ReleaseDownload,
    ReleaseExternalId,
    ReleaseExternalIds,
    ReleasePerformer,
    ReleaseTag,
)
from libraries.client_culture_extractor import ClientCultureExtractor


router = APIRouter()


@router.get("")
def list_releases(
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
    site: Annotated[
        str,
        Query(description="Site identifier (UUID, short_name, or name)"),
    ],
    tag: Annotated[
        str | None,
        Query(description="Filter by tag (UUID, short_name, or name)"),
    ] = None,
    performer: Annotated[
        str | None,
        Query(description="Filter by performer (UUID, short_name, or name)"),
    ] = None,
    limit: Annotated[
        int | None,
        Query(description="Limit number of results", ge=1),
    ] = None,
    desc: Annotated[
        bool,
        Query(description="Sort by release date descending (newest first)"),
    ] = False,
) -> list[Release]:
    """List releases for a site with optional filtering."""
    site_uuid, _site_name = resolve_site(client, site)
    tag_uuid = _resolve_tag(client, site_uuid, tag) if tag else None
    performer_uuid = _resolve_performer(client, site_uuid, performer) if performer else None

    releases_df = client.get_releases(site_uuid, tag_uuid=tag_uuid, performer_uuid=performer_uuid)

    if releases_df.is_empty():
        return []

    releases_df = releases_df.sort("ce_release_date", descending=desc, nulls_last=True)

    if limit and limit > 0:
        releases_df = releases_df.head(limit)

    return [Release(**row) for row in releases_df.to_dicts()]


@router.get("/{uuid}/thumbnail")
def get_release_thumbnail(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> FileResponse:
    """Get the thumbnail image for a release.

    Returns the cover/thumbnail image file if it exists on disk.
    """
    metadata_base = get_metadata_base_path()
    if not metadata_base:
        raise HTTPException(
            status_code=503,
            detail="Metadata storage not configured (CE_METADATA_BASE_PATH not set)",
        )

    release_df = client.get_release_by_uuid(uuid)
    if release_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Release with UUID '{uuid}' not found")

    site_name = release_df["ce_site_name"][0]
    downloads_df = client.get_release_downloads(uuid)

    # Find thumbnail download - try different patterns in order of preference
    thumbnail = _find_thumbnail(downloads_df)

    if not thumbnail:
        raise HTTPException(status_code=404, detail="No thumbnail found for this release")

    saved_filename = thumbnail.get("ce_downloads_saved_filename")
    if not saved_filename:
        raise HTTPException(status_code=404, detail="Thumbnail file not available")

    # Build path: {base}/{site_name}/Metadata/{release_uuid}/{filename}
    file_path = metadata_base / site_name / "Metadata" / uuid / saved_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found on disk")

    return FileResponse(
        path=file_path,
        media_type="image/jpeg",
        filename=saved_filename,
    )



def _resolve_tag(client: ClientCultureExtractor, site_uuid: str, tag: str) -> str:
    """Resolve tag identifier to UUID for a given site."""
    tags_df = client.get_tags(site_uuid)
    tag_match = tags_df.filter(
        (tags_df["ce_tags_name"] == tag)
        | (tags_df["ce_tags_uuid"] == tag)
        | (tags_df["ce_tags_short_name"] == tag)
    )

    if tag_match.is_empty():
        raise HTTPException(status_code=404, detail=f"Tag '{tag}' not found for this site")

    return tag_match["ce_tags_uuid"][0]


def _resolve_performer(client: ClientCultureExtractor, site_uuid: str, performer: str) -> str:
    """Resolve performer identifier to UUID for a given site."""
    performers_df = client.get_performers(site_uuid)
    performer_match = performers_df.filter(
        (performers_df["ce_performers_name"] == performer)
        | (performers_df["ce_performers_uuid"] == performer)
        | (performers_df["ce_performers_short_name"] == performer)
    )

    if performer_match.is_empty():
        raise HTTPException(status_code=404, detail=f"Performer '{performer}' not found for this site")

    return performer_match["ce_performers_uuid"][0]


def _find_thumbnail(downloads_df) -> dict | None:
    """Find the best thumbnail image from downloads.

    Tries patterns in order of preference:
    1. image/cover/thumbnail
    2. image/cover/* (any cover image)
    3. image/scene/preview
    4. Any image file
    """
    downloads = list(downloads_df.iter_rows(named=True))

    # Priority 1: image/cover/thumbnail
    for d in downloads:
        if (
            d.get("ce_downloads_file_type") == "image"
            and d.get("ce_downloads_content_type") == "cover"
            and d.get("ce_downloads_variant") == "thumbnail"
        ):
            return d

    # Priority 2: any image/cover
    for d in downloads:
        if (
            d.get("ce_downloads_file_type") == "image"
            and d.get("ce_downloads_content_type") == "cover"
        ):
            return d

    # Priority 3: image/scene/preview
    for d in downloads:
        if (
            d.get("ce_downloads_file_type") == "image"
            and d.get("ce_downloads_content_type") == "scene"
            and d.get("ce_downloads_variant") == "preview"
        ):
            return d

    # Priority 4: any image
    for d in downloads:
        if d.get("ce_downloads_file_type") == "image":
            return d

    return None


@router.get("/{uuid}")
def get_release(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> ReleaseDetail:
    """Get detailed information about a specific release."""
    release_df = client.get_release_by_uuid(uuid)

    if release_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Release with UUID '{uuid}' not found")

    release_data = release_df.to_dicts()[0]
    external_ids_list = client.get_release_external_ids(uuid)
    performers_df = client.get_release_performers(uuid)
    tags_df = client.get_release_tags(uuid)
    downloads_df = client.get_release_downloads(uuid)

    # Build legacy format (first ID per target system)
    stashapp_id = next(
        (e["external_id"] for e in external_ids_list if e["target_system"] == "stashapp"), None
    )
    stashdb_id = next(
        (e["external_id"] for e in external_ids_list if e["target_system"] == "stashdb"), None
    )

    return ReleaseDetail(
        **release_data,
        external_ids=ReleaseExternalIds(stashapp=stashapp_id, stashdb=stashdb_id),
        external_id_mappings=[ReleaseExternalId(**e) for e in external_ids_list],
        performers=[ReleasePerformer(**row) for row in performers_df.to_dicts()],
        tags=[ReleaseTag(**row) for row in tags_df.to_dicts()],
        downloads=[ReleaseDownload(**row) for row in downloads_df.to_dicts()],
    )


@router.post("/{uuid}/link")
def link_release(
    uuid: str,
    request: LinkReleaseRequest,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> dict:
    """Link a release to an external system."""
    valid_targets = {"stashapp", "stashdb"}
    if request.target not in valid_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target system. Must be one of: {', '.join(valid_targets)}",
        )

    release_df = client.get_release_by_uuid(uuid)
    if release_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Release with UUID '{uuid}' not found")

    release_name = release_df["ce_release_name"][0]

    try:
        client.set_release_external_id(uuid, request.target, request.external_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "message": f"Linked release '{release_name}' to {request.target}",
        "release_uuid": uuid,
        "target": request.target,
        "external_id": request.external_id,
    }


@router.delete("/{uuid}")
def delete_release(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> DeleteReleaseResponse:
    """Delete a release and all associated database records.

    This removes the release from the database along with all related data
    (downloads, tag links, performer links, external IDs). File system
    cleanup must be handled separately by the client.
    """
    release_df = client.get_release_by_uuid(uuid)
    if release_df.is_empty():
        raise HTTPException(status_code=404, detail=f"Release with UUID '{uuid}' not found")

    try:
        result = client.delete_release(uuid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    downloads = [
        DeletedDownload(
            uuid=d.get("uuid", ""),
            saved_filename=d.get("saved_filename"),
        )
        for d in result.get("downloads", [])
    ]

    return DeleteReleaseResponse(
        message=f"Deleted release '{result['release_name']}' from '{result['site_name']}'",
        release_uuid=uuid,
        release_name=result["release_name"],
        site_name=result["site_name"],
        downloads=downloads,
    )
