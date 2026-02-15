#!/usr/bin/env python3
"""
Release Orchestrator

Coordinates the entire release extraction workflow:
1. Discovery (Reddit/Patreon posts)
2. Analysis (LLM enrichment)
3. Audio extraction (platform-agnostic)
4. Release aggregation
5. Storage organization

All files are stored directly in data/releases/{performer}/{release_dir}/
"""

import argparse
import errno
import hashlib
import json
import re
import sys
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import config as aural_config
import httpx
from analyze_reddit_post import EnhancedRedditPostAnalyzer
from ao3_extractor import AO3Extractor
from audiochan_extractor import AudiochanExtractor
from erocast_extractor import ErocastExtractor
from exceptions import DiskSpaceError
from hotaudio_extractor import HotAudioExtractor
from scriptbin_extractor import ScriptBinExtractor
from soundgasm_extractor import SoundgasmExtractor
from url_utils import is_audio_content_url
from whypit_extractor import WhypitExtractor


if TYPE_CHECKING:
    from platform_availability import PlatformAvailabilityTracker


def _is_disk_space_error(error: Exception) -> bool:
    """Check if an exception indicates disk space exhaustion."""
    if isinstance(error, OSError):
        if hasattr(error, "errno") and error.errno == errno.ENOSPC:
            return True
        if "no space left" in str(error).lower():
            return True
    return False


@dataclass
class AudioSource:
    """Unified audio source schema."""

    audio: dict = field(default_factory=lambda: {
        "sourceUrl": None,
        "downloadUrl": None,
        "filePath": None,
        "format": None,
        "fileSize": None,
        "checksum": {}
    })
    metadata: dict = field(default_factory=lambda: {
        "title": None,
        "author": None,
        "description": None,
        "tags": [],
        "duration": None,
        "uploadDate": None,
        "extractedAt": None,
        "platform": {"name": None, "extractorVersion": None}
    })
    platform_data: dict = field(default_factory=dict)
    backup_files: dict = field(default_factory=lambda: {"html": None, "metadata": None})
    version_info: dict | None = None
    alternate_sources: list | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "audio": self.audio,
            "metadata": self.metadata,
            "platformData": self.platform_data,
            "backupFiles": self.backup_files,
        }
        if self.version_info:
            result["versionInfo"] = self.version_info
        if self.alternate_sources:
            result["alternateSources"] = self.alternate_sources
        return result


@dataclass
class Release:
    """Release - aggregates multiple audio sources and enrichment data."""

    id: str = ""
    title: str | None = None
    primary_performer: str | None = None
    additional_performers: list = field(default_factory=list)
    script_author: str | None = None
    release_date: str | None = None
    enrichment_data: dict = field(default_factory=lambda: {
        "reddit": None,
        "patreon": None,
        "llmAnalysis": None,
        "gwasi": None
    })
    audio_sources: list = field(default_factory=list)
    script: dict | None = None
    artwork: list = field(default_factory=list)
    aggregated_at: str = ""
    version: str = "1.0"
    # Runtime field - actual directory path where release is stored (not serialized)
    release_dir: Path | None = None

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
        if not self.aggregated_at:
            self.aggregated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _generate_id(self) -> str:
        """Generate a unique ID for the release."""
        data = f"{self.title}-{self.primary_performer}-{datetime.now(UTC).timestamp()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def add_audio_source(self, audio_source: AudioSource | dict):
        """Add an audio source to the release."""
        if isinstance(audio_source, AudioSource):
            self.audio_sources.append(audio_source.to_dict())
        else:
            self.audio_sources.append(audio_source)

    def get_audio_sources_by_platform(self, platform_name: str) -> list:
        """Get audio sources by platform."""
        return [
            source for source in self.audio_sources
            if source.get("metadata", {}).get("platform", {}).get("name") == platform_name
        ]

    def has_all_variants(self, expected_variants: list[str] | None = None) -> bool:
        """Check if release has all expected audio variants."""
        if expected_variants is None:
            expected_variants = ["M4F", "F4M"]

        found_variants = set()

        for source in self.audio_sources:
            metadata = source.get("metadata", {})
            all_text = " ".join([
                metadata.get("title") or "",
                metadata.get("description") or "",
                *metadata.get("tags", [])
            ]).upper()

            for variant in expected_variants:
                if variant in all_text:
                    found_variants.add(variant)

        return all(v in found_variants for v in expected_variants)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "primaryPerformer": self.primary_performer,
            "additionalPerformers": self.additional_performers,
            "scriptAuthor": self.script_author,
            "releaseDate": self.release_date,
            "enrichmentData": self.enrichment_data,
            "audioSources": self.audio_sources,
            "script": self.script,
            "artwork": self.artwork,
            "aggregatedAt": self.aggregated_at,
            "version": self.version
        }


class ReleaseOrchestrator:
    """Main orchestrator class for release extraction workflow."""

    def __init__(
        self,
        config: dict | None = None,
        availability_tracker: PlatformAvailabilityTracker | None = None,
    ):
        config = config or {}
        self.config = {
            "dataDir": config.get("dataDir", str(aural_config.RELEASES_DIR.parent)),
            "validateExtractions": config.get("validateExtractions", True),
            **config
        }

        # Platform availability tracker for batch processing
        self.availability_tracker = availability_tracker

        # Platform extractors registry
        self.extractors: dict[str, dict] = {}

        # Initialize default extractors
        self.register_extractor("soundgasm", {
            "pattern": re.compile(r"soundgasm\.net", re.IGNORECASE),
            "class": SoundgasmExtractor
        })

        self.register_extractor("whypit", {
            "pattern": re.compile(r"whyp\.it", re.IGNORECASE),
            "class": WhypitExtractor
        })

        self.register_extractor("hotaudio", {
            "pattern": re.compile(r"hotaudio\.net", re.IGNORECASE),
            "class": HotAudioExtractor
        })

        self.register_extractor("audiochan", {
            "pattern": re.compile(r"audiochan\.com", re.IGNORECASE),
            "class": AudiochanExtractor
        })

        self.register_extractor("erocast", {
            "pattern": re.compile(r"erocast\.me", re.IGNORECASE),
            "class": ErocastExtractor
        })

        # Track active extractor instances for cleanup
        self.active_extractors: dict[str, Any] = {}

        # Platform priority for selecting preferred audio source
        # HotAudio is last because it requires slow encryption key capture
        self.platform_priority = ["soundgasm", "whypit", "erocast", "audiochan", "hotaudio"]

    def register_extractor(self, platform: str, config: dict):
        """Register a platform extractor."""
        self.extractors[platform] = config

    def _get_shared_playwright(self) -> tuple:
        """Get page and context from an active extractor for browser sharing.

        Returns:
            Tuple of (page, context) from an active extractor, or (None, None) if none available.
        """
        for extractor in self.active_extractors.values():
            if hasattr(extractor, "page") and extractor.page is not None:
                return extractor.page, extractor.context
        return None, None

    def _create_slug(self, text: str, max_length: int = 50) -> str:
        """
        Create a URL-safe slug from text.

        Args:
            text: Text to slugify
            max_length: Maximum length of the slug

        Returns:
            Lowercase slug with hyphens instead of spaces
        """
        if not text:
            return "untitled"

        # Convert to lowercase and replace spaces/underscores with hyphens
        slug = text.lower().strip()
        slug = re.sub(r"[\s_]+", "-", slug)

        # Remove characters that aren't alphanumeric or hyphens
        slug = re.sub(r"[^a-z0-9\-]", "", slug)

        # Collapse multiple hyphens
        slug = re.sub(r"-+", "-", slug)

        # Strip leading/trailing hyphens
        slug = slug.strip("-")

        # Truncate to max_length, but try to break at a hyphen
        if len(slug) > max_length:
            slug = slug[:max_length]
            # If we cut in the middle of a word, try to find last hyphen
            last_hyphen = slug.rfind("-")
            if last_hyphen > max_length // 2:
                slug = slug[:last_hyphen]

        return slug or "untitled"

    def _find_existing_release_dir(self, performer_dir: Path, post_id: str) -> Path | None:
        """
        Find an existing release directory for a post ID.

        Searches for directories matching {post_id}_* pattern to handle
        LLM non-determinism in slug generation.

        Args:
            performer_dir: Path to the performer's releases directory
            post_id: The Reddit post ID

        Returns:
            Path to existing release directory if found, None otherwise
        """
        if not performer_dir.exists():
            return None

        # Look for directories starting with {post_id}_
        pattern = f"{post_id}_*"
        matches = list(performer_dir.glob(pattern))

        if not matches:
            return None

        if len(matches) == 1:
            return matches[0]

        # Multiple matches - prefer one with stashapp_scene_id, then oldest
        best_match = None
        best_has_stash = False
        best_mtime = float("inf")

        for match in matches:
            release_json = match / "release.json"
            if not release_json.exists():
                continue

            try:
                data = json.loads(release_json.read_text(encoding="utf-8"))
                has_stash = data.get("stashapp_scene_id") is not None
                mtime = release_json.stat().st_mtime

                # Prefer: has stashapp_scene_id > oldest
                if has_stash and not best_has_stash:
                    best_match = match
                    best_has_stash = True
                    best_mtime = mtime
                elif has_stash == best_has_stash and mtime < best_mtime:
                    best_match = match
                    best_mtime = mtime
            except (json.JSONDecodeError, OSError):
                continue

        return best_match or matches[0]

    def load_reddit_data(self, file_path: str | Path) -> tuple[dict, dict]:
        """
        Load reddit data from aural_data/index/reddit format.

        The reddit index files have a nested structure:
        - Top-level: GWASI index data (post_id, tags, username, etc.)
        - reddit_data: Full PRAW enrichment (selftext, author_flair_text, comments, etc.)

        Returns:
            Tuple of (post, full_data):
            - post: Flat dict for process_post() with id, title, author, selftext
            - full_data: Original nested structure for enrichment storage
        """
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))

        # Extract reddit_data for processing (has selftext with audio links)
        post = data.get("reddit_data", data).copy()

        # Normalize field names (post_id -> id)
        post["id"] = post.get("post_id") or data.get("post_id")

        return post, data

    def get_extractor_for_url(self, url: str) -> tuple[str, dict] | None:
        """Get appropriate extractor for a URL."""
        for platform, config in self.extractors.items():
            if config["pattern"].search(url):
                return platform, config
        return None

    def sort_urls_by_priority(self, urls: list[dict]) -> list[dict]:
        """Sort URLs by platform priority, filtering unavailable platforms."""
        if not urls:
            return []

        # Filter unavailable platforms first if tracker provided
        if self.availability_tracker:
            urls = self.availability_tracker.filter_urls(urls)

        if not urls:
            return []

        def get_priority(url_info: dict) -> int:
            platform = (url_info.get("platform") or "").lower()
            try:
                return self.platform_priority.index(platform)
            except ValueError:
                return 99  # Unknown platforms get lowest priority

        return sorted(urls, key=get_priority)

    def extract_audio(self, url: str, target_path: dict) -> AudioSource:
        """
        Extract audio from URL directly to target path.

        Args:
            url: Audio URL to extract
            target_path: Dict with 'dir' and 'basename' keys

        Returns:
            AudioSource with extraction results
        """
        # Find appropriate extractor
        extractor_info = self.get_extractor_for_url(url)
        if not extractor_info:
            raise ValueError(f"No extractor found for URL: {url}")

        platform, config = extractor_info
        print(f"🔧 Using {platform} extractor for: {url}")

        try:
            # Get or create extractor instance
            extractor = self.active_extractors.get(platform)
            if not extractor:
                extractor_class = config["class"]
                extractor = extractor_class({"request_delay": 2.0})

                if hasattr(extractor, "setup_playwright"):
                    page, context = self._get_shared_playwright()
                    extractor.setup_playwright(page=page, context=context)

                self.active_extractors[platform] = extractor

            # Extract audio directly to target path
            result = extractor.extract(url, target_path)

            # Transform to AudioSource
            audio_source = self.normalize_extractor_result(result, platform)

            return audio_source

        except Exception as error:
            print(f"❌ Extraction failed for {url}: {error}")
            raise

    def extract_audio_multi_track(self, url: str, target_path: dict) -> list[AudioSource]:
        """
        Extract all audio tracks from a multi-track HotAudio CYOA page.

        Args:
            url: HotAudio URL to extract
            target_path: Dict with 'dir' key for output directory

        Returns:
            List of AudioSource objects, one for each track
        """
        extractor_info = self.get_extractor_for_url(url)
        if not extractor_info:
            raise ValueError(f"No extractor found for URL: {url}")

        platform, config = extractor_info

        if platform != "hotaudio":
            # Only HotAudio supports multi-track extraction
            return [self.extract_audio(url, target_path)]

        print(f"🔧 Using {platform} multi-track extractor for: {url}")

        try:
            extractor = self.active_extractors.get(platform)
            if not extractor:
                extractor_class = config["class"]
                extractor = extractor_class({"request_delay": 2.0})
                self.active_extractors[platform] = extractor

            # Use extract_all for multi-track extraction
            result = extractor.extract_all(url, target_path)

            audio_sources = []

            if result.get("isCYOA") and result.get("tracks"):
                # Multi-track CYOA result
                for track in result["tracks"]:
                    if "error" not in track:
                        audio_source = self.normalize_extractor_result(track, platform)
                        # Add track-specific metadata
                        audio_source.platform_data["trackIndex"] = track.get("trackIndex")
                        audio_source.platform_data["trackTitle"] = track.get("trackTitle")
                        audio_source.platform_data["tid"] = track.get("tid")
                        audio_source.platform_data["isCYOATrack"] = True
                        audio_sources.append(audio_source)
            elif result.get("tracks"):
                # Single track or fallback with tracks
                for track in result["tracks"]:
                    if "error" not in track:
                        audio_sources.append(
                            self.normalize_extractor_result(track, platform)
                        )
            else:
                audio_sources.append(
                    self.normalize_extractor_result(result, platform)
                )

            return audio_sources

        except Exception as error:
            print(f"❌ Multi-track extraction failed for {url}: {error}")
            raise

    def discover_hotaudio_tracks(self, url: str) -> list[dict]:
        """
        Discover all tracks on a HotAudio page without extracting.

        Args:
            url: HotAudio URL to scan

        Returns:
            List of track info dicts with tid, title, index
        """
        if "hotaudio.net" not in url.lower():
            return []

        try:
            extractor = self.active_extractors.get("hotaudio")
            if not extractor:
                extractor = HotAudioExtractor({"request_delay": 2.0})
                self.active_extractors["hotaudio"] = extractor

            return extractor.discover_tracks(url)
        except Exception as e:
            print(f"Warning: Failed to discover tracks: {e}")
            return []

    def cleanup(self):
        """Cleanup all active extractors."""
        for platform, extractor in self.active_extractors.items():
            if hasattr(extractor, "close_browser"):
                extractor.close_browser()
                print(f"🔒 Closed {platform} extractor")
        self.active_extractors.clear()

    def normalize_extractor_result(self, result: dict, platform: str) -> AudioSource:
        """Normalize extractor results to unified schema."""
        # If already an AudioSource, return as-is
        if isinstance(result, AudioSource):
            return result

        # Transform from extractor format to AudioSource schema
        audio = result.get("audio", {})
        metadata = result.get("metadata", {})

        audio_source = AudioSource(
            audio={
                "sourceUrl": audio.get("sourceUrl") or result.get("sourceUrl") or result.get("url"),
                "downloadUrl": audio.get("downloadUrl") or result.get("audioUrl"),
                "filePath": audio.get("filePath") or result.get("filePath"),
                "format": audio.get("format") or result.get("format", "m4a"),
                "fileSize": audio.get("fileSize") or result.get("fileSize"),
                "checksum": audio.get("checksum") or result.get("checksum", {}),
            },
            metadata={
                "title": metadata.get("title") or result.get("title"),
                "author": metadata.get("author") or result.get("author") or result.get("user"),
                "description": metadata.get("description") or result.get("description", ""),
                "tags": metadata.get("tags") or result.get("tags", []),
                "duration": metadata.get("duration") or result.get("duration"),
                "uploadDate": metadata.get("uploadDate") or result.get("uploadDate"),
                "extractedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "platform": {
                    "name": platform,
                    "extractorVersion": metadata.get("platform", {}).get("extractorVersion", "1.0")
                }
            },
            platform_data=result.get("platformData", {}),
            backup_files={
                "html": result.get("backupFiles", {}).get("html") or result.get("htmlBackup"),
                "metadata": result.get("backupFiles", {}).get("metadata") or result.get("metadataFile")
            }
        )

        return audio_source

    def process_post(
        self,
        post: dict,
        llm_analysis: dict,
        gwasi_data: dict | None = None
    ) -> Release:
        """
        Process a Reddit/Patreon post into a release.

        Args:
            post: Flat post dict with id, title, author, selftext, created_utc
            llm_analysis: LLM analysis results (required for proper URL grouping and naming)
            gwasi_data: Optional full GWASI data (preserves nested structure for enrichment)

        Raises:
            ValueError: If llm_analysis is not provided or has no audio_versions
        """
        self._validate_process_inputs(llm_analysis)
        print(f"🎯 Processing post: {post.get('title', 'Unknown')}")

        post_id = post.get("id") or llm_analysis.get("metadata", {}).get("post_id") or "unknown"
        release_dir = self._determine_release_directory(post, llm_analysis, post_id)

        existing_release = self._load_existing_release(release_dir)
        if existing_release:
            return existing_release

        release = self._create_release_object(post, llm_analysis, gwasi_data, post_id, release_dir)
        release_dir.mkdir(parents=True, exist_ok=True)

        self._extract_audio_sources(post, llm_analysis, release, release_dir)

        if not release.audio_sources:
            self.cleanup()
            raise ValueError("No audio sources could be downloaded - all extractions failed")

        self._extract_script_if_available(llm_analysis, release, release_dir)
        self._finalize_release(release)

        return release

    def _validate_process_inputs(self, llm_analysis: dict) -> None:
        """Validate that LLM analysis is provided and has audio versions."""
        if not llm_analysis:
            raise ValueError("LLM analysis is required. Run analyze_reddit_post.py first.")
        if not llm_analysis.get("audio_versions"):
            raise ValueError("LLM analysis has no audio_versions. Cannot process post.")

    def _determine_release_directory(
        self, post: dict, llm_analysis: dict, post_id: str
    ) -> Path:
        """Determine the release directory, using existing if found."""
        data_dir = Path(self.config["dataDir"])
        performer_dir = data_dir / "releases" / post.get("author", "unknown")

        existing_dir = self._find_existing_release_dir(performer_dir, post_id)
        if existing_dir:
            return existing_dir

        version_naming = llm_analysis.get("version_naming", {})
        if version_naming.get("release_directory"):
            release_dir_name = version_naming["release_directory"]
        else:
            title_slug = self._create_slug(post.get("title", ""), max_length=40)
            release_dir_name = f"{post_id}_{title_slug}" if title_slug else post_id

        return performer_dir / release_dir_name

    def _load_existing_release(self, release_dir: Path) -> Release | None:
        """Load existing release if valid, or return None to proceed with extraction."""
        release_path = release_dir / "release.json"
        if not release_path.exists():
            return None

        try:
            existing_data = json.loads(release_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        audio_sources = existing_data.get("audioSources", [])

        if not audio_sources:
            print("⚠️  Release exists but has no audio sources - re-extracting...")
            return None

        missing_files = self._find_missing_audio_files(audio_sources)
        if missing_files:
            print(f"⚠️  Release metadata exists but {len(missing_files)} audio file(s) missing:")
            for f in missing_files:
                print(f"     - {Path(f).name}")
            print("   Re-extracting audio...")
            return None

        print(f"⏭️  Release already exists: {release_dir}")
        print(f"   Audio sources: {len(audio_sources)}")

        return Release(
            id=existing_data.get("id", ""),
            title=existing_data.get("title"),
            primary_performer=existing_data.get("primaryPerformer"),
            additional_performers=existing_data.get("additionalPerformers", []),
            script_author=existing_data.get("scriptAuthor"),
            release_date=existing_data.get("releaseDate"),
            enrichment_data=existing_data.get("enrichmentData", {}),
            audio_sources=audio_sources,
            script=existing_data.get("script"),
            artwork=existing_data.get("artwork", []),
            aggregated_at=existing_data.get("aggregatedAt", ""),
            version=existing_data.get("version", "1.0"),
            release_dir=release_dir,
        )

    def _find_missing_audio_files(self, audio_sources: list[dict]) -> list[str]:
        """Check audio sources and return list of missing file paths."""
        missing = []
        for source in audio_sources:
            file_path = source.get("audio", {}).get("filePath")
            if file_path and not Path(file_path).exists():
                missing.append(file_path)
        return missing

    def _create_release_object(
        self,
        post: dict,
        llm_analysis: dict,
        gwasi_data: dict | None,
        post_id: str,
        release_dir: Path,
    ) -> Release:
        """Create a new Release object with enrichment data."""
        reddit_data = gwasi_data.get("reddit_data", post) if gwasi_data else post

        return Release(
            id=post_id,
            title=post.get("title"),
            primary_performer=post.get("author"),
            release_date=post.get("created_utc"),
            enrichment_data={
                "reddit": reddit_data,
                "patreon": None,
                "llmAnalysis": llm_analysis,
                "gwasi": gwasi_data,
            },
            release_dir=release_dir,
        )

    def _extract_audio_sources(
        self,
        post: dict,
        llm_analysis: dict,
        release: Release,
        release_dir: Path,
    ) -> None:
        """Extract all audio sources for the release."""
        audio_urls = self.extract_audio_urls(post, llm_analysis)
        print(f"🔗 Found {len(audio_urls)} unique audio URL{'s' if len(audio_urls) != 1 else ''}")

        self._try_extract_hotaudio_cyoa(audio_urls, release, release_dir)

        if not release.audio_sources:
            self._extract_audio_versions(llm_analysis, release, release_dir)

    def _try_extract_hotaudio_cyoa(
        self,
        audio_urls: list[str],
        release: Release,
        release_dir: Path,
    ) -> None:
        """Try to extract HotAudio CYOA multi-track content if applicable."""
        hotaudio_available = (
            not self.availability_tracker
            or self.availability_tracker.is_available("hotaudio")
        )
        if not hotaudio_available:
            return

        hotaudio_urls = [u for u in audio_urls if "hotaudio.net" in u.lower()]
        if len(hotaudio_urls) != 1:
            return

        hotaudio_url = hotaudio_urls[0]
        tracks = self.discover_hotaudio_tracks(hotaudio_url)
        if len(tracks) <= 1:
            return

        print(f"🎭 Detected HotAudio CYOA with {len(tracks)} tracks")
        target_path = {"dir": str(release_dir)}

        try:
            audio_sources = self.extract_audio_multi_track(hotaudio_url, target_path)
            for audio_source in audio_sources:
                track_title = audio_source.platform_data.get("trackTitle", "")
                audio_source.version_info = {
                    "version_name": track_title,
                    "description": f"CYOA Track: {track_title}",
                    "isCYOATrack": True,
                }
                release.add_audio_source(audio_source)
                print(f"✅ Added CYOA track: {track_title}")
        except Exception as error:
            if _is_disk_space_error(error):
                raise DiskSpaceError(str(error), error) from error
            print(f"❌ Multi-track extraction failed: {error}")

    def _extract_audio_versions(
        self,
        llm_analysis: dict,
        release: Release,
        release_dir: Path,
    ) -> None:
        """Process each audio version from LLM analysis."""
        for i, audio_version in enumerate(llm_analysis["audio_versions"]):
            if not audio_version.get("urls"):
                continue

            target_path = self._build_target_path(audio_version, llm_analysis, release, release_dir, i)
            audio_source, used_url = self._try_extract_from_platforms(audio_version, target_path, i)

            if audio_source:
                self._attach_version_metadata(audio_source, audio_version, used_url)
                release.add_audio_source(audio_source)
                version_name = audio_version.get("version_name", "Version")
                platform_name = audio_source.metadata["platform"]["name"]
                print(f"✅ Added audio source: {version_name} from {platform_name}")
            else:
                print(f"❌ All platforms failed for {audio_version.get('version_name') or f'Version {i + 1}'}")

    def _build_target_path(
        self,
        audio_version: dict,
        llm_analysis: dict,
        release: Release,
        release_dir: Path,
        index: int,
    ) -> dict:
        """Build target path configuration for audio extraction."""
        if audio_version.get("filename"):
            basename = re.sub(r"\.[^.]+$", "", audio_version["filename"])
        else:
            release_slug = llm_analysis.get("version_naming", {}).get("release_slug") or release.id
            basename = f"{release_slug}_{audio_version.get('slug', index)}"

        return {"dir": str(release_dir), "basename": basename}

    def _try_extract_from_platforms(
        self,
        audio_version: dict,
        target_path: dict,
        version_index: int,
    ) -> tuple[AudioSource | None, dict | None]:
        """Try extracting audio from each platform with retries."""
        sorted_urls = self.sort_urls_by_priority(audio_version["urls"])

        for url_info in sorted_urls:
            audio_source = self._try_extract_single_url(url_info, target_path, audio_version, version_index)
            if audio_source:
                return audio_source, url_info

        return None, None

    def _try_extract_single_url(
        self,
        url_info: dict,
        target_path: dict,
        audio_version: dict,
        version_index: int,
    ) -> AudioSource | None:
        """Try extracting from a single URL with retry logic."""
        url = url_info.get("url", "")

        # Filter out profile URLs (not actual audio content)
        if not is_audio_content_url(url):
            print(f"⏭️  Skipping profile URL: {url}")
            return None

        platform = url_info.get("platform", "unknown")
        max_retries = 3

        for retry_count in range(max_retries):
            try:
                version_name = audio_version.get("version_name") or f"Version {version_index + 1}"
                print(f"📥 Extracting: {url} ({version_name})")
                audio_source = self.extract_audio(url, target_path)

                if self.availability_tracker:
                    self.availability_tracker.record_success(platform)

                return audio_source
            except Exception as error:
                if _is_disk_space_error(error):
                    raise DiskSpaceError(str(error), error) from error

                if self.availability_tracker:
                    self.availability_tracker.record_failure(platform, error)

                if retry_count < max_retries - 1:
                    print(f"⚠️  Retry {retry_count + 1}/{max_retries} for {platform}: {error}")
                else:
                    print(f"❌ Failed {platform} after {max_retries} retries: {error}")

        return None

    def _attach_version_metadata(
        self,
        audio_source: AudioSource,
        audio_version: dict,
        used_url: dict,
    ) -> None:
        """Attach version-specific metadata to the audio source."""
        sorted_urls = self.sort_urls_by_priority(audio_version["urls"])

        audio_source.version_info = {
            "slug": audio_version.get("slug"),
            "version_name": audio_version.get("version_name"),
            "description": audio_version.get("description"),
            "performers": audio_version.get("performers", []),
            "tags": audio_version.get("tags", []),
        }

        audio_source.alternate_sources = [
            {"platform": u.get("platform"), "url": u.get("url")}
            for u in sorted_urls
            if u.get("url") != used_url.get("url")
        ]

    def _extract_script_if_available(
        self,
        llm_analysis: dict,
        release: Release,
        release_dir: Path,
    ) -> None:
        """Extract script if available in LLM analysis."""
        if not llm_analysis or not llm_analysis.get("script", {}).get("url"):
            return

        try:
            release.script = self.extract_script(llm_analysis["script"], release_dir)
        except Exception as error:
            print(f"❌ Failed to extract script: {error}")

    def _finalize_release(self, release: Release) -> None:
        """Save release and cleanup extractors."""
        self.save_release(release)
        self.cleanup()
        print(f"✅ Release processed: {release.id}")

    def extract_audio_urls(self, post: dict, llm_analysis: dict | None = None) -> list[str]:
        """Extract audio URLs from post and analysis."""
        urls = set()

        # From post content
        url_regex = re.compile(
            r"https?://(?:www\.)?(soundgasm\.net|whyp\.it|hotaudio\.net|audiochan\.com)[^\s\]]+",
            re.IGNORECASE
        )
        post_content = post.get("content") or post.get("selftext") or ""
        matches = url_regex.findall(post_content)
        for match in matches:
            # The regex captures just the domain, we need the full URL
            full_matches = re.findall(
                rf"https?://(?:www\.)?{re.escape(match)}[^\s\]]+",
                post_content,
                re.IGNORECASE
            )
            urls.update(full_matches)

        # Better approach: find all URLs directly
        all_urls = re.findall(
            r"https?://(?:www\.)?(?:soundgasm\.net|whyp\.it|hotaudio\.net|audiochan\.com)[^\s\]\)]+",
            post_content,
            re.IGNORECASE
        )
        urls.update(all_urls)

        # From LLM analysis
        if llm_analysis and llm_analysis.get("audio_versions"):
            for version in llm_analysis["audio_versions"]:
                if version.get("urls"):
                    for url_info in version["urls"]:
                        urls.add(url_info.get("url", ""))

        # Remove empty strings
        urls.discard("")

        # Clean URLs - strip trailing punctuation that may have been captured
        cleaned_urls = set()
        for url in urls:
            # Strip trailing ), ], or other punctuation that's not part of URL
            clean_url = url.rstrip(")].,:;!?")
            if clean_url:
                cleaned_urls.add(clean_url)

        return list(cleaned_urls)

    def extract_script(self, script_info: dict, release_dir: Path) -> dict:
        """
        Extract script from URL and save to release directory.

        Args:
            script_info: Script info object with url, author, fillType
            release_dir: Directory to save the script

        Returns:
            Script data including content and metadata
        """
        url = script_info.get("url", "")
        author = script_info.get("author")
        fill_type = script_info.get("fillType")

        print(f"📝 Extracting script: {url}")

        try:
            # Resolve the URL (handles Reddit share URLs, redirects, etc.)
            resolved_url = self.resolve_script_url(url)
            print(f"   Resolved URL: {resolved_url}")

            script_content = None
            html_content = None
            script_metadata = {
                "originalUrl": url,
                "resolvedUrl": resolved_url,
                "author": author,
                "fillType": fill_type,
                "extractedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z")
            }

            if "scriptbin.works" in resolved_url:
                result = self.extract_scriptbin_script(resolved_url)
                script_content = result.get("content")
                html_content = result.get("htmlContent")
                script_metadata.update(result.get("metadata", {}))
            elif "archiveofourown.org" in resolved_url:
                result = self.extract_ao3_script(resolved_url)
                script_content = result.get("content")
                html_content = result.get("htmlContent")
                script_metadata.update(result.get("metadata", {}))
            elif "reddit.com" in resolved_url:
                result = self.extract_reddit_script(resolved_url)
                script_content = result.get("content")
                html_content = result.get("htmlContent")
                script_metadata.update(result.get("metadata", {}))
            else:
                print(f"⚠️  Unknown script source: {resolved_url}")
                script_metadata["status"] = "unsupported_source"
                return script_metadata

            # Save script if we got content
            if script_content:
                script_path = release_dir / "script.txt"
                script_path.write_text(script_content, encoding="utf-8")
                script_metadata["filePath"] = str(script_path)
                script_metadata["status"] = "downloaded"
                print(f"✅ Script saved: {script_path}")

            # Save HTML backup if available
            if html_content:
                html_path = release_dir / "script.html"
                html_path.write_text(html_content, encoding="utf-8")
                script_metadata["htmlFilePath"] = str(html_path)
                print(f"✅ Script HTML saved: {html_path}")

            # Save script metadata
            metadata_path = release_dir / "script_metadata.json"
            metadata_path.write_text(
                json.dumps(script_metadata, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            return script_metadata

        except Exception as error:
            print(f"❌ Script extraction failed: {error}")
            return {
                "originalUrl": url,
                "author": author,
                "fillType": fill_type,
                "status": "failed",
                "error": str(error)
            }

    def resolve_script_url(self, url: str) -> str:
        """Resolve script URLs (handle redirects, share links, etc.)."""
        # Handle Reddit share URLs (format: reddit.com/r/.../s/xxx)
        if "/s/" in url:
            try:
                response = httpx.head(url, follow_redirects=True, timeout=30.0)
                return str(response.url)
            except Exception as error:
                print(f"⚠️  Could not resolve redirect for {url}: {error}")
                return url
        return url

    def extract_scriptbin_script(self, url: str) -> dict:
        """Extract script content from scriptbin.works using ScriptBinExtractor."""
        try:
            # Get or create scriptbin extractor instance
            extractor = self.active_extractors.get("scriptbin")
            if not extractor:
                extractor = ScriptBinExtractor()
                # Try to share browser from an active audio extractor
                page, context = self._get_shared_playwright()
                extractor.setup_playwright(page=page, context=context)
                self.active_extractors["scriptbin"] = extractor

            # Extract script data
            script_data = extractor.get_script_data(url)

            if not script_data or not script_data.get("script_content"):
                return {
                    "content": None,
                    "htmlContent": script_data.get("html_content") if script_data else None,
                    "metadata": {
                        "source": "scriptbin.works",
                        "url": url,
                        "note": "Could not extract script content"
                    }
                }

            # Join the script lines into a single content string
            content = "\n".join(script_data["script_content"])

            return {
                "content": content,
                "htmlContent": script_data.get("html_content"),
                "metadata": {
                    "source": "scriptbin.works",
                    "title": script_data.get("title"),
                    "author": script_data.get("author") or script_data.get("username"),
                    "wordCount": script_data.get("word_count"),
                    "characterCount": script_data.get("character_count"),
                    "performers": script_data.get("performers"),
                    "listeners": script_data.get("listeners"),
                    "tags": script_data.get("tags"),
                    "shortLink": script_data.get("short_link")
                }
            }

        except Exception as error:
            raise ValueError(f"Scriptbin extraction failed: {error}") from error

    def extract_ao3_script(self, url: str) -> dict:
        """Extract script content from archiveofourown.org using AO3Extractor."""
        try:
            # Get or create AO3 extractor instance
            extractor = self.active_extractors.get("ao3")
            if not extractor:
                extractor = AO3Extractor()
                # Try to share browser from an active audio extractor
                page, context = self._get_shared_playwright()
                extractor.setup_playwright(page=page, context=context)
                self.active_extractors["ao3"] = extractor

            # Extract work data
            work_data = extractor.get_work_data(url)

            if not work_data or not work_data.get("script_content"):
                return {
                    "content": None,
                    "htmlContent": work_data.get("html_content") if work_data else None,
                    "metadata": {
                        "source": "archiveofourown.org",
                        "url": url,
                        "note": "Could not extract work content"
                    }
                }

            # Join the content lines into a single string
            content = "\n".join(work_data["script_content"])

            return {
                "content": content,
                "htmlContent": work_data.get("html_content"),
                "metadata": {
                    "source": "archiveofourown.org",
                    "workId": work_data.get("work_id"),
                    "title": work_data.get("title"),
                    "author": work_data.get("author"),
                    "authors": work_data.get("authors"),
                    "username": work_data.get("username"),
                    "wordCount": work_data.get("word_count"),
                    "rating": work_data.get("rating"),
                    "archiveWarnings": work_data.get("archive_warnings"),
                    "categories": work_data.get("categories"),
                    "fandoms": work_data.get("fandoms"),
                    "relationships": work_data.get("relationships"),
                    "characters": work_data.get("characters"),
                    "additionalTags": work_data.get("additional_tags"),
                    "language": work_data.get("language"),
                    "published": work_data.get("published"),
                    "updated": work_data.get("updated"),
                    "chapters": work_data.get("chapters"),
                    "kudos": work_data.get("kudos"),
                    "summary": work_data.get("summary"),
                    "series": work_data.get("series")
                }
            }

        except Exception as error:
            raise ValueError(f"AO3 extraction failed: {error}") from error

    def extract_reddit_script(self, url: str) -> dict:
        """
        Extract script content from Reddit post.
        If the post contains a link to scriptbin.works, follows that link.
        """
        try:
            # Clean URL - remove query params and ensure proper format
            parsed = urlparse(url)
            clean_path = parsed.path.rstrip("/")
            json_url = f"https://www.reddit.com{clean_path}.json"

            response = httpx.get(
                json_url,
                headers={
                    "User-Agent": "Aural/1.0 (audio archival tool)",
                    "Accept": "application/json"
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                raise ValueError(f"Unexpected content type: {content_type}")

            data = response.json()

            # Reddit API returns array: [post, comments]
            post = data[0]["data"]["children"][0]["data"] if data else None

            if not post:
                raise ValueError("Could not find post data")

            post_content = post.get("selftext", "")
            title = post.get("title", "")
            post_author = post.get("author", "")

            reddit_metadata = {
                "source": "reddit",
                "title": title,
                "postAuthor": post_author,
                "postId": post.get("id"),
                "subreddit": post.get("subreddit"),
                "created": (
                    datetime.fromtimestamp(post["created_utc"], tz=UTC).isoformat()
                    if post.get("created_utc") else None
                ),
                "redditPostUrl": url
            }

            # Check if this Reddit post links to AO3 (preferred)
            ao3_match = re.search(
                r"https?://(?:www\.)?archiveofourown\.org/works/[^\s\)\]]+",
                post_content,
                re.IGNORECASE
            )

            if ao3_match:
                ao3_url = ao3_match.group(0)
                print(f"   Found archiveofourown.org link: {ao3_url}")

                try:
                    ao3_result = self.extract_ao3_script(ao3_url)

                    if ao3_result.get("content"):
                        return {
                            "content": ao3_result["content"],
                            "htmlContent": ao3_result.get("htmlContent"),
                            "metadata": {
                                **reddit_metadata,
                                **ao3_result.get("metadata", {}),
                                "source": "archiveofourown.org",
                                "ao3Url": ao3_url,
                                "redditScriptOfferPost": post_content
                            }
                        }
                except Exception as ao3_error:
                    # Don't fall back to Reddit post - propagate the failure
                    raise ValueError(
                        f"Found archiveofourown.org link but extraction failed: {ao3_error}"
                    ) from ao3_error

            # Check if this Reddit post links to scriptbin.works
            scriptbin_match = re.search(
                r"https?://(?:www\.)?scriptbin\.works/[^\s\)\]]+",
                post_content,
                re.IGNORECASE
            )

            if scriptbin_match:
                scriptbin_url = scriptbin_match.group(0)
                print(f"   Found scriptbin.works link: {scriptbin_url}")

                try:
                    scriptbin_result = self.extract_scriptbin_script(scriptbin_url)

                    if scriptbin_result.get("content"):
                        return {
                            "content": scriptbin_result["content"],
                            "htmlContent": scriptbin_result.get("htmlContent"),
                            "metadata": {
                                **reddit_metadata,
                                **scriptbin_result.get("metadata", {}),
                                "source": "scriptbin.works",
                                "scriptbinUrl": scriptbin_url,
                                "redditScriptOfferPost": post_content
                            }
                        }
                except Exception as scriptbin_error:
                    # Don't fall back to Reddit post - propagate the failure
                    raise ValueError(
                        f"Found scriptbin.works link but extraction failed: {scriptbin_error}"
                    ) from scriptbin_error

            # No scriptbin link found - return Reddit post content as the script
            return {
                "content": post_content,
                "metadata": reddit_metadata
            }

        except Exception as error:
            raise ValueError(f"Reddit script extraction failed: {error}") from error

    def save_release(self, release: Release):
        """Save release to storage."""
        release_dir = release.release_dir
        release_dir.mkdir(parents=True, exist_ok=True)

        # Save release metadata
        release_path = release_dir / "release.json"
        release_path.write_text(
            json.dumps(release.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Update release index
        self.update_release_index(release)

        print(f"💾 Release saved: {release_path}")

    def update_release_index(self, release: Release):
        """Update global release index."""
        data_dir = Path(self.config["dataDir"])
        index_path = data_dir / "releases" / "index.json"

        index = {"releases": []}
        try:
            if index_path.exists():
                index = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            pass

        # Add or update release in index
        index_entry = {
            "id": release.id,
            "title": release.title,
            "primaryPerformer": release.primary_performer,
            "audioSourceCount": len(release.audio_sources),
            "platforms": list({
                s.get("metadata", {}).get("platform", {}).get("name")
                for s in release.audio_sources
                if s.get("metadata", {}).get("platform", {}).get("name")
            }),
            "aggregatedAt": release.aggregated_at
        }

        # Find existing entry
        existing_index = next(
            (i for i, r in enumerate(index["releases"]) if r.get("id") == release.id),
            None
        )

        if existing_index is not None:
            index["releases"][existing_index] = index_entry
        else:
            index["releases"].append(index_entry)

        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def validate_extraction(self, audio_source: AudioSource) -> bool:
        """Validate extraction results."""
        if not self.config.get("validateExtractions", True):
            return True

        audio = audio_source.audio
        metadata = audio_source.metadata

        validations = {
            "hasFile": bool(audio.get("filePath")),
            "hasTitle": bool(metadata.get("title")),
            "hasAuthor": bool(metadata.get("author")),
            "hasChecksum": bool(audio.get("checksum", {}).get("sha256")),
            "fileExists": False
        }

        # Check if file exists
        if audio.get("filePath"):
            validations["fileExists"] = Path(audio["filePath"]).exists()

        is_valid = all(validations.values())

        if not is_valid:
            print(f"⚠️  Validation warnings: {validations}")

        return is_valid


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Release Orchestrator - Process posts into releases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process with automatic LLM analysis (default):
  uv run python release_orchestrator.py aural_data/index/reddit/performer/post.json

  # Process with pre-computed analysis:
  uv run python release_orchestrator.py post.json --analysis analysis.json
"""
    )
    parser.add_argument(
        "post_file",
        nargs="?",
        help="JSON file containing post data (from aural_data/index/reddit/...)"
    )
    parser.add_argument(
        "--analysis",
        "-a",
        help="JSON file containing pre-computed LLM analysis (skips LLM call)"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=str(aural_config.RELEASES_DIR.parent),
        help=f"Output directory (default: {aural_config.RELEASES_DIR.parent})"
    )

    args = parser.parse_args()

    if not args.post_file:
        parser.print_help()
        return 1

    try:
        # Load post data
        post_path = Path(args.post_file)
        if not post_path.exists():
            print(f"❌ Post file not found: {args.post_file}")
            return 1

        # Create orchestrator
        orchestrator = ReleaseOrchestrator({"dataDir": args.output_dir})

        # Use load_reddit_data for proper nested data handling
        post, gwasi_data = orchestrator.load_reddit_data(post_path)

        # Load pre-computed analysis or run LLM analysis
        if args.analysis:
            analysis_path = Path(args.analysis)
            if not analysis_path.exists():
                print(f"❌ Analysis file not found: {args.analysis}")
                return 1
            llm_analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            print(f"📋 Loaded analysis from: {args.analysis}")
        else:
            print("🤖 Running LLM analysis...")
            analyzer = EnhancedRedditPostAnalyzer()
            llm_analysis = analyzer.analyze_post(post_path)
            print("✅ LLM analysis complete")

        # Process the post
        release = orchestrator.process_post(post, llm_analysis, gwasi_data=gwasi_data)

        print("\n✅ Processing complete!")
        print(f"📁 Release ID: {release.id}")
        print(f"🎵 Audio sources: {len(release.audio_sources)}")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
