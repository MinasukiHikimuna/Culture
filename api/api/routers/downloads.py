"""Downloads API router."""

from typing import Annotated

import polars as pl
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_ce_client
from api.routers.utils import resolve_site
from api.schemas.releases import DeleteDownloadResponse, DownloadDetail, ReleaseDownloadSummary
from libraries.client_culture_extractor import ClientCultureExtractor


router = APIRouter()


@router.get("")
def list_download_summary(
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
    site: Annotated[
        str,
        Query(description="Site identifier (UUID, short_name, or name)"),
    ],
    downloads: Annotated[
        str,
        Query(description="Filter: 'all' (default) or 'none' (no downloads)"),
    ] = "all",
    has_file: Annotated[
        str | None,
        Query(description="Filter to releases with this file_type downloaded (e.g. 'video')"),
    ] = None,
    missing_file: Annotated[
        str | None,
        Query(description="Filter to releases missing this file_type (e.g. 'video')"),
    ] = None,
    has_content: Annotated[
        str | None,
        Query(description="Filter to releases with this content_type downloaded (e.g. 'scene')"),
    ] = None,
    missing_content: Annotated[
        str | None,
        Query(description="Filter to releases missing this content_type (e.g. 'scene')"),
    ] = None,
    limit: Annotated[
        int | None,
        Query(description="Limit number of results", ge=1),
    ] = None,
    desc: Annotated[
        bool,
        Query(description="Sort by release date descending (newest first)"),
    ] = False,
) -> list[ReleaseDownloadSummary]:
    """List per-release download summaries for a site with optional filtering."""
    site_uuid, _site_name = resolve_site(client, site)

    df = client.get_release_download_summary(site_uuid)
    if df.is_empty():
        return []

    df = _apply_download_filters(df, downloads, has_file, missing_file, has_content, missing_content)
    df = df.sort("ce_release_date", descending=desc, nulls_last=True)

    if limit and limit > 0:
        df = df.head(limit)

    return [ReleaseDownloadSummary(**row) for row in df.to_dicts()]


def _apply_download_filters(
    df: pl.DataFrame,
    downloads: str,
    has_file: str | None,
    missing_file: str | None,
    has_content: str | None,
    missing_content: str | None,
) -> pl.DataFrame:
    """Apply download-related filters to the summary DataFrame."""
    if downloads == "none":
        df = df.filter(pl.col("ce_release_download_count") == 0)

    if has_file:
        df = df.filter(
            pl.col("ce_release_download_file_types").is_not_null()
            & pl.col("ce_release_download_file_types").str.contains(has_file)
        )

    if missing_file:
        df = df.filter(
            pl.col("ce_release_download_file_types").is_null()
            | ~pl.col("ce_release_download_file_types").str.contains(missing_file)
        )

    if has_content:
        df = df.filter(
            pl.col("ce_release_download_content_types").is_not_null()
            & pl.col("ce_release_download_content_types").str.contains(has_content)
        )

    if missing_content:
        df = df.filter(
            pl.col("ce_release_download_content_types").is_null()
            | ~pl.col("ce_release_download_content_types").str.contains(missing_content)
        )

    return df


@router.get("/{uuid}")
def get_download(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> DownloadDetail:
    """Get details about a specific download."""
    download = client.get_download_by_uuid(uuid)
    if not download:
        raise HTTPException(status_code=404, detail=f"Download with UUID '{uuid}' not found")
    return DownloadDetail(**download)


@router.delete("/{uuid}")
def delete_download(
    uuid: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> DeleteDownloadResponse:
    """Delete a single download record and its referencing external IDs.

    This removes the download from the database along with any external IDs
    that reference it. File system cleanup must be handled separately by the client.
    """
    try:
        result = client.delete_download(uuid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return DeleteDownloadResponse(
        message=(
            f"Deleted download '{result['file_type']}/{result['content_type']}' "
            f"from release '{result['release_name']}'"
        ),
        download_uuid=result["download_uuid"],
        saved_filename=result["saved_filename"],
        file_type=result["file_type"],
        content_type=result["content_type"],
        variant=result["variant"],
        release_uuid=result["release_uuid"],
        release_name=result["release_name"],
        site_name=result["site_name"],
        external_ids_deleted=result["external_ids_deleted"],
    )
