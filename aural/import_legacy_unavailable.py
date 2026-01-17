#!/usr/bin/env python3
"""
Import Legacy Unavailable Audio Files to Stashapp

Imports legacy audio files (MP4s with JSON sidecars) where the original
Reddit content has been deleted/removed. Uses sidecar metadata for:
- Title
- URL (converted from old.reddit.com to www.reddit.com)
- Performer (from author field)
- Tags (matched against existing Stashapp tags)
- "Missing or Removed" tag added to all imports

Usage:
    uv run python import_legacy_unavailable.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/"
    uv run python import_legacy_unavailable.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --dry-run
    uv run python import_legacy_unavailable.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --limit 5
"""

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

from config import REDDIT_INDEX_DIR
from stashapp_importer import StashappClient, match_tags_with_stash


STASH_LIBRARY_PATH = Path("/Volumes/Culture 1/Aural_Stash")


def find_scene_by_filename(client: StashappClient, filename: str) -> dict | None:
    """Find a scene by its filename (basename)."""
    # Wrap in double quotes for exact phrase match in Stashapp
    search_term = f'"{filename}"'

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
            "scene_filter": {"path": {"value": search_term, "modifier": "INCLUDES"}},
            "filter": {"per_page": 10},
        },
    )
    scenes = result.get("findScenes", {}).get("scenes", [])
    # Match exact basename
    for scene in scenes:
        for f in scene.get("files", []):
            if f.get("basename") == filename:
                return scene
    return None


MISSING_TAG_NAME = "Missing or Removed"


def normalize_reddit_url(url: str) -> str:
    """Convert old.reddit.com URL to www.reddit.com format."""
    if not url:
        return url
    url = url.replace("old.reddit.com", "www.reddit.com")
    url = url.rstrip(")/")
    return url


def extract_post_id_from_url(url: str) -> str | None:
    """Extract post ID from Reddit URL."""
    match = re.search(r"/comments/([a-z0-9]+)", url, re.IGNORECASE)
    return match.group(1) if match else None


def is_content_unavailable(post_id: str, reddit_dir: Path) -> bool:
    """Check if Reddit content for this post is unavailable."""
    # Search for post in aural_data/index/reddit
    for author_dir in reddit_dir.iterdir():
        if not author_dir.is_dir():
            continue
        for json_file in author_dir.glob(f"{post_id}_*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                selftext = data.get("reddit_data", {}).get("selftext", "")
                return selftext in ("[removed]", "[deleted]")
            except (json.JSONDecodeError, FileNotFoundError):
                continue
    return True  # If not found, assume unavailable


def find_legacy_sidecars(directory: Path, reddit_dir: Path) -> list[tuple[Path, Path]]:
    """Find JSON sidecars with MP4s where Reddit content is unavailable."""
    results = []

    for json_file in sorted(directory.glob("*.json")):
        mp4_file = json_file.with_suffix(".mp4")
        if not mp4_file.exists():
            continue

        try:
            sidecar = json.loads(json_file.read_text(encoding="utf-8"))
            urls = sidecar.get("urls", [])

            # Find Reddit URL
            reddit_url = None
            for url in urls:
                if "reddit.com" in url:
                    reddit_url = url
                    break

            if not reddit_url:
                continue

            post_id = extract_post_id_from_url(reddit_url)
            if not post_id:
                continue

            # Check if content is unavailable
            if is_content_unavailable(post_id, reddit_dir):
                results.append((json_file, mp4_file))

        except (json.JSONDecodeError, FileNotFoundError):
            continue

    return results


def import_legacy_file(
    json_path: Path,
    mp4_path: Path,
    client: StashappClient,
    missing_tag_id: str,
    dry_run: bool = False,
) -> dict:
    """Import a single legacy file to Stashapp."""
    sidecar = json.loads(json_path.read_text(encoding="utf-8"))

    # Extract metadata
    title = sidecar.get("title", mp4_path.stem)
    author = sidecar.get("author", "Unknown")
    tags = sidecar.get("tags", [])

    # Get Reddit URL
    reddit_url = None
    for url in sidecar.get("urls", []):
        if "reddit.com" in url:
            reddit_url = normalize_reddit_url(url)
            break

    if dry_run:
        print(f"  [DRY RUN] Would import: {mp4_path.name}")
        print(f"    Title: {title}")
        print(f"    Performer: {author}")
        print(f"    URL: {reddit_url}")
        print(f"    Tags: {len(tags)}")
        return {"success": True, "dryRun": True}

    # 1. Copy MP4 to Stashapp library
    dest_path = STASH_LIBRARY_PATH / mp4_path.name
    if dest_path.exists():
        print(f"  File already exists in library: {dest_path.name}")
        # Try to find existing scene
        scene = find_scene_by_filename(client, dest_path.name)
        if scene:
            print(f"  Scene already exists: {scene['id']}")
            return {"success": True, "sceneId": scene["id"], "alreadyExists": True}
    else:
        shutil.copy2(mp4_path, dest_path)
        print(f"  Copied to library: {dest_path.name}")

    # 2. Trigger scan and wait
    client.trigger_scan()
    if not client.wait_for_scan(timeout=60):
        print("  Warning: Scan timeout, continuing anyway...")

    # 3. Find scene by filename (with retry)
    scene = None
    for attempt in range(10):
        scene = find_scene_by_filename(client, dest_path.name)
        if scene:
            break
        time.sleep(1)

    if not scene:
        return {"success": False, "error": "Scene not found after scan"}

    scene_id = scene["id"]

    # 4. Find or create performer
    performer = client.find_or_create_performer(author, gender="FEMALE")
    performer_ids = [performer["id"]] if performer else []

    # 5. Match tags (only existing tags in Stashapp, no creation)
    tag_ids = [missing_tag_id]  # Always include "Missing or Removed"
    all_stash_tags = client.get_all_tags()
    matched_tag_ids = match_tags_with_stash(tags, all_stash_tags)
    tag_ids.extend(matched_tag_ids)

    # 6. Update scene
    updates = {
        "title": title,
        "performer_ids": performer_ids,
        "tag_ids": list(set(tag_ids)),  # Dedupe
    }
    if reddit_url:
        updates["urls"] = [reddit_url]

    client.update_scene(scene_id, updates)
    print(f"  Updated scene: {scene_id}")

    # 7. Delete legacy files
    json_path.unlink()
    mp4_path.unlink()
    print("  Deleted legacy files")

    return {"success": True, "sceneId": scene_id}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import legacy unavailable audio files to Stashapp"
    )
    parser.add_argument("directory", help="Path to legacy GWA directory")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    parser.add_argument("--limit", type=int, help="Max files to process")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    directory = Path(args.directory)
    reddit_dir = REDDIT_INDEX_DIR

    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1

    # Find files to import
    sidecars = find_legacy_sidecars(directory, reddit_dir)
    print(f"Found {len(sidecars)} legacy files with unavailable Reddit content")

    if args.limit:
        sidecars = sidecars[: args.limit]

    if not sidecars:
        return 0

    # Initialize client
    client = StashappClient()

    # Find "Missing or Removed" tag (must exist in Stashapp)
    missing_tag = client.find_tag(MISSING_TAG_NAME)
    if not missing_tag:
        print(f"Error: Tag '{MISSING_TAG_NAME}' not found in Stashapp")
        return 1
    missing_tag_id = missing_tag["id"]

    # Process files
    results = {"success": 0, "failed": 0}

    for i, (json_path, mp4_path) in enumerate(sidecars):
        print(f"\n[{i + 1}/{len(sidecars)}] {json_path.name}")

        try:
            result = import_legacy_file(
                json_path, mp4_path, client, missing_tag_id, args.dry_run
            )
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
                print(f"  Error: {result.get('error')}")
        except Exception as e:
            results["failed"] += 1
            print(f"  Error: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Imported: {results['success']}")
    print(f"Failed: {results['failed']}")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
