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
    # Single file
    uv run python import_legacy_unavailable.py --file "/path/to/file.json"

    # Directory
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
from stashapp_importer import (
    StashappClient,
    convert_audio_to_video,
    match_tags_with_stash,
)


AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".ogg", ".flac"}


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


def get_reddit_url_from_sidecar(sidecar: dict) -> str | None:
    """Extract and normalize Reddit URL from sidecar."""
    for url in sidecar.get("urls", []):
        if "reddit.com" in url:
            return normalize_reddit_url(url)
    return None


def copy_or_convert_media(media_path: Path, dest_path: Path) -> bool:
    """Copy or convert media file to destination. Returns success."""
    is_audio = media_path.suffix.lower() in AUDIO_EXTENSIONS
    if is_audio:
        print(f"  Converting audio to video: {media_path.name} -> {dest_path.name}")
        if not convert_audio_to_video(media_path, dest_path):
            return False
        print(f"  Converted to library: {dest_path.name}")
    else:
        shutil.copy2(media_path, dest_path)
        print(f"  Copied to library: {dest_path.name}")
    return True


def wait_for_scene(client: StashappClient, filename: str) -> dict | None:
    """Trigger scan and wait for scene to appear."""
    client.trigger_scan()
    if not client.wait_for_scan(timeout=60):
        print("  Warning: Scan timeout, continuing anyway...")

    for _ in range(10):
        scene = find_scene_by_filename(client, filename)
        if scene:
            return scene
        time.sleep(1)
    return None


def import_legacy_file(
    json_path: Path,
    media_path: Path,
    client: StashappClient,
    missing_tag_id: str,
    dry_run: bool = False,
) -> dict:
    """Import a single legacy file to Stashapp."""
    sidecar = json.loads(json_path.read_text(encoding="utf-8"))
    title = sidecar.get("title", media_path.stem)
    author = sidecar.get("author", "Unknown")
    tags = sidecar.get("tags", [])
    reddit_url = get_reddit_url_from_sidecar(sidecar)

    is_audio = media_path.suffix.lower() in AUDIO_EXTENSIONS
    output_filename = media_path.with_suffix(".mp4").name if is_audio else media_path.name
    dest_path = STASH_LIBRARY_PATH / output_filename

    if dry_run:
        return print_dry_run(media_path, output_filename, is_audio, title, author, reddit_url, tags)

    # Check for existing scene
    if dest_path.exists():
        print(f"  File already exists in library: {dest_path.name}")
        scene = find_scene_by_filename(client, dest_path.name)
        if scene:
            print(f"  Scene already exists: {scene['id']}")
            return {"success": True, "sceneId": scene["id"], "alreadyExists": True}

    # Copy or convert media
    if not copy_or_convert_media(media_path, dest_path):
        return {"success": False, "error": "Audio to video conversion failed"}

    # Wait for scene to appear in Stashapp
    scene = wait_for_scene(client, dest_path.name)
    if not scene:
        return {"success": False, "error": "Scene not found after scan"}

    # Update scene metadata
    scene_id = scene["id"]
    performer = client.find_or_create_performer(author, gender="FEMALE")
    performer_ids = [performer["id"]] if performer else []

    all_stash_tags = client.get_all_tags()
    matched_tag_ids = match_tags_with_stash(tags, all_stash_tags)
    tag_ids = list({missing_tag_id, *matched_tag_ids})

    updates = {"title": title, "performer_ids": performer_ids, "tag_ids": tag_ids}
    if reddit_url:
        updates["urls"] = [reddit_url]

    client.update_scene(scene_id, updates)
    print(f"  Updated scene: {scene_id}")

    # Clean up legacy files
    json_path.unlink()
    media_path.unlink()
    print("  Deleted legacy files")

    return {"success": True, "sceneId": scene_id}


def print_dry_run(
    media_path: Path,
    output_filename: str,
    is_audio: bool,
    title: str,
    author: str,
    reddit_url: str | None,
    tags: list,
) -> dict:
    """Print dry run info and return result."""
    print(f"  [DRY RUN] Would import: {media_path.name}")
    if is_audio:
        print(f"    Convert to: {output_filename}")
    print(f"    Title: {title}")
    print(f"    Performer: {author}")
    print(f"    URL: {reddit_url}")
    print(f"    Tags: {len(tags)}")
    return {"success": True, "dryRun": True}


def find_media_file(json_path: Path) -> Path | None:
    """Find media file corresponding to JSON sidecar (.mp4, .m4a, .mp3, etc.)."""
    for ext in (".mp4", ".m4a", ".mp3", ".wav", ".ogg", ".flac"):
        media_path = json_path.with_suffix(ext)
        if media_path.exists():
            return media_path
    return None


def get_sidecars_to_process(
    args: argparse.Namespace,
) -> tuple[list[tuple[Path, Path]], str | None]:
    """Get list of sidecars to process based on args. Returns (sidecars, error)."""
    if args.file:
        json_path = Path(args.file)
        if not json_path.exists():
            return [], f"File not found: {json_path}"
        media_path = find_media_file(json_path)
        if not media_path:
            return [], f"No media file (.mp4/.m4a) found for: {json_path}"
        print(f"Processing single file: {json_path.name}")
        return [(json_path, media_path)], None

    directory = Path(args.directory)
    if not directory.exists():
        return [], f"Directory not found: {directory}"
    sidecars = find_legacy_sidecars(directory, REDDIT_INDEX_DIR)
    print(f"Found {len(sidecars)} legacy files with unavailable Reddit content")
    return sidecars, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import legacy unavailable audio files to Stashapp"
    )
    parser.add_argument("directory", nargs="?", help="Path to legacy GWA directory")
    parser.add_argument("--file", help="Path to single JSON sidecar file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    parser.add_argument("--limit", type=int, help="Max files to process")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if not args.directory and not args.file:
        parser.error("Either directory or --file is required")
    if args.directory and args.file:
        parser.error("Cannot use both directory and --file")

    sidecars, error = get_sidecars_to_process(args)
    if error:
        print(f"Error: {error}")
        return 1

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
