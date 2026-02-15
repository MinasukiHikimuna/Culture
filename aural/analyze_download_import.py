#!/usr/bin/env python3
"""
Analyze, Download, and Import Pipeline

Complete workflow script that:
1. Analyzes Reddit posts using analyze_reddit_post.py
2. Downloads audio files using the release orchestrator
3. Imports to Stashapp using stashapp_importer.py

Tracks processed posts to avoid duplicate work.

Usage:
    uv run python analyze_download_import.py <post_file_or_directory> [options]
"""

import argparse
import contextlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import config as aural_config
import httpx
from analyze_reddit_post import EnhancedRedditPostAnalyzer
from exceptions import DiskSpaceError, LMStudioUnavailableError, StashappUnavailableError
from platform_availability import PlatformAvailabilityTracker
from release_orchestrator import ReleaseOrchestrator
from stashapp_importer import STASH_BASE_URL, StashappImporter, StashScanStuckError


class RedditResolver:
    """Resolves crosspost content by fetching original post data."""

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "Aural/1.0 (audio archival tool)"},
        )

    def is_crosspost(self, reddit_data: dict) -> bool:
        """Check if the post is a crosspost."""
        # Check for crosspost_parent or crosspost_parent_list
        if reddit_data.get("crosspost_parent"):
            return True
        if reddit_data.get("crosspost_parent_list"):
            return True
        # Note: Empty selftext alone does NOT indicate a crosspost.
        # Link posts (is_self=False) legitimately have no selftext.
        return False

    def resolve(self, reddit_data: dict) -> dict | None:
        """
        Resolve crosspost to get original post content.

        Returns dict with selftext and resolved_from if successful, None otherwise.
        """
        try:
            # Try crosspost_parent_list first (contains full post data)
            crosspost_list = reddit_data.get("crosspost_parent_list", [])
            if crosspost_list:
                original = crosspost_list[0]
                if original.get("selftext", "").strip():
                    return {
                        "selftext": original["selftext"],
                        "resolved_from": "crosspost_parent_list",
                        "original_post": original,
                    }

            # Try fetching via crosspost_parent ID
            crosspost_parent = reddit_data.get("crosspost_parent")
            if crosspost_parent:
                # Format: t3_postid  # noqa: ERA001
                post_id = crosspost_parent.replace("t3_", "")
                return self._fetch_post_by_id(post_id)

            return None

        except Exception as e:
            print(f"  Warning: Failed to resolve crosspost: {e}")
            return None

    def _fetch_post_by_id(self, post_id: str) -> dict | None:
        """Fetch post data by ID from Reddit API."""
        try:
            url = f"https://www.reddit.com/api/info.json?id=t3_{post_id}"
            response = self.client.get(url)

            if response.status_code != 200:
                return None

            data = response.json()
            children = data.get("data", {}).get("children", [])
            if children:
                post = children[0].get("data", {})
                selftext = post.get("selftext", "")
                if selftext.strip():
                    return {
                        "selftext": selftext,
                        "resolved_from": "api_fetch",
                        "original_post": post,
                    }

            return None

        except Exception:
            return None


class AnalyzeDownloadImportPipeline:
    """Main pipeline class for processing Reddit posts."""

    def __init__(self, options: dict | None = None):
        options = options or {}
        self.analysis_dir = Path(options.get("analysis_dir", str(aural_config.ANALYSIS_DIR)))
        self.data_dir = Path(options.get("data_dir", str(aural_config.RELEASES_DIR.parent)))
        self.dry_run = options.get("dry_run", False)
        self.verbose = options.get("verbose", False)
        self.skip_analysis = options.get("skip_analysis", False)
        self.skip_import = options.get("skip_import", False)
        self.force = options.get("force", False)
        self.skip_health_check = options.get("skip_health_check", False)

        # Platform availability tracking
        self.availability_tracker = PlatformAvailabilityTracker()

        # Mark manually skipped platforms from CLI
        for platform in options.get("skip_platforms", []):
            self.availability_tracker.mark_manually_skipped(platform.lower())

        # Initialize release orchestrator with availability tracker
        self.release_orchestrator = ReleaseOrchestrator(
            {"dataDir": str(self.data_dir), "validateExtractions": True},
            availability_tracker=self.availability_tracker,
        )

        # Lazy-loaded components
        self._stashapp_importer: StashappImporter | None = None
        self._analyzer: EnhancedRedditPostAnalyzer | None = None
        self._reddit_resolver: RedditResolver | None = None

        # Processed posts tracking
        self._processed_posts: dict | None = None

    @property
    def analyzer(self) -> EnhancedRedditPostAnalyzer:
        """Lazy-load the analyzer."""
        if self._analyzer is None:
            self._analyzer = EnhancedRedditPostAnalyzer()
        return self._analyzer

    @property
    def reddit_resolver(self) -> RedditResolver:
        """Lazy-load the Reddit resolver."""
        if self._reddit_resolver is None:
            self._reddit_resolver = RedditResolver()
        return self._reddit_resolver

    def load_processed_posts(self) -> dict:
        """Load processed posts tracking data."""
        if self._processed_posts is not None:
            return self._processed_posts

        tracking_path = self.data_dir / "processed_posts.json"
        try:
            self._processed_posts = json.loads(
                tracking_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError):
            self._processed_posts = {"posts": {}, "lastUpdated": None}

        return self._processed_posts

    def save_processed_posts(self) -> None:
        """Save processed posts tracking data."""
        if self._processed_posts is None:
            return

        tracking_path = self.data_dir / "processed_posts.json"
        self._processed_posts["lastUpdated"] = (
            datetime.now(UTC).isoformat().replace("+00:00", "Z")
        )
        tracking_path.parent.mkdir(parents=True, exist_ok=True)
        tracking_path.write_text(
            json.dumps(self._processed_posts, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def is_processed(self, post_id: str) -> bool:
        """
        Check if a post has already been successfully processed.
        Only returns True if the post was fully imported to Stash or intentionally skipped.
        """
        processed = self.load_processed_posts()
        record = processed.get("posts", {}).get(post_id)
        if not record:
            return False

        # Processed if: successful import with scene ID, OR intentionally skipped
        return (
            record.get("success") is True and record.get("stashSceneId") is not None
        ) or (record.get("success") is True and record.get("stage") == "skipped")

    def mark_processed(self, post_id: str, result: dict) -> None:
        """Mark a post as processed."""
        processed = self.load_processed_posts()
        processed["posts"][post_id] = {
            "processedAt": datetime.now(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "releaseId": result.get("release", {}).get("id")
            if result.get("release")
            else None,
            "releaseDir": result.get("releaseDir"),
            "stashSceneId": result.get("stashSceneId"),
            "audioSourceCount": len(result.get("release", {}).get("audioSources", []))
            if result.get("release")
            else 0,
            "success": result.get("success", False),
            "stage": result.get("stage"),
            "reason": result.get("reason"),
        }
        self.save_processed_posts()

    def get_post_id(self, post_file_path: Path) -> str:
        """Get post ID from file path or content."""
        try:
            data = json.loads(post_file_path.read_text(encoding="utf-8"))
            return (
                data.get("reddit_data", {}).get("id")
                or post_file_path.stem.split("_")[0]
            )
        except (json.JSONDecodeError, FileNotFoundError):
            return post_file_path.stem.split("_")[0]

    def _pre_check_audio_platforms(
        self, content: str, post_id: str, progress_prefix: str
    ) -> dict | None:
        """
        Pre-analysis check: scan raw post content for audio platform URLs.

        Returns a skip result dict if all found URLs are from unavailable platforms,
        or None to continue with normal processing.
        """
        # Regex to find audio platform URLs in content
        platform_patterns = {
            "soundgasm": r"soundgasm\.net",
            "whypit": r"whyp\.it",
            "hotaudio": r"hotaudio\.net",
            "audiochan": r"audiochan\.com",
        }

        found_platforms: set[str] = set()
        for platform, pattern in platform_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                found_platforms.add(platform)

        if not found_platforms:
            # No audio URLs found - continue with analysis (might be in comments, etc.)
            return None

        # Check if any found platforms are available
        available = [p for p in found_platforms if self.availability_tracker.is_available(p)]

        if not available:
            # All found platforms are unavailable - skip without analysis
            unavailable_str = ", ".join(sorted(found_platforms))
            print(f"{progress_prefix}  Skipped (pre-check): only {unavailable_str} URLs found")
            return {
                "success": False,
                "skipped": True,
                "postId": post_id,
                "skippedDueToUnavailablePlatforms": True,
                "unavailablePlatforms": list(found_platforms),
                "preCheck": True,
            }

        # Some available platforms found - continue with analysis
        return None

    def has_analyzable_content(self, post_file_path: Path) -> dict:
        """
        Check if a post has content that can be analyzed.
        Attempts to resolve crossposts by fetching the original post.
        """
        try:
            data = json.loads(post_file_path.read_text(encoding="utf-8"))
            reddit_data = data.get("reddit_data")

            if not reddit_data:
                return {"ok": False, "reason": "missing reddit_data"}

            selftext = reddit_data.get("selftext") or ""

            # If we have content, we're good
            if selftext.strip():
                return {"ok": True}

            # Check if this is a link post with an audio URL (no selftext needed)
            if not reddit_data.get("is_self", True):
                url = reddit_data.get("url", "")
                audio_domains = ["soundgasm.net", "whyp.it", "hotaudio.net", "audiochan.com"]
                if any(domain in url for domain in audio_domains):
                    return {"ok": True, "link_post": True}

            # Check if this is a crosspost that we can resolve
            if self.reddit_resolver.is_crosspost(reddit_data):
                print("  Detected crosspost, attempting to resolve...")

                resolved = self.reddit_resolver.resolve(reddit_data)

                if resolved and resolved.get("selftext", "").strip():
                    # Update the file with resolved content
                    data["reddit_data"]["selftext"] = resolved["selftext"]
                    data["reddit_data"]["resolved_from"] = resolved["resolved_from"]
                    if resolved.get("original_post"):
                        data["reddit_data"]["original_post"] = resolved["original_post"]
                    post_file_path.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                    print("  Crosspost resolved successfully")
                    return {"ok": True, "resolved": True}

                return {"ok": False, "reason": "crosspost target unavailable or empty"}

            # Empty selftext and not a resolvable crosspost
            return {"ok": False, "reason": "empty selftext (not a crosspost)"}

        except Exception as e:
            return {"ok": False, "reason": str(e)}

    def analyze_post(self, post_file_path: Path) -> dict:
        """Analyze a single Reddit post file."""
        try:
            # Check if post has analyzable content
            content_check = self.has_analyzable_content(post_file_path)
            if not content_check.get("ok"):
                return {
                    "success": False,
                    "postFile": str(post_file_path),
                    "error": content_check.get("reason"),
                    "noContent": True,
                }

            self.analysis_dir.mkdir(parents=True, exist_ok=True)

            post_file_name = post_file_path.stem
            analysis_file_name = f"{post_file_name}_analysis.json"
            analysis_file_path = self.analysis_dir / analysis_file_name

            # Check if analysis already exists
            if self.skip_analysis and analysis_file_path.exists():
                if self.verbose:
                    print(f"  Using existing analysis: {analysis_file_path}")
                return {
                    "success": True,
                    "postFile": str(post_file_path),
                    "analysisFile": str(analysis_file_path),
                    "skipped": True,
                }

            if self.verbose:
                print(f"  Analyzing post: {post_file_path}")

            # Use the Python analyzer directly
            analysis = self.analyzer.analyze_post(post_file_path)

            # Save analysis to file
            analysis_file_path.write_text(
                json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            return {
                "success": True,
                "postFile": str(post_file_path),
                "analysisFile": str(analysis_file_path),
            }

        except LMStudioUnavailableError:
            # Re-raise mandatory resource errors to abort processing
            raise
        except Exception as e:
            print(f"  Analysis failed for {post_file_path}: {e}")
            return {
                "success": False,
                "postFile": str(post_file_path),
                "error": str(e),
            }

    def extract_audio_urls(self, post: dict, analysis: dict | None = None) -> list[str]:
        """Extract audio URLs from post and analysis."""
        urls: set[str] = set()

        post_content = post.get("selftext") or post.get("content") or ""

        # Get full URLs
        full_urls = re.findall(
            r"https?://(?:www\.)?(?:soundgasm\.net|whyp\.it|hotaudio\.net|audiochan\.com)[^\s\]\)]+",
            post_content,
            re.IGNORECASE,
        )
        urls.update(full_urls)

        # From LLM analysis
        if analysis and analysis.get("audio_versions"):
            for version in analysis["audio_versions"]:
                if version.get("urls"):
                    for url_info in version["urls"]:
                        urls.add(url_info.get("url", ""))

        # Remove empty strings and clean URLs
        urls.discard("")
        cleaned_urls = {url.rstrip(")].,:;!?") for url in urls if url}

        return list(cleaned_urls)

    def process_analysis_with_orchestrator(
        self, analysis_file_path: Path, post_file_path: Path | None = None
    ) -> dict:
        """Process analysis through release orchestrator (download audio)."""
        try:
            analysis = json.loads(analysis_file_path.read_text(encoding="utf-8"))

            post_data = None
            if post_file_path:
                try:
                    post_data = json.loads(post_file_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    print(f"  Warning: Could not load original post: {e}")

            post = {
                "id": analysis.get("metadata", {}).get("post_id")
                or (post_data.get("reddit_data", {}).get("id") if post_data else None),
                "title": analysis.get("metadata", {}).get("title")
                or (
                    post_data.get("reddit_data", {}).get("title") if post_data else None
                ),
                "author": analysis.get("metadata", {}).get("username")
                or (
                    post_data.get("reddit_data", {}).get("author")
                    if post_data
                    else None
                ),
                "created_utc": analysis.get("metadata", {}).get("created_utc")
                or (
                    post_data.get("reddit_data", {}).get("created_utc")
                    if post_data
                    else None
                ),
                "selftext": analysis.get("metadata", {}).get("content")
                or (
                    post_data.get("reddit_data", {}).get("selftext")
                    if post_data
                    else ""
                ),
                "url": analysis.get("metadata", {}).get("url")
                or (post_data.get("reddit_data", {}).get("url") if post_data else None),
                "subreddit": analysis.get("metadata", {}).get("subreddit")
                or (
                    post_data.get("reddit_data", {}).get("subreddit")
                    if post_data
                    else "gonewildaudio"
                ),
                "original_metadata": analysis.get("metadata"),
                "reddit_data": post_data.get("reddit_data") if post_data else None,
            }

            if self.dry_run:
                print("[DRY RUN] Would process the following:")
                print(f"  Post: {post.get('title')}")
                print(f"  Author: {post.get('author')}")

                audio_urls = self.extract_audio_urls(post, analysis)
                print(f"  Audio URLs: {len(audio_urls)}")
                for url in audio_urls:
                    print(f"    - {url}")

                return {
                    "success": True,
                    "dryRun": True,
                    "analysisFile": str(analysis_file_path),
                }

            release = self.release_orchestrator.process_post(
                post, analysis, gwasi_data=post_data
            )

            # Use the actual release directory from the orchestrator
            # (prevents path mismatch from LLM non-deterministic slug generation)
            release_dir = release.release_dir

            return {
                "success": True,
                "analysisFile": str(analysis_file_path),
                "release": release.to_dict(),
                "releaseDir": str(release_dir),
                "audioSourceCount": len(release.audio_sources),
                "cyoaDetection": analysis.get("cyoa_detection"),
            }

        except Exception as e:
            print(f"  Processing failed for {analysis_file_path}: {e}")
            if self.verbose:
                import traceback

                traceback.print_exc()
            return {
                "success": False,
                "analysisFile": str(analysis_file_path),
                "error": str(e),
            }

    def import_to_stashapp(self, release_dir: str) -> dict:
        """Import release to Stashapp.

        Raises:
            StashScanStuckError: If Stashapp scan is stuck and not completing.
                This exception is NOT caught here - it propagates up to abort the batch.
        """
        if self.skip_import:
            print("  Skipping Stashapp import (--skip-import)")
            return {"success": True, "skipped": True}

        try:
            print(f"  Importing to Stashapp: {release_dir}")

            # Check if already imported by looking for stashapp_scene_id in release.json
            release_path = Path(release_dir) / "release.json"
            if release_path.exists():
                try:
                    release_data = json.loads(release_path.read_text(encoding="utf-8"))
                    existing_scene_id = release_data.get("stashapp_scene_id")
                    if existing_scene_id:
                        print(
                            f"  Already imported to Stashapp: "
                            f"{STASH_BASE_URL}/scenes/{existing_scene_id}"
                        )
                        return {"success": True, "stashSceneId": existing_scene_id}
                except (json.JSONDecodeError, KeyError):
                    pass  # Continue with import if we can't read the file

            # Initialize importer on first use
            if self._stashapp_importer is None:
                self._stashapp_importer = StashappImporter(verbose=self.verbose)
                self._stashapp_importer.test_connection()

            result = self._stashapp_importer.process_release(release_dir)

            if result.get("success"):
                print("  Stashapp import completed")
                return {"success": True, "stashSceneId": result.get("sceneId")}
            print(f"  Stashapp import failed: {result.get('error')}")
            return {"success": False, "error": result.get("error")}

        except (StashScanStuckError, StashappUnavailableError):
            # Let mandatory resource errors propagate up to abort the batch
            raise

        except Exception as e:
            print(f"  Stashapp import failed: {e}")
            return {"success": False, "error": str(e)}

    def reextract_script(self, release_dir: Path) -> dict:
        """
        Re-extract only the script for an existing release.

        Args:
            release_dir: Path to the release directory containing release.json

        Returns:
            dict with success status and script info
        """
        from release_orchestrator import ReleaseOrchestrator

        release_path = release_dir / "release.json"
        if not release_path.exists():
            print(f"  Error: No release.json found in {release_dir}")
            return {"success": False, "error": "release.json not found"}

        try:
            release_data = json.loads(release_path.read_text(encoding="utf-8"))
            llm_analysis = release_data.get("enrichmentData", {}).get("llmAnalysis", {})
            script_info = llm_analysis.get("script", {})

            if not script_info.get("url"):
                print("  No script URL found in release metadata")
                return {"success": False, "error": "No script URL in metadata"}

            print(f"  Re-extracting script for: {release_dir.name}")
            print(f"  Script URL: {script_info['url']}")

            # Delete existing script files
            for script_file in ["script.txt", "script.html", "script_metadata.json"]:
                script_path = release_dir / script_file
                if script_path.exists():
                    script_path.unlink()
                    print(f"  Deleted: {script_file}")

            # Use release orchestrator to extract the script
            orchestrator = ReleaseOrchestrator({"dataDir": str(self.data_dir)})

            try:
                script_result = orchestrator.extract_script(script_info, release_dir)

                if script_result.get("status") == "downloaded":
                    print(f"  Script saved: {script_result.get('filePath')}")

                    # Update release.json with new script info
                    release_data["script"] = script_result
                    release_path.write_text(
                        json.dumps(release_data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    print("  Updated release.json")

                    return {"success": True, "script": script_result}
                print(f"  Script extraction failed: {script_result.get('error')}")
                return {"success": False, "error": script_result.get("error")}

            finally:
                orchestrator.cleanup()

        except Exception as e:
            print(f"  Script re-extraction failed: {e}")
            if self.verbose:
                import traceback

                traceback.print_exc()
            return {"success": False, "error": str(e)}

    def process_post(self, post_file_path: Path, progress_prefix: str = "") -> dict:
        """
        Process a single Reddit post through the complete pipeline.

        Args:
            post_file_path: Path to the post JSON file
            progress_prefix: Optional prefix for progress display (e.g., "[1/247]")
        """
        post_id = self.get_post_id(post_file_path)

        # Check if already processed
        if not self.force and self.is_processed(post_id):
            print(
                f"{progress_prefix}  Already processed: {post_id} ({post_file_path.name})"
            )
            # Include stashSceneId so callers can clean up legacy files
            processed = self.load_processed_posts()
            record = processed.get("posts", {}).get(post_id, {})
            return {
                "success": True,
                "skipped": True,
                "postId": post_id,
                "stashSceneId": record.get("stashSceneId"),
                "alreadyProcessed": True,
            }

        # Early detection for deleted/removed content
        try:
            post_data = json.loads(post_file_path.read_text(encoding="utf-8"))
            reddit_data = post_data.get("reddit_data", {})
            selftext = reddit_data.get("selftext", "")

            if selftext in ("[removed]", "[deleted]"):
                removal_type = "removed" if selftext == "[removed]" else "deleted"
                print(
                    f"{progress_prefix}  Content {removal_type}: {post_id} "
                    f"(post content is no longer available on Reddit)"
                )
                # Don't mark as processed - these need manual curation
                return {
                    "success": False,
                    "skipped": True,
                    "postId": post_id,
                    "contentDeleted": True,
                    "reason": f"content_{removal_type}",
                }

            # Pre-analysis platform check: scan raw content for audio URLs
            # This avoids running expensive LLM analysis for posts with only unavailable platforms
            if self.availability_tracker.get_unavailable_platforms():
                pre_check = self._pre_check_audio_platforms(selftext, post_id, progress_prefix)
                if pre_check:
                    return pre_check

        except (json.JSONDecodeError, FileNotFoundError):
            pass  # Continue with analysis if we can't read the file

        # Step 1: Analyze the post
        analysis_result = self.analyze_post(post_file_path)
        if not analysis_result.get("success"):
            # Handle posts with no content (crossposts, link posts) as skipped, not failed
            if analysis_result.get("noContent"):
                print(
                    f"{progress_prefix}  No content: {post_id} ({analysis_result.get('error')})"
                )
                self.mark_processed(
                    post_id,
                    {
                        "success": True,
                        "stage": "skipped",
                        "reason": analysis_result.get("error"),
                    },
                )
                return {
                    "success": True,
                    "skipped": True,
                    "postId": post_id,
                    "noContent": True,
                }

            print(f"\n{'=' * 60}")
            print(f"{progress_prefix}  Analysis failed: {post_file_path.name}")
            print(f"{'=' * 60}")
            print(f"Error: {analysis_result.get('error')}")
            # Don't mark as processed - allow retry on next run
            return {
                "success": False,
                "stage": "analysis",
                "postFile": str(post_file_path),
                "error": analysis_result.get("error"),
            }

        print(f"\n{'=' * 60}")
        print(f"{progress_prefix}  Processing: {post_file_path.name}")
        print(f"{'=' * 60}")

        # Load analysis and check post type
        analysis_file = Path(analysis_result["analysisFile"])
        analysis = json.loads(analysis_file.read_text(encoding="utf-8"))

        # Also load original post data for heuristic checks
        original_post = None
        with contextlib.suppress(json.JSONDecodeError, FileNotFoundError):
            original_post = json.loads(post_file_path.read_text(encoding="utf-8"))

        # Heuristic detection for script offers (fallback for older analyses without post_type)
        is_script_offer_heuristic = (
            analysis.get("post_type") == "script_offer"
            or (
                original_post
                and "script offer"
                in (
                    original_post.get("reddit_data", {}).get("link_flair_text") or ""
                ).lower()
            )
            or (
                original_post
                and "script offer" in (original_post.get("post_type") or "").lower()
            )
            or (
                original_post
                and original_post.get("reddit_data", {}).get("subreddit")
                == "GWAScriptGuild"
                and not any(v.get("urls") for v in analysis.get("audio_versions", []))
            )
        )

        if is_script_offer_heuristic:
            print(
                f"{progress_prefix}  Script Offer: Skipping audio download "
                "(script offers don't contain audio)"
            )
            self.mark_processed(
                post_id, {"success": True, "stage": "skipped", "reason": "script_offer"}
            )
            return {
                "success": True,
                "skipped": True,
                "postId": post_id,
                "scriptOffer": True,
            }

        if analysis.get("post_type") == "request":
            print(
                f"{progress_prefix}  Request Post: Skipping (content requests don't contain audio)"
            )
            self.mark_processed(
                post_id, {"success": True, "stage": "skipped", "reason": "request_post"}
            )
            return {
                "success": True,
                "skipped": True,
                "postId": post_id,
                "requestPost": True,
            }

        if analysis.get("post_type") == "other":
            print(
                f"{progress_prefix}  Other Post: Skipping (announcement, meta post, etc.)"
            )
            self.mark_processed(
                post_id,
                {"success": True, "stage": "skipped", "reason": "other_post_type"},
            )
            return {
                "success": True,
                "skipped": True,
                "postId": post_id,
                "otherPost": True,
            }

        # Verification posts should be processed normally (they contain audio)
        if analysis.get("post_type") == "verification":
            print(f"{progress_prefix}  Verification post - processing as audio content")

        # Check if there are no audio URLs to download
        audio_urls = [
            u.get("url")
            for v in analysis.get("audio_versions", [])
            for u in v.get("urls", [])
            if u.get("url")
        ]
        if not audio_urls:
            print(
                f"{progress_prefix}  No Audio URLs: Skipping (no audio links found in post)"
            )
            self.mark_processed(
                post_id,
                {"success": True, "stage": "skipped", "reason": "no_audio_urls"},
            )
            return {
                "success": True,
                "skipped": True,
                "postId": post_id,
                "noAudioUrls": True,
            }

        # Check if there are audio URLs from available platforms
        audio_urls_by_platform: dict[str, list[str]] = {}
        for v in analysis.get("audio_versions", []):
            for u in v.get("urls", []):
                if u.get("url"):
                    platform = (u.get("platform") or "unknown").lower()
                    if platform not in audio_urls_by_platform:
                        audio_urls_by_platform[platform] = []
                    audio_urls_by_platform[platform].append(u.get("url"))

        # Filter to only available platforms
        available_platforms = [
            p
            for p in audio_urls_by_platform
            if self.availability_tracker.is_available(p)
        ]

        if not available_platforms:
            unavailable = list(audio_urls_by_platform.keys())
            print(
                f"{progress_prefix}  Skipped: All audio URLs from unavailable platforms "
                f"({', '.join(unavailable)})"
            )
            # Don't mark as processed - allow retry when platforms come back
            return {
                "success": False,
                "skipped": True,
                "postId": post_id,
                "skippedDueToUnavailablePlatforms": True,
                "unavailablePlatforms": unavailable,
            }

        # Step 2: Download audio through release orchestrator
        print("\n  Step 2: Downloading audio...")
        process_result = self.process_analysis_with_orchestrator(
            analysis_file, post_file_path
        )

        if not process_result.get("success"):
            # Don't mark as processed - allow retry on next run
            return {
                "success": False,
                "stage": "download",
                "postFile": str(post_file_path),
                "analysisFile": str(analysis_file),
                "error": process_result.get("error"),
            }

        if process_result.get("dryRun"):
            return {"success": True, "dryRun": True}

        # Step 3: Import to Stashapp
        print("\n  Step 3: Importing to Stashapp...")
        import_result = self.import_to_stashapp(process_result["releaseDir"])

        # Only mark as processed if import fully succeeded with a scene ID
        if not import_result.get("success") or not import_result.get("stashSceneId"):
            print(
                f"  Import failed: {import_result.get('error') or 'No scene created'}"
            )
            # Don't mark as processed - allow retry on next run
            return {
                "success": False,
                "stage": "import",
                "postFile": str(post_file_path),
                "releaseDir": process_result["releaseDir"],
                "error": import_result.get("error") or "No scene created",
            }

        # Get Reddit URL from post file
        reddit_url = None
        try:
            post_data = json.loads(post_file_path.read_text(encoding="utf-8"))
            reddit_url = post_data.get("reddit_url") or post_data.get(
                "reddit_data", {}
            ).get("permalink")
        except (json.JSONDecodeError, FileNotFoundError):
            pass

        # Check for CYOA
        cyoa_detection = process_result.get("cyoaDetection")
        is_cyoa = cyoa_detection.get("is_cyoa") is True if cyoa_detection else False

        # Mark as successfully processed
        result = {
            "success": True,
            "postFile": str(post_file_path),
            "analysisFile": str(analysis_file),
            "release": process_result.get("release"),
            "releaseDir": process_result["releaseDir"],
            "stashSceneId": import_result.get("stashSceneId"),
            "redditUrl": reddit_url,
            "importSuccess": import_result.get("success"),
            "isCYOA": is_cyoa,
            "cyoaDetection": cyoa_detection,
        }

        self.mark_processed(post_id, result)

        # Summary
        print(f"\n{'-' * 60}")
        print(f"  Release: {process_result['release']['id']}")
        print(f"  Audio sources: {process_result['audioSourceCount']}")
        print(f"  Directory: {process_result['releaseDir']}")
        if reddit_url:
            print(f"  Reddit: {reddit_url}")
        if import_result.get("stashSceneId"):
            print(
                f"  Stashapp: {STASH_BASE_URL}/scenes/{import_result['stashSceneId']}"
            )
        if is_cyoa:
            print("  CYOA: Requires manual decision tree mapping in Stashapp")

        return result

    def process_batch(self, post_files: list[Path]) -> dict:
        """Process multiple Reddit posts."""
        print(f"\n  Processing batch of {len(post_files)} Reddit posts")
        print(f"{'=' * 60}\n")

        self._run_health_checks()

        results = self._create_empty_results()

        for i, post_file in enumerate(post_files):
            progress_prefix = f"[{i + 1}/{len(post_files)}]"
            should_abort = self._process_single_post(
                post_file, progress_prefix, results, i, len(post_files)
            )
            if should_abort:
                break

        self._print_batch_summary(results)
        return results

    def _run_health_checks(self) -> None:
        """Run platform health checks and report results."""
        if not self.skip_health_check:
            print("  Checking audio platform availability...")
            health_results = self.availability_tracker.run_health_checks()
            for platform, result in sorted(health_results.items()):
                if result.get("skipped"):
                    print(f"    {platform}: SKIPPED (CLI flag)")
                elif result.get("available"):
                    print(f"    {platform}: available")
                else:
                    print(f"    {platform}: UNAVAILABLE - {result.get('error')}")
            print()

        if self.availability_tracker.manually_skipped:
            skipped_str = ", ".join(sorted(self.availability_tracker.manually_skipped))
            print(f"  Skipped platforms (CLI): {skipped_str}\n")

    def _create_empty_results(self) -> dict:
        """Create an empty results dictionary."""
        return {
            "processed": [],
            "skipped": [],
            "failed": [],
            "cyoa": [],
            "scriptOffers": [],
            "requestPosts": [],
            "otherPosts": [],
            "noAudioUrls": [],
            "skippedUnavailablePlatforms": [],
        }

    def _process_single_post(
        self,
        post_file: Path,
        progress_prefix: str,
        results: dict,
        index: int,
        total: int,
    ) -> bool:
        """Process a single post and update results. Returns True if batch should abort."""
        try:
            result = self.process_post(post_file, progress_prefix)
            self._categorize_result(post_file, result, results)
            self._maybe_delay_between_posts(result, index, total)
            return False
        except (StashScanStuckError, DiskSpaceError) as e:
            self._handle_critical_error(e, post_file, results)
            return True
        except Exception as e:
            print(f"  Unexpected error: {e}")
            results["failed"].append({"file": str(post_file), "error": str(e)})
            return False

    def _categorize_result(self, post_file: Path, result: dict, results: dict) -> None:
        """Categorize a post result into the appropriate results bucket."""
        if result.get("skipped"):
            self._categorize_skipped_result(post_file, result, results)
        elif result.get("success"):
            self._categorize_success_result(post_file, result, results)
        else:
            results["failed"].append({
                "file": str(post_file),
                "stage": result.get("stage"),
                "error": result.get("error"),
            })

    def _categorize_skipped_result(
        self, post_file: Path, result: dict, results: dict
    ) -> None:
        """Categorize a skipped post result."""
        results["skipped"].append({
            "file": str(post_file),
            "postId": result.get("postId"),
        })

        skip_reason_map = [
            ("skippedDueToUnavailablePlatforms", "skippedUnavailablePlatforms", {
                "file": str(post_file),
                "postId": result.get("postId"),
                "platforms": result.get("unavailablePlatforms", []),
            }),
            ("scriptOffer", "scriptOffers", {
                "file": str(post_file),
                "postId": result.get("postId"),
            }),
            ("requestPost", "requestPosts", {
                "file": str(post_file),
                "postId": result.get("postId"),
            }),
            ("otherPost", "otherPosts", {
                "file": str(post_file),
                "postId": result.get("postId"),
            }),
            ("noAudioUrls", "noAudioUrls", {
                "file": str(post_file),
                "postId": result.get("postId"),
            }),
        ]

        for result_key, results_key, entry in skip_reason_map:
            if result.get(result_key):
                results[results_key].append(entry)
                break

    def _categorize_success_result(
        self, post_file: Path, result: dict, results: dict
    ) -> None:
        """Categorize a successful post result."""
        results["processed"].append({"file": str(post_file), "result": result})

        if result.get("isCYOA"):
            results["cyoa"].append({
                "file": str(post_file),
                "releaseDir": result.get("releaseDir"),
                "redditUrl": result.get("redditUrl"),
                "cyoaDetection": result.get("cyoaDetection"),
            })

    def _maybe_delay_between_posts(
        self, result: dict, index: int, total: int
    ) -> None:
        """Add delay between posts if needed."""
        if index < total - 1 and not result.get("skipped") and not self.dry_run:
            print("\n  Waiting 3 seconds before next post...")
            time.sleep(3)

    def _handle_critical_error(
        self, error: Exception, post_file: Path, results: dict
    ) -> None:
        """Handle critical errors that should abort the batch."""
        if isinstance(error, StashScanStuckError):
            error_type = "Stashapp scan is stuck"
            recovery_msg = "Please check Stashapp and restart the scan manually."
        else:
            error_type = "Disk space exhausted"
            recovery_msg = "Please free up disk space and re-run this script."

        print(f"\n{'!' * 60}")
        print(f"  ABORTING BATCH: {error_type}!")
        print(f"  {error}")
        print(f"{'!' * 60}")
        print(f"\n{recovery_msg}")
        print("Then re-run this script to continue processing.\n")

        results["failed"].append({
            "file": str(post_file),
            "error": str(error),
            "aborted": True,
        })
        results["aborted"] = True
        results["abort_reason"] = str(error)

    def _print_batch_summary(self, results: dict) -> None:
        """Print the batch processing summary."""
        print(f"\n{'=' * 60}")
        print("  Batch Processing Summary")
        print(f"{'=' * 60}")

        self._print_summary_stats(results)
        self._print_failed_posts(results)
        self._print_unavailable_platforms(results)
        self._print_script_offers(results)
        self._print_cyoa_warnings(results)
        self._print_platform_status()

    def _print_summary_stats(self, results: dict) -> None:
        """Print summary statistics."""
        if results.get("aborted"):
            print(f"  STATUS: ABORTED ({results.get('abort_reason', 'Unknown')})")
        print(f"  Processed: {len(results['processed'])}")
        print(f"  Skipped: {len(results['skipped'])}")

        if results["skipped"]:
            already_done = (
                len(results["skipped"])
                - len(results["scriptOffers"])
                - len(results["requestPosts"])
                - len(results["otherPosts"])
                - len(results["noAudioUrls"])
                - len(results["skippedUnavailablePlatforms"])
            )
            if already_done > 0:
                print(f"     Already processed: {already_done}")
            if results["skippedUnavailablePlatforms"]:
                print(f"     Unavailable platforms: {len(results['skippedUnavailablePlatforms'])}")
            if results["scriptOffers"]:
                print(f"     Script offers: {len(results['scriptOffers'])}")
            if results["requestPosts"]:
                print(f"     Request posts: {len(results['requestPosts'])}")
            if results["otherPosts"]:
                print(f"     Other posts: {len(results['otherPosts'])}")
            if results["noAudioUrls"]:
                print(f"     No audio URLs: {len(results['noAudioUrls'])}")

        print(f"  Failed: {len(results['failed'])}")

    def _print_failed_posts(self, results: dict) -> None:
        """Print failed posts section."""
        if results["failed"]:
            print("\nFailed posts:")
            for fail in results["failed"]:
                print(f"  - {Path(fail['file']).name}: {fail.get('error') or fail.get('stage')}")

    def _print_unavailable_platforms(self, results: dict) -> None:
        """Print unavailable platforms section."""
        if not results["skippedUnavailablePlatforms"]:
            return

        print(f"\n{'-' * 60}")
        print(f"  Skipped (Unavailable Platforms): {len(results['skippedUnavailablePlatforms'])} posts")
        print("  (Re-run when platforms are back online)")

        for skip in results["skippedUnavailablePlatforms"][:10]:
            platforms_str = ", ".join(skip.get("platforms", []))
            print(f"    - {Path(skip['file']).name} [{platforms_str}]")

        if len(results["skippedUnavailablePlatforms"]) > 10:
            remaining = len(results["skippedUnavailablePlatforms"]) - 10
            print(f"    ... and {remaining} more")

    def _print_script_offers(self, results: dict) -> None:
        """Print script offers section."""
        if results["scriptOffers"]:
            print(f"\n{'-' * 60}")
            print(f"  Script Offers ({len(results['scriptOffers'])} posts):")
            for so in results["scriptOffers"]:
                print(f"  - {Path(so['file']).name}")

    def _print_cyoa_warnings(self, results: dict) -> None:
        """Print CYOA warnings section."""
        if not results["cyoa"]:
            return

        print(f"\n{'=' * 60}")
        print(f"  CYOA Releases Requiring Manual Handling: {len(results['cyoa'])}")
        print(f"{'=' * 60}")
        print("These releases have decision tree structures that require manual")
        print("mapping in Stashapp release descriptions as links.\n")

        for cyoa in results["cyoa"]:
            detection = cyoa.get("cyoaDetection") or {}
            print(f"    {Path(cyoa['file']).name}")
            if cyoa.get("redditUrl"):
                print(f"     Reddit: {cyoa['redditUrl']}")
            if detection.get("audio_count"):
                endings = detection.get("endings_count")
                endings_str = f", Endings: {endings}" if endings else ""
                print(f"     Audios: {detection['audio_count']}{endings_str}")
            if detection.get("decision_tree_url"):
                print(f"     Flowchart: {detection['decision_tree_url']}")
            if detection.get("reason"):
                print(f"     Reason: {detection['reason']}")
            print()

    def _print_platform_status(self) -> None:
        """Print final platform status summary."""
        platform_summary = self.availability_tracker.get_summary()
        unavailable = [
            p for p, s in platform_summary.items()
            if "unavailable" in s or "skipped" in s
        ]
        if unavailable:
            print(f"\n{'-' * 60}")
            print("  Platform Status:")
            for platform, status in sorted(platform_summary.items()):
                print(f"    {platform}: {status}")

    def find_reddit_posts(self, directory: Path) -> list[Path]:
        """Find all JSON files in a directory (Reddit posts)."""
        posts: list[Path] = []

        def search_directory(dir_path: Path) -> None:
            if not dir_path.exists():
                return

            for entry in dir_path.iterdir():
                if entry.is_dir():
                    search_directory(entry)
                elif (
                    entry.is_file()
                    and entry.suffix == ".json"
                    and "_enriched" not in entry.name
                ):
                    # Check if it looks like a Reddit post
                    try:
                        data = json.loads(entry.read_text(encoding="utf-8"))
                        if (
                            data.get("reddit_data")
                            and data["reddit_data"].get("selftext") is not None
                        ):
                            posts.append(entry)
                    except (json.JSONDecodeError, FileNotFoundError):
                        pass

        search_directory(directory)
        return posts

    def show_status(self) -> None:
        """Show processing status."""
        processed = self.load_processed_posts()

        posts = processed.get("posts", {})
        total = len(posts)
        successful = sum(1 for p in posts.values() if p.get("success"))
        failed = sum(1 for p in posts.values() if not p.get("success"))

        print("  Processing Status")
        print(f"{'=' * 40}")
        print(f"Total processed: {total}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"Last updated: {processed.get('lastUpdated') or 'Never'}")

        if failed > 0:
            print("\nFailed posts:")
            for post_id, info in posts.items():
                if not info.get("success"):
                    print(f"  - {post_id}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze, Download, and Import Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Complete workflow that analyzes Reddit posts, downloads audio, and imports to Stashapp.

Examples:
  # Process single Reddit post
  uv run python analyze_download_import.py aural_data/index/reddit/SweetnEvil86/1bdg16n_post.json

  # Process all posts in directory
  uv run python analyze_download_import.py aural_data/index/reddit/SweetnEvil86/

  # Dry run to see what would be processed
  uv run python analyze_download_import.py aural_data/index/reddit/SweetnEvil86/ --dry-run

  # Re-process a specific post (ignore tracking)
  uv run python analyze_download_import.py aural_data/index/reddit/SweetnEvil86/1bdg16n_post.json --force

  # Process without importing to Stashapp
  uv run python analyze_download_import.py aural_data/index/reddit/SweetnEvil86/ --skip-import

  # Show current processing status
  uv run python analyze_download_import.py --status

  # Re-extract only the script for an existing release
  uv run python analyze_download_import.py data/releases/performer/release_dir --script-only
""",
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        help="Reddit post JSON file or directory containing posts",
    )
    parser.add_argument(
        "--analysis-dir",
        default=str(aural_config.ANALYSIS_DIR),
        help=f"Directory for analysis results (default: {aural_config.ANALYSIS_DIR})",
    )
    parser.add_argument(
        "--data-dir",
        default=str(aural_config.RELEASES_DIR.parent),
        help=f"Directory for all data (default: {aural_config.RELEASES_DIR.parent})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually processing",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress information",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip analysis if already exists",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Skip Stashapp import step",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process even if already done",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show processing status and exit",
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="Re-extract only the script for an existing release (use with release directory path)",
    )
    parser.add_argument(
        "--skip-audio-platform",
        action="append",
        dest="skip_platforms",
        default=[],
        metavar="PLATFORM",
        help="Skip specified audio platform (can be used multiple times). "
        "Valid platforms: soundgasm, whypit, hotaudio, audiochan",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip platform health checks at batch start",
    )

    args = parser.parse_args()

    options = {
        "analysis_dir": args.analysis_dir,
        "data_dir": args.data_dir,
        "dry_run": args.dry_run,
        "verbose": args.verbose,
        "skip_analysis": args.skip_analysis,
        "skip_import": args.skip_import,
        "force": args.force,
        "script_only": args.script_only,
        "skip_platforms": args.skip_platforms,
        "skip_health_check": args.skip_health_check,
    }

    try:
        pipeline = AnalyzeDownloadImportPipeline(options)

        # Show status
        if args.status:
            pipeline.show_status()
            return 0

        # Script-only mode
        if args.script_only:
            if not args.input_path:
                print("  Please provide a release directory path")
                return 1
            result = pipeline.reextract_script(Path(args.input_path))
            return 0 if result.get("success") else 1

        if not args.input_path:
            print("  Please provide a Reddit post file or directory")
            parser.print_help()
            return 1

        input_path = Path(args.input_path)

        if not input_path.exists():
            print(f"  Error: Path not found: {input_path}")
            return 1

        if input_path.is_file():
            result = pipeline.process_post(input_path)
            return 0 if result.get("success") else 1

        if input_path.is_dir():
            print(f"  Searching for Reddit posts in: {input_path}")
            post_files = pipeline.find_reddit_posts(input_path)

            if not post_files:
                print("  No Reddit post files found in directory")
                return 1

            print(f"  Found {len(post_files)} Reddit post files")
            results = pipeline.process_batch(post_files)
            return 0 if len(results["failed"]) == 0 else 1

        print("  Input path must be a file or directory")
        return 1

    except Exception as e:
        print(f"  Pipeline error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
