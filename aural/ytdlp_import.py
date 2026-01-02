#!/usr/bin/env python3
"""
yt-dlp Import - Download and import videos directly to Stashapp.

This script downloads video content using yt-dlp and imports it into Stashapp
with metadata extracted from the source platform (Pornhub, YouTube, etc.).

Usage:
    uv run python ytdlp_import.py <url>
"""

import argparse
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from stashapp_importer import (
    STASH_BASE_URL,
    STASH_OUTPUT_DIR,
    StashappClient,
    match_tags_with_stash,
)
from ytdlp_extractor import YtDlpExtractor


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
                output_dir=str(Path.cwd() / "ytdlp_data"), use_cache=True
            )
        return self._extractor

    def is_cached(self, url: str) -> bool:
        """Check if URL is already in the yt-dlp cache."""
        cache_path = self.extractor._get_cache_path(url)
        return cache_path.exists()

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

    def process_url(self, url: str) -> dict:
        """Download video and import to Stashapp."""
        print(f"\n{'=' * 60}")
        print(f"Processing: {url}")
        print("=" * 60)

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
            print(f"  Moving to: {output_path}")
            shutil.move(str(source_path), str(output_path))
            # Also move the .info.json if it exists
            info_json = source_path.with_suffix(".info.json")
            if info_json.exists():
                shutil.move(str(info_json), str(output_path.with_suffix(".info.json")))

        # Step 3: Trigger Stashapp scan
        print("\nStep 3: Triggering Stashapp scan...")
        job_id = self.stash_client.trigger_scan()
        print(f"  Scan job started: {job_id}")

        print("  Waiting for scan to complete...")
        self.stash_client.wait_for_scan(60)

        # Step 4: Find the scene
        print("\nStep 4: Finding scene in Stashapp...")
        scene = None
        max_retries = 10
        retry_delay = 2

        for retry in range(max_retries):
            scene = self.stash_client.find_scene_by_basename(output_filename)
            if scene:
                break
            if retry < max_retries - 1:
                print(
                    f"  Scene not found yet, retrying in {retry_delay}s... "
                    f"({retry + 1}/{max_retries})"
                )
                time.sleep(retry_delay)

        if not scene:
            return {
                "success": False,
                "error": "Scene not found after scan. May need manual refresh.",
            }

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

        # Performer
        print("\n  Processing performer...")
        performer_name = metadata.get("author")
        if performer_name:
            thumbnail = platform_data.get("thumbnail")
            performer = self.stash_client.find_or_create_performer(
                performer_name, image_url=thumbnail
            )
            updates["performer_ids"] = [performer["id"]]

            print("\n  Processing studio...")
            studio = self.stash_client.find_or_create_studio(performer_name)
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

        return {
            "success": True,
            "sceneId": scene["id"],
            "sceneUrl": f"{STASH_BASE_URL}/scenes/{scene['id']}",
            "videoFile": str(output_path),
        }

    def process_channel(self, url: str, limit: int | None = None) -> dict:
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

            if self.is_cached(video_url):
                print(f"  ✓ {title} - cached")
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

        for video_url in new_videos:
            try:
                result = self.process_url(video_url)
                if result["success"]:
                    imported += 1
                else:
                    failed += 1
                    print(f"  Failed: {result.get('error')}")
            except Exception as e:
                failed += 1
                print(f"  Error: {e}")

        return {
            "success": True,
            "imported": imported,
            "skipped": cached_count,
            "failed": failed,
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
        result = importer.process_channel(args.url, limit=args.limit)

        print(f"\n{'=' * 60}")
        if result.get("imported", 0) == 1 and result.get("skipped", 0) == 0:
            print("Import completed successfully!")
        else:
            print("Import completed!")
            print(f"  Imported: {result.get('imported', 0)}")
            print(f"  Skipped (cached): {result.get('skipped', 0)}")
        if result.get("failed"):
            print(f"  Failed: {result.get('failed')}")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
