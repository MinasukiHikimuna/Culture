#!/usr/bin/env python3
"""
yt-dlp Import - Download and import videos directly to Stashapp.

This script downloads video content using yt-dlp and imports it into Stashapp
with metadata extracted from the source platform (Pornhub, YouTube, etc.).

Usage:
    uv run python ytdlp_import.py <url>
"""

import argparse
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import config as aural_config
import oshash
from config import PROCESSED_URLS_FILE
from stashapp_importer import (
    STASH_BASE_URL,
    STASH_OUTPUT_DIR,
    StashappClient,
    StashScanStuckError,
    match_tags_with_stash,
)
from ytdlp_extractor import YtDlpExtractor
import sys


class YtDlpImporter:
    """Download via yt-dlp and import directly to Stashapp."""

    def __init__(
        self,
        output_dir: Path | None = None,
        verbose: bool = False,
    ):
        self.output_dir = output_dir or STASH_OUTPUT_DIR
        self.verbose = verbose
        self._stash_client: StashappClient | None = None
        self._extractor: YtDlpExtractor | None = None
        self._processed_urls: dict | None = None

    @property
    def stash_client(self) -> StashappClient:
        """Lazy-load Stashapp client."""
        if self._stash_client is None:
            self._stash_client = StashappClient()
        return self._stash_client

    @property
    def extractor(self) -> YtDlpExtractor:
        """Lazy-load yt-dlp extractor."""
        if self._extractor is None:
            self._extractor = YtDlpExtractor(
                output_dir=str(aural_config.YTDLP_DIR), use_cache=True
            )
        return self._extractor

    def is_imported(self, url: str) -> bool:
        """Check if URL is already imported to Stashapp."""
        query = """
            query FindScenes($scene_filter: SceneFilterType!) {
                findScenes(scene_filter: $scene_filter) {
                    count
                }
            }
        """
        result = self.stash_client.query(
            query,
            {"scene_filter": {"url": {"value": url, "modifier": "INCLUDES"}}},
        )
        count = result.get("findScenes", {}).get("count", 0)
        return count > 0

    def load_processed_urls(self) -> dict:
        """Load processed URLs tracking data."""
        if self._processed_urls is not None:
            return self._processed_urls

        try:
            self._processed_urls = json.loads(
                PROCESSED_URLS_FILE.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError):
            self._processed_urls = {"urls": {}, "lastUpdated": None}

        return self._processed_urls

    def save_processed_urls(self) -> None:
        """Save processed URLs tracking data."""
        if self._processed_urls is None:
            return

        self._processed_urls["lastUpdated"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        PROCESSED_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROCESSED_URLS_FILE.write_text(
            json.dumps(self._processed_urls, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def is_url_processed(self, url: str) -> bool:
        """Check if URL has already been successfully processed."""
        processed = self.load_processed_urls()
        record = processed.get("urls", {}).get(url)
        if not record:
            return False
        return record.get("success") is True and record.get("sceneId") is not None

    def mark_url_processed(self, url: str, result: dict) -> None:
        """Mark a URL as successfully processed."""
        processed = self.load_processed_urls()
        processed["urls"][url] = {
            "processedAt": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "sceneId": result.get("sceneId"),
            "videoFile": result.get("videoFile"),
            "success": result.get("success", False),
        }
        self.save_processed_urls()

    def test_connection(self) -> str:
        """Test Stashapp connection."""
        print("Testing Stashapp connection...")
        version = self.stash_client.get_version()
        print(f"Connected to Stashapp {version}")
        return version

    def format_output_filename(self, result: dict) -> str:
        """Generate output filename in Stashapp format."""
        metadata = result.get("metadata", {})
        platform_data = result.get("platformData", {})
        author = metadata.get("author", "Unknown")

        # Parse date
        upload_date = platform_data.get("upload_date")  # Format: YYYYMMDD
        if upload_date and len(upload_date) == 8:
            date_str = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        else:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Get video ID
        video_id = platform_data.get("id", "unknown")

        # Clean title
        title = metadata.get("title") or "Unknown"
        clean_title = re.sub(r"[^\w\s\-\.\,\!\?\'\"\u0080-\uFFFF]", "", title).strip()
        if len(clean_title) > 100:
            clean_title = clean_title[:100].rsplit(" ", 1)[0]
        clean_title = re.sub(r'[<>:"/\\|?*]', "", clean_title)

        return f"{author} - {date_str} - {video_id} - {clean_title}.mp4"

    def process_url(self, url: str, force: bool = False) -> dict:
        """Download video and import to Stashapp."""
        print(f"\n{'=' * 60}")
        print(f"Processing: {url}")
        print("=" * 60)

        # Check if already processed (unless force flag)
        if not force and self.is_url_processed(url):
            tracked = self.load_processed_urls().get("urls", {}).get(url, {})
            print("  Already processed (tracked)")
            if tracked.get("sceneId"):
                print(f"  Scene: {STASH_BASE_URL}/scenes/{tracked['sceneId']}")
            return {
                "success": True,
                "skipped": True,
                "sceneId": tracked.get("sceneId"),
            }

        # Step 1: Download
        print("\nStep 1: Downloading video...")
        result = self.extractor.download(url)

        metadata = result.get("metadata", {})
        video_info = result.get("video", {})
        platform_data = result.get("platformData", {})

        print(f"  Title: {metadata.get('title')}")
        print(f"  Author: {metadata.get('author')}")
        print(f"  Duration: {metadata.get('duration')}s")

        # Step 2: Move file to Stash output directory
        print("\nStep 2: Moving to Stash directory...")

        source_path = Path(video_info.get("filePath", ""))
        if not source_path.exists():
            return {"success": False, "error": f"Video file not found: {source_path}"}

        output_filename = self.format_output_filename(result)
        output_path = self.output_dir / output_filename

        if output_path.exists():
            print(f"  File already exists: {output_path}")
        else:
            print(f"  Copying to: {output_path}")
            shutil.copy2(str(source_path), str(output_path))

        # Clean up source video file after successful copy/verification
        if output_path.exists() and source_path.exists():
            source_path.unlink()
            print(f"  Cleaned up source: {source_path.name}")

        # Step 3: Trigger Stashapp scan
        print("\nStep 3: Triggering Stashapp scan...")
        job_id = self.stash_client.trigger_scan()
        print(f"  Scan job started: {job_id}")

        print("  Waiting for scan to complete...")
        scan_completed = self.stash_client.wait_for_scan(60)

        if not scan_completed:
            raise StashScanStuckError(
                f"Stashapp scan job {job_id} did not complete within 60 seconds. "
                "The scan may be stuck. Please check Stashapp and restart if needed."
            )

        # Step 4: Find the scene by oshash
        print("\nStep 4: Finding scene in Stashapp...")
        file_oshash = oshash.oshash(str(output_path))
        scene = None
        max_retries = 10
        retry_delay = 2

        for retry in range(max_retries):
            scene = self.stash_client.find_scene_by_oshash(file_oshash)
            if scene:
                break
            if retry < max_retries - 1:
                print(
                    f"  Scene not found yet, retrying in {retry_delay}s... "
                    f"({retry + 1}/{max_retries})"
                )
                time.sleep(retry_delay)

        if not scene:
            raise StashScanStuckError(
                f"Scene not found after scan completed. oshash: {file_oshash}. "
                "Stashapp may not be scanning the expected directory, or the scan is stuck."
            )

        print(f"  Found scene ID: {scene['id']}")

        # Step 5: Update metadata
        print("\nStep 5: Updating scene metadata...")
        updates: dict = {}

        updates["title"] = metadata.get("title", "")

        upload_date = platform_data.get("upload_date")
        if upload_date and len(upload_date) == 8:
            updates["date"] = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

        source_url = video_info.get("sourceUrl")
        if source_url:
            updates["urls"] = [source_url]

        description = metadata.get("description", "")
        if description:
            updates["details"] = description[:5000]

        # Performer - try URL match first, then fall back to name
        print("\n  Processing performer...")
        performer = None
        performer_name = metadata.get("author")
        channel_url = metadata.get("platform", {}).get("url")

        # Try to find performer by channel URL first
        if channel_url:
            print(f"    Looking up by URL: {channel_url}")
            performer = self.stash_client.find_performer_by_url(channel_url)
            if performer:
                print(f"    Found by URL: {performer['name']} (ID: {performer['id']})")

        # Fall back to name-based lookup/creation
        if not performer and performer_name:
            thumbnail = platform_data.get("thumbnail")
            performer = self.stash_client.find_or_create_performer(
                performer_name, image_url=thumbnail
            )

        if performer:
            updates["performer_ids"] = [performer["id"]]

            print("\n  Processing studio...")
            studio = self.stash_client.find_or_create_studio(performer["name"])
            updates["studio_id"] = studio["id"]

        # Tags
        print("\n  Processing tags...")
        source_tags = metadata.get("tags", [])
        if source_tags:
            print(f"    Source has {len(source_tags)} tags")
            stash_tags = self.stash_client.get_all_tags()
            matched_tag_ids = match_tags_with_stash(source_tags, stash_tags)
            if matched_tag_ids:
                updates["tag_ids"] = matched_tag_ids
                print(f"    Matched {len(matched_tag_ids)} tags")

        print("\n  Updating scene...")
        self.stash_client.update_scene(scene["id"], updates)
        print("  Scene updated successfully!")

        # Generate cover image
        print("  Generating cover image...")
        self.stash_client.generate_covers()
        self.stash_client.wait_for_scan(30)
        print("  Cover generated!")

        result = {
            "success": True,
            "sceneId": scene["id"],
            "sceneUrl": f"{STASH_BASE_URL}/scenes/{scene['id']}",
            "videoFile": str(output_path),
        }

        # Track successful import
        source_url = video_info.get("sourceUrl")
        if source_url:
            self.mark_url_processed(source_url, result)

        return result

    def process_channel(self, url: str, limit: int | None = None, force: bool = False) -> dict:
        """Process all videos from a channel/playlist URL."""
        print(f"\nIndexing channel: {url}")
        entries = self.extractor.index_playlist(url, max_videos=limit)
        print(f"Found {len(entries)} videos")

        # Check duplicates
        print("\nChecking duplicates...")
        new_videos = []
        cached_count = 0

        for entry in entries:
            video_url = entry.get("video", {}).get("sourceUrl")
            title = entry.get("metadata", {}).get("title", "Unknown")[:50]

            if not video_url:
                print(f"  ? {title} - no URL found")
                continue

            # Check both Stashapp and local tracking (unless force)
            if not force and (self.is_imported(video_url) or self.is_url_processed(video_url)):
                print(f"  ✓ {title} - already imported")
                cached_count += 1
            else:
                print(f"  ○ {title} - new")
                new_videos.append(video_url)

        print(f"\n{len(new_videos)} new, {cached_count} cached")

        if not new_videos:
            return {"success": True, "imported": 0, "skipped": cached_count}

        # Process new videos
        print(f"\nProcessing {len(new_videos)} new videos...")
        imported = 0
        failed = 0
        aborted = False

        for video_url in new_videos:
            try:
                result = self.process_url(video_url, force=force)
                if result.get("skipped"):
                    cached_count += 1
                elif result["success"]:
                    imported += 1
                else:
                    failed += 1
                    print(f"  Failed: {result.get('error')}")
            except StashScanStuckError as e:
                # Stash is stuck - abort the entire batch immediately
                print(f"\n{'!' * 60}")
                print("  ABORTING BATCH: Stashapp scan is stuck!")
                print(f"  {e}")
                print(f"{'!' * 60}")
                print("\nPlease check Stashapp and restart the scan manually.")
                print("Then re-run this script to continue processing.\n")
                failed += 1
                aborted = True
                break  # Exit the batch loop immediately
            except Exception as e:
                failed += 1
                print(f"  Error: {e}")

        return {
            "success": not aborted and failed == 0,
            "imported": imported,
            "skipped": cached_count,
            "failed": failed,
            "aborted": aborted,
        }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download and import videos to Stashapp via yt-dlp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python ytdlp_import.py https://www.pornhub.com/view_video.php?viewkey=...
  uv run python ytdlp_import.py https://www.pornhub.com/model/username
  uv run python ytdlp_import.py https://www.pornhub.com/model/username --limit 5
""",
    )
    parser.add_argument("url", help="Video or channel URL to download and import")
    parser.add_argument("--limit", "-l", type=int, help="Max videos to process (for channels)")
    parser.add_argument("--force", "-f", action="store_true", help="Re-process even if already tracked")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not STASH_OUTPUT_DIR.exists():
        print(f"Error: Stash output directory not found: {STASH_OUTPUT_DIR}")
        print("Make sure the volume is mounted.")
        return 1

    try:
        importer = YtDlpImporter(verbose=args.verbose)
        importer.test_connection()

        # Always use process_channel - it handles both single videos and channels
        result = importer.process_channel(args.url, limit=args.limit, force=args.force)

        print(f"\n{'=' * 60}")
        if result.get("aborted"):
            print("Import ABORTED (Stashapp scan stuck)")
        elif result.get("imported", 0) == 1 and result.get("skipped", 0) == 0:
            print("Import completed successfully!")
        else:
            print("Import completed!")
        print(f"  Imported: {result.get('imported', 0)}")
        print(f"  Skipped (cached): {result.get('skipped', 0)}")
        if result.get("failed"):
            print(f"  Failed: {result.get('failed')}")
        print("=" * 60)
        return 1 if result.get("aborted") or result.get("failed") else 0

    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
