#!/usr/bin/env python3
"""
Pornhub Metadata Importer - Update Stashapp scenes with yt-dlp metadata

This script reads .info.json files from yt-dlp downloads and updates
the corresponding scenes in Stashapp with metadata (title, date, tags, etc.)

Usage:
    uv run python pornhub_metadata_importer.py --dry-run  # Preview changes
    uv run python pornhub_metadata_importer.py            # Apply changes
"""

import argparse
import json
import re
from pathlib import Path

from stashapp_importer import (
    STASH_OUTPUT_DIR,
    StashappClient,
    match_tags_with_stash,
)


def parse_info_json(path: Path) -> dict:
    """Parse a yt-dlp .info.json file."""
    return json.loads(path.read_text(encoding="utf-8"))


def extract_video_id_from_filename(filename: str) -> str | None:
    """Extract Pornhub video ID from filename pattern.

    Pattern: Pornhub - {uploader} - {date} - {video_id} - {title}.info.json
    """
    match = re.search(r"Pornhub - .+ - \d{4}-\d{2}-\d{2} - ([a-f0-9]+) -", filename)
    if match:
        return match.group(1)
    return None


def find_scene_by_video_id(client: StashappClient, video_id: str) -> dict | None:
    """Find a scene by Pornhub video ID in the file path.

    Returns the scene if exactly one match found, None otherwise.
    """
    query = """
        query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
            findScenes(scene_filter: $scene_filter, filter: $filter) {
                scenes { id title files { path basename } }
            }
        }
    """
    result = client.query(
        query,
        {
            "scene_filter": {
                "path": {"value": video_id, "modifier": "INCLUDES"}
            },
            "filter": {"per_page": 10},
        },
    )
    scenes = result.get("findScenes", {}).get("scenes", [])

    if len(scenes) == 0:
        print(f"  Warning: No scene found for video ID {video_id}")
        return None
    elif len(scenes) > 1:
        scene_ids = [s["id"] for s in scenes]
        print(f"  Error: Multiple scenes found for video ID {video_id}: {scene_ids}")
        return None

    return scenes[0]


def format_date(upload_date: str) -> str:
    """Convert yt-dlp date (YYYYMMDD) to Stashapp format (YYYY-MM-DD)."""
    if len(upload_date) == 8:
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return upload_date


def format_tags_as_description(tags: list[str], categories: list[str]) -> str:
    """Format tags and categories as Reddit-style bracketed description.

    Example output: [Creampie] [Blowjob] [Big Tits] [Romantic]
    """
    all_tags = []

    # Add categories first (typically more general)
    for cat in categories or []:
        # Title case each word
        formatted = cat.title()
        all_tags.append(f"[{formatted}]")

    # Add tags
    for tag in tags or []:
        # Title case each word
        formatted = tag.title()
        all_tags.append(f"[{formatted}]")

    return " ".join(all_tags)


def process_info_file(
    client: StashappClient,
    info_path: Path,
    stash_tags: list[dict],
    dry_run: bool = False,
) -> dict:
    """Process a single .info.json file and update the corresponding scene.

    Returns a result dict with status and details.
    """
    filename = info_path.name
    print(f"\nProcessing: {filename}")

    # Parse metadata
    metadata = parse_info_json(info_path)

    # Get video ID from metadata or filename
    video_id = metadata.get("id") or extract_video_id_from_filename(filename)
    if not video_id:
        print("  Error: Could not extract video ID")
        return {"status": "error", "reason": "no_video_id"}

    print(f"  Video ID: {video_id}")

    # Find scene in Stashapp
    scene = find_scene_by_video_id(client, video_id)
    if not scene:
        return {"status": "skipped", "reason": "scene_not_found"}

    print(f"  Found scene ID: {scene['id']} - {scene.get('title', 'Untitled')}")

    # Prepare updates
    updates: dict = {}

    # Title
    if metadata.get("title"):
        updates["title"] = metadata["title"]

    # Date
    if metadata.get("upload_date"):
        updates["date"] = format_date(metadata["upload_date"])

    # URLs
    if metadata.get("webpage_url"):
        updates["urls"] = [metadata["webpage_url"]]

    # Details (tags formatted Reddit-style)
    tags_description = format_tags_as_description(
        metadata.get("tags", []),
        metadata.get("categories", []),
    )
    if tags_description:
        updates["details"] = tags_description

    # Performer
    uploader = metadata.get("uploader")
    if uploader:
        if dry_run:
            print(f"  Would find/create performer: {uploader}")
        else:
            performer = client.find_or_create_performer(
                uploader,
                gender="FEMALE",  # alekirser is female
            )
            updates["performer_ids"] = [performer["id"]]

    # Studio (same as performer for solo creators)
    if uploader:
        if dry_run:
            print(f"  Would find/create studio: {uploader}")
        else:
            studio = client.find_or_create_studio(uploader)
            updates["studio_id"] = studio["id"]

    # Tags - combine tags and categories from yt-dlp
    all_tags = []
    if metadata.get("tags"):
        all_tags.extend(metadata["tags"])
    if metadata.get("categories"):
        all_tags.extend(metadata["categories"])

    if all_tags and stash_tags:
        matched_tag_ids = match_tags_with_stash(all_tags, stash_tags)
        if matched_tag_ids:
            updates["tag_ids"] = matched_tag_ids
            if dry_run:
                print(f"  Would match {len(matched_tag_ids)} tags")

    # Show what would be updated
    if dry_run:
        print(f"  Would update scene {scene['id']} with:")
        for key, value in updates.items():
            if key in ("performer_ids", "tag_ids"):
                print(f"    {key}: {len(value)} items")
            elif key == "urls":
                print(f"    {key}: {value}")
            else:
                display_value = value[:60] + "..." if len(str(value)) > 60 else value
                print(f"    {key}: {display_value}")
        return {"status": "dry_run", "scene_id": scene["id"], "updates": updates}

    # Apply updates
    print(f"  Updating scene {scene['id']}...")
    client.update_scene(scene["id"], updates)
    print("  Scene updated successfully!")

    return {"status": "updated", "scene_id": scene["id"]}


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Update Stashapp scenes with Pornhub yt-dlp metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--performer",
        default="alekirser",
        help="Performer name to filter files (default: alekirser)",
    )

    args = parser.parse_args()

    # Check output directory
    if not STASH_OUTPUT_DIR.exists():
        print(f"Error: Stash output directory not found: {STASH_OUTPUT_DIR}")
        return 1

    # Find all matching .info.json files
    pattern = f"Pornhub - {args.performer} - *.info.json"
    info_files = sorted(STASH_OUTPUT_DIR.glob(pattern))

    if not info_files:
        print(f"No .info.json files found matching pattern: {pattern}")
        return 1

    print(f"Found {len(info_files)} .info.json files for {args.performer}")

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    # Initialize Stashapp client
    client = StashappClient()
    version = client.get_version()
    print(f"Connected to Stashapp {version}")

    # Get all tags for matching
    print("Fetching Stashapp tags...")
    stash_tags = client.get_all_tags()
    print(f"Found {len(stash_tags)} tags")

    # Process each file
    stats = {"updated": 0, "skipped": 0, "error": 0, "dry_run": 0}

    for info_path in info_files:
        result = process_info_file(client, info_path, stash_tags, args.dry_run)
        stats[result["status"]] = stats.get(result["status"], 0) + 1

    # Summary
    print(f"\n{'=' * 60}")
    print("Summary:")
    if args.dry_run:
        print(f"  Would update: {stats.get('dry_run', 0)}")
    else:
        print(f"  Updated: {stats.get('updated', 0)}")
    print(f"  Skipped: {stats.get('skipped', 0)}")
    print(f"  Errors: {stats.get('error', 0)}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
