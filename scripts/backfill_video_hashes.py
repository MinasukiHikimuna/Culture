#!/usr/bin/env python3
"""Backfill missing video hashes for downloads that failed due to ffmpeg issue.

554 videos were downloaded without hashes because the videohashes tool couldn't
find ffmpeg/ffprobe (it searches in cwd, not PATH). This script recalculates
the hashes from the original files on disk and updates the database.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text


# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "extractors" / "scrapy"))

from cultureextractorscrapy.spiders.database import get_session


load_dotenv()

VIDEO_SEARCH_DIRS = [
    "/Volumes/Sabrent/Ripping",
    "/Volumes/Culture 1/Videos",
    "/Volumes/Culture 2/Videos",
    "/Volumes/Culture 3/Videos",
    "/Volumes/Culture 4/Videos",
    "/Volumes/Culture 5/Videos",
    "/Volumes/Culture 5/Staging",
]

VIDEOHASHES_PATH = "/Users/thardas/Code/videohashes/dist/videohashes-arm64-macos"

VIDEO_EXTENSIONS = ("mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "mpg", "mpeg", "ts")


def find_video_file(download_uuid: str) -> str | None:
    """Find video file by download UUID using fd across all volumes."""
    search_paths = []
    for d in VIDEO_SEARCH_DIRS:
        if Path(d).exists():
            search_paths.extend(["--search-path", d])

    if not search_paths:
        return None

    cmd = ["fd", "--ignore-case", str(download_uuid), *search_paths]
    for ext in VIDEO_EXTENSIONS:
        cmd.extend(["--extension", ext])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        # Return the first match
        return result.stdout.strip().split("\n")[0]
    return None


def calculate_hashes(file_path: str, ffmpeg_dir: str) -> dict | None:
    """Calculate video hashes using videohashes tool."""
    try:
        result = subprocess.run(
            [VIDEOHASHES_PATH, "-json", "-md5", file_path],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ffmpeg_dir,
            check=False,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        print(f"  ERROR: videohashes failed: {result.stdout}")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def update_metadata_with_hashes(session, download_uuid, file_metadata, hashes):
    """Update the file_metadata in the database with calculated hashes."""
    new_metadata = dict(file_metadata) if file_metadata else {}
    new_metadata["duration"] = hashes.get("duration")
    new_metadata["phash"] = hashes.get("phash")
    new_metadata["oshash"] = hashes.get("oshash")
    new_metadata["md5"] = hashes.get("md5")
    new_metadata.pop("video_hashes_error", None)

    session.execute(
        text("UPDATE downloads SET file_metadata = :metadata WHERE uuid = :uuid"),
        {"metadata": json.dumps(new_metadata), "uuid": download_uuid},
    )
    session.commit()


def main(limit: int | None = None, dry_run: bool = False):
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        print("ERROR: ffmpeg not found in PATH")
        sys.exit(1)
    ffmpeg_dir = str(Path(ffmpeg_path).parent)
    print(f"Using ffmpeg from: {ffmpeg_dir}")

    session = get_session()

    query_str = """
        SELECT d.uuid, d.saved_filename, d.file_metadata, d.release_uuid, si.name as site_name
        FROM downloads d
        JOIN releases r ON d.release_uuid = r.uuid
        JOIN sites si ON r.site_uuid = si.uuid
        WHERE d.file_type = 'video'
          AND (d.file_metadata::jsonb)->>'video_hashes_error' IS NOT NULL
        ORDER BY d.downloaded_at ASC
    """
    if limit:
        query_str += f" LIMIT {limit}"

    rows = session.execute(text(query_str)).fetchall()
    print(f"Found {len(rows)} videos missing hashes")

    success_count = 0
    error_count = 0
    not_found_count = 0

    for i, row in enumerate(rows):
        download_uuid, saved_filename, file_metadata, release_uuid, site_name = row
        display_name = saved_filename[:80] if saved_filename else "unknown"
        print(f"\n[{i + 1}/{len(rows)}] {site_name}: {display_name}")

        file_path = find_video_file(str(release_uuid))
        if not file_path:
            print("  FILE NOT FOUND on any volume")
            not_found_count += 1
            continue

        print(f"  Found: {file_path}")

        if dry_run:
            print("  DRY RUN - skipping hash calculation")
            continue

        hashes = calculate_hashes(file_path, ffmpeg_dir)
        if not hashes:
            error_count += 1
            continue

        print(f"  phash: {hashes.get('phash')}")
        print(f"  oshash: {hashes.get('oshash')}")
        print(f"  md5: {hashes.get('md5')}")

        update_metadata_with_hashes(session, download_uuid, file_metadata, hashes)
        print("  Updated database")
        success_count += 1

    print("\n=== SUMMARY ===")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Not found: {not_found_count}")

    session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill missing video hashes")
    parser.add_argument("--limit", type=int, help="Limit number of files to process")
    parser.add_argument("--dry-run", action="store_true", help="Find files but don't update database")
    args = parser.parse_args()
    main(limit=args.limit, dry_run=args.dry_run)
