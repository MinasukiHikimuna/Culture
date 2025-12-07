"""Job manager for face matching background processing.

This service manages background jobs for face recognition matching,
storing job state and results in memory.
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


class JobStatus(str, Enum):
    """Status of a matching job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MatchBin(str, Enum):
    """Bin category for a performer match result."""

    EASY = "easy"  # High confidence + exact name match
    DIFFICULT = "difficult"  # Lower confidence or no name match
    NO_MATCH = "no_match"  # No face matches found
    NO_IMAGE = "no_image"  # Image file not available


@dataclass
class NameMatchResult:
    """Result of name matching comparison."""

    match_type: str  # "exact", "partial", or "none"
    matched_name: str | None
    score: int


@dataclass
class EnrichedMatch:
    """An enriched match with data from StashDB and Stashapp."""

    # From Stashface
    name: str
    confidence: int
    stashdb_id: str
    stashdb_image_url: str | None

    # From StashDB lookup
    aliases: list[str]
    country: str | None

    # From Stashapp lookup
    stashapp_id: int | None
    stashapp_exists: bool

    # Computed
    name_match: NameMatchResult


@dataclass
class PerformerMatchResult:
    """Match result for a single performer."""

    performer_uuid: str
    performer_name: str
    performer_image_available: bool
    bin: MatchBin
    matches: list[EnrichedMatch]


@dataclass
class MatchingJob:
    """A face matching job."""

    job_id: str
    site_uuid: str
    site_name: str
    status: JobStatus
    total_performers: int
    processed_count: int
    results: dict[str, PerformerMatchResult]
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JobManager:
    """Manager for face matching background jobs."""

    def __init__(self) -> None:
        """Initialize the job manager."""
        self._jobs: dict[str, MatchingJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def create_job(self, site_uuid: str, site_name: str, total_performers: int) -> str:
        """Create a new matching job.

        Args:
            site_uuid: UUID of the site being processed
            site_name: Name of the site
            total_performers: Total number of performers to process

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        job = MatchingJob(
            job_id=job_id,
            site_uuid=site_uuid,
            site_name=site_name,
            status=JobStatus.PENDING,
            total_performers=total_performers,
            processed_count=0,
            results={},
        )
        self._jobs[job_id] = job
        return job_id

    def get_job(self, job_id: str) -> MatchingJob | None:
        """Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            MatchingJob or None if not found
        """
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 10) -> list[MatchingJob]:
        """List recent jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of jobs sorted by creation time (newest first)
        """
        jobs = sorted(
            self._jobs.values(),
            key=lambda j: j.created_at,
            reverse=True,
        )
        return jobs[:limit]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
    ) -> None:
        """Update job status.

        Args:
            job_id: Job ID
            status: New status
            error: Optional error message
        """
        job = self._jobs.get(job_id)
        if job:
            job.status = status
            job.error = error
            job.updated_at = datetime.now(UTC)

    def add_result(
        self,
        job_id: str,
        result: PerformerMatchResult,
    ) -> None:
        """Add a performer result to a job.

        Args:
            job_id: Job ID
            result: Performer match result
        """
        job = self._jobs.get(job_id)
        if job:
            job.results[result.performer_uuid] = result
            job.processed_count = len(job.results)
            job.updated_at = datetime.now(UTC)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled, False if not found or not running
        """
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
            return False

        # Cancel the async task if running
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        job.status = JobStatus.CANCELLED
        job.updated_at = datetime.now(UTC)
        return True

    def start_job(
        self,
        job_id: str,
        processor: Callable[[str], asyncio.Task],
    ) -> None:
        """Start a job by creating a background task.

        Args:
            job_id: Job ID
            processor: Async function that processes the job
        """
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.PENDING:
            job.status = JobStatus.RUNNING
            job.updated_at = datetime.now(UTC)
            task = asyncio.create_task(processor(job_id))
            self._tasks[job_id] = task

    def is_job_cancelled(self, job_id: str) -> bool:
        """Check if a job has been cancelled.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled
        """
        job = self._jobs.get(job_id)
        return job is not None and job.status == JobStatus.CANCELLED


def calculate_name_match(
    ce_name: str,
    match_name: str,
    aliases: list[str] | None,
) -> NameMatchResult:
    """Compare CE performer name against match name and aliases.

    Args:
        ce_name: CE performer name
        match_name: Match performer name
        aliases: List of performer aliases

    Returns:
        NameMatchResult with match type and score
    """
    names_to_check = [match_name] + (aliases or [])
    ce_lower = ce_name.lower().strip()

    # Check for exact match
    for name in names_to_check:
        if ce_lower == name.lower().strip():
            return NameMatchResult(match_type="exact", matched_name=name, score=100)

    # Check for partial match (contains)
    for name in names_to_check:
        name_lower = name.lower().strip()
        if ce_lower in name_lower or name_lower in ce_lower:
            return NameMatchResult(match_type="partial", matched_name=name, score=75)

    return NameMatchResult(match_type="none", matched_name=None, score=0)


def categorize_match(result: PerformerMatchResult) -> MatchBin:
    """Categorize a performer match result into a bin.

    Args:
        result: Performer match result

    Returns:
        MatchBin category
    """
    if not result.performer_image_available:
        return MatchBin.NO_IMAGE

    if not result.matches:
        return MatchBin.NO_MATCH

    best_match = result.matches[0]
    # Easy: high confidence (>=90%) AND exact name match
    if best_match.confidence >= 90 and best_match.name_match.match_type == "exact":
        return MatchBin.EASY

    # Everything else needs manual review
    return MatchBin.DIFFICULT


def get_performer_image_path(
    base_path: Path,
    site_name: str,
    performer_uuid: str,
) -> Path | None:
    """Get the path to a performer's image file.

    Args:
        base_path: Base metadata path
        site_name: Name of the site
        performer_uuid: Performer UUID

    Returns:
        Path to image file or None if not found
    """
    # Try common image extensions
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        image_path = (
            base_path / site_name / "Performers" / performer_uuid / f"{performer_uuid}{ext}"
        )
        if image_path.exists():
            return image_path

    return None


# Global job manager instance
job_manager = JobManager()
