"""Face matching API router for performer face recognition."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.config import get_metadata_base_path
from api.dependencies import get_ce_client
from api.services.job_manager import (
    EnrichedMatch,
    JobStatus,
    MatchBin,
    MatchingJob,
    PerformerMatchResult,
    calculate_name_match,
    categorize_match,
    get_performer_image_path,
    job_manager,
)
from api.services.stashapp import StashappClient
from api.services.stashdb import StashDBClient
from api.services.stashface import StashfaceClient
from libraries.client_culture_extractor import ClientCultureExtractor


router = APIRouter()


# Pydantic models for API responses
class NameMatchResultResponse(BaseModel):
    """Name match result for API response."""

    match_type: str
    matched_name: str | None
    score: int


class EnrichedMatchResponse(BaseModel):
    """Enriched match for API response."""

    name: str
    confidence: int
    stashdb_id: str
    stashdb_image_url: str | None
    aliases: list[str]
    country: str | None
    stashapp_id: int | None
    stashapp_exists: bool
    name_match: NameMatchResultResponse


class PerformerMatchResultResponse(BaseModel):
    """Performer match result for API response."""

    performer_uuid: str
    performer_name: str
    performer_image_available: bool
    bin: str
    matches: list[EnrichedMatchResponse]


class JobResponse(BaseModel):
    """Job status response."""

    job_id: str
    site_uuid: str
    site_name: str
    status: str
    total_performers: int
    processed_count: int
    error: str | None = None


class JobDetailResponse(JobResponse):
    """Job detail response with results."""

    results: dict[str, PerformerMatchResultResponse]


class StartJobRequest(BaseModel):
    """Request to start a face matching job."""

    site: str  # Site identifier (UUID, short_name, or name)


class StartJobResponse(BaseModel):
    """Response from starting a job."""

    job_id: str
    message: str


@router.post("/jobs")
async def start_matching_job(
    request: StartJobRequest,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> StartJobResponse:
    """Start a new face matching job for a site.

    This will process all unmapped performers for the site, running
    face recognition and enriching matches with StashDB/Stashapp data.
    """
    metadata_base = get_metadata_base_path()
    if not metadata_base:
        raise HTTPException(
            status_code=503,
            detail="Metadata storage not configured (CE_METADATA_BASE_PATH not set)",
        )

    # Resolve site
    site_uuid, site_name = _resolve_site(client, request.site)

    # Get unmapped performers
    performers_df = client.get_performers_unmapped(site_uuid, target_system_name="stashapp")
    total_performers = len(performers_df)

    if total_performers == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No unmapped performers found for site '{site_name}'",
        )

    # Create job
    job_id = job_manager.create_job(site_uuid, site_name, total_performers)

    # Start background processing
    performers_list = performers_df.to_dicts()

    async def process_job(jid: str) -> None:
        await _process_matching_job(jid, performers_list, metadata_base, site_name)

    job_manager.start_job(job_id, process_job)

    return StartJobResponse(
        job_id=job_id,
        message=f"Started matching job for {total_performers} performers in '{site_name}'",
    )


@router.get("/jobs")
def list_jobs(
    limit: Annotated[int, Query(description="Maximum jobs to return", ge=1, le=50)] = 10,
) -> list[JobResponse]:
    """List recent face matching jobs."""
    jobs = job_manager.list_jobs(limit)
    return [_job_to_response(job) for job in jobs]


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    client: Annotated[ClientCultureExtractor, Depends(get_ce_client)],
) -> JobDetailResponse:
    """Get the status and results of a face matching job.

    Filters out performers that are already linked to StashDB.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Filter out performers already linked to StashDB
    filtered_results = _filter_linked_performers(job.results, client)

    # Create a copy of the job with filtered results
    filtered_job = MatchingJob(
        job_id=job.job_id,
        site_uuid=job.site_uuid,
        site_name=job.site_name,
        status=job.status,
        total_performers=job.total_performers,
        processed_count=job.processed_count,
        results=filtered_results,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )

    return _job_to_detail_response(filtered_job)


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str) -> dict:
    """Cancel a running face matching job."""
    if job_manager.cancel_job(job_id):
        return {"message": f"Job '{job_id}' cancelled"}
    raise HTTPException(
        status_code=400,
        detail=f"Job '{job_id}' not found or cannot be cancelled",
    )


def _filter_linked_performers(
    results: dict[str, PerformerMatchResult],
    client: ClientCultureExtractor,
) -> dict[str, PerformerMatchResult]:
    """Filter out performers that are already linked to StashDB.

    Args:
        results: Dict of performer UUID to match result
        client: CE database client

    Returns:
        Filtered dict excluding already-linked performers
    """
    if not results:
        return results

    # Get performer UUIDs that need checking
    performer_uuids = list(results.keys())

    # Check each performer's StashDB link status
    linked_uuids = set()
    for uuid in performer_uuids:
        performer_df = client.get_performer_by_uuid(uuid)
        if not performer_df.is_empty():
            stashdb_id = performer_df.row(0, named=True).get("ce_performers_stashdb_id")
            if stashdb_id:
                linked_uuids.add(uuid)

    # Return only unlinked performers
    return {
        uuid: result
        for uuid, result in results.items()
        if uuid not in linked_uuids
    }


async def _process_matching_job(
    job_id: str,
    performers: list[dict],
    metadata_base,
    site_name: str,
) -> None:
    """Process a face matching job in the background.

    Args:
        job_id: Job ID
        performers: List of performer dicts
        metadata_base: Base path for metadata
        site_name: Name of the site
    """
    stashface = StashfaceClient()
    stashdb = StashDBClient()
    stashapp = StashappClient()

    try:
        for performer in performers:
            if job_manager.is_job_cancelled(job_id):
                break

            result = await _process_performer(
                performer, site_name, metadata_base, stashface, stashdb, stashapp
            )
            job_manager.add_result(job_id, result)

        # Mark as completed if not cancelled
        if not job_manager.is_job_cancelled(job_id):
            job_manager.update_job_status(job_id, JobStatus.COMPLETED)

    except Exception as e:
        job_manager.update_job_status(job_id, JobStatus.FAILED, str(e))


async def _process_performer(
    performer: dict,
    site_name: str,
    metadata_base,
    stashface: StashfaceClient,
    stashdb: StashDBClient,
    stashapp: StashappClient,
) -> PerformerMatchResult:
    """Process a single performer for face matching.

    Args:
        performer: Performer dict from database
        site_name: Name of the site
        metadata_base: Base path for metadata
        stashface: Stashface client
        stashdb: StashDB client
        stashapp: Stashapp client

    Returns:
        PerformerMatchResult
    """
    performer_uuid = performer["ce_performers_uuid"]
    performer_name = performer["ce_performers_name"]

    # Find performer image
    image_path = get_performer_image_path(metadata_base, site_name, performer_uuid)

    if not image_path:
        return PerformerMatchResult(
            performer_uuid=performer_uuid,
            performer_name=performer_name,
            performer_image_available=False,
            bin=MatchBin.NO_IMAGE,
            matches=[],
        )

    # Run face recognition
    stashface_result = await stashface.analyze_image(str(image_path))

    if not stashface_result.success or not stashface_result.faces:
        return PerformerMatchResult(
            performer_uuid=performer_uuid,
            performer_name=performer_name,
            performer_image_available=True,
            bin=MatchBin.NO_MATCH,
            matches=[],
        )

    # Get the first face's matches (assuming single performer per image)
    face = stashface_result.faces[0]
    enriched_matches = []

    for match in face.performers:
        enriched = await _enrich_match(performer_name, match, stashdb, stashapp)
        enriched_matches.append(enriched)

    result = PerformerMatchResult(
        performer_uuid=performer_uuid,
        performer_name=performer_name,
        performer_image_available=True,
        bin=MatchBin.DIFFICULT,  # Will be recategorized
        matches=enriched_matches,
    )

    # Categorize into bin
    result.bin = categorize_match(result)

    return result


async def _enrich_match(
    ce_performer_name: str,
    match,
    stashdb: StashDBClient,
    stashapp: StashappClient,
) -> EnrichedMatch:
    """Enrich a face match with StashDB and Stashapp data.

    Args:
        ce_performer_name: CE performer name for name matching
        match: PerformerMatch from Stashface
        stashdb: StashDB client
        stashapp: Stashapp client

    Returns:
        EnrichedMatch
    """
    # Lookup performer in StashDB for aliases
    stashdb_performer = await stashdb.get_performer(match.stashdb_id)
    aliases = stashdb_performer.aliases if stashdb_performer else []
    country = stashdb_performer.country if stashdb_performer else match.country

    # Lookup performer in Stashapp
    stashapp_performer = await stashapp.get_performer_by_stashdb_id(match.stashdb_id)
    stashapp_id = stashapp_performer.id if stashapp_performer else None
    stashapp_exists = stashapp_performer is not None

    # Calculate name match
    name_match = calculate_name_match(ce_performer_name, match.name, aliases)

    return EnrichedMatch(
        name=match.name,
        confidence=match.confidence,
        stashdb_id=match.stashdb_id,
        stashdb_image_url=match.image_url,
        aliases=aliases,
        country=country,
        stashapp_id=stashapp_id,
        stashapp_exists=stashapp_exists,
        name_match=name_match,
    )


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


def _job_to_response(job: MatchingJob) -> JobResponse:
    """Convert MatchingJob to API response."""
    return JobResponse(
        job_id=job.job_id,
        site_uuid=job.site_uuid,
        site_name=job.site_name,
        status=job.status.value,
        total_performers=job.total_performers,
        processed_count=job.processed_count,
        error=job.error,
    )


def _job_to_detail_response(job: MatchingJob) -> JobDetailResponse:
    """Convert MatchingJob to detailed API response."""
    results = {}
    for uuid, result in job.results.items():
        results[uuid] = PerformerMatchResultResponse(
            performer_uuid=result.performer_uuid,
            performer_name=result.performer_name,
            performer_image_available=result.performer_image_available,
            bin=result.bin.value,
            matches=[
                EnrichedMatchResponse(
                    name=m.name,
                    confidence=m.confidence,
                    stashdb_id=m.stashdb_id,
                    stashdb_image_url=m.stashdb_image_url,
                    aliases=m.aliases,
                    country=m.country,
                    stashapp_id=m.stashapp_id,
                    stashapp_exists=m.stashapp_exists,
                    name_match=NameMatchResultResponse(
                        match_type=m.name_match.match_type,
                        matched_name=m.name_match.matched_name,
                        score=m.name_match.score,
                    ),
                )
                for m in result.matches
            ],
        )

    return JobDetailResponse(
        job_id=job.job_id,
        site_uuid=job.site_uuid,
        site_name=job.site_name,
        status=job.status.value,
        total_performers=job.total_performers,
        processed_count=job.processed_count,
        error=job.error,
        results=results,
    )
