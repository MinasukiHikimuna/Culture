#!/usr/bin/env python3
"""
Archive saved posts that have already been imported to Stashapp.

Checks each JSON file in saved_posts/ to see if its Reddit post ID
exists in Stashapp (by searching filenames), and moves matched files
to saved_posts_archived/.

Usage:
    uv run python archive_imported_saved.py [--dry-run]
"""

import argparse
import json
import shutil
from pathlib import Path

from dotenv import load_dotenv

from stashapp_importer import StashappClient

load_dotenv(Path(__file__).parent / ".env")

SAVED_POSTS_DIR = Path("saved_posts")
ARCHIVE_DIR = Path("saved_posts_archived")


def get_all_scenes_with_post_ids(client: StashappClient) -> dict[str, dict]:
    """
    Fetch all scenes from Stashapp and extract Reddit post IDs from filenames.
    Returns a dict mapping post_id -> scene info.
    """
    import re

    query = """
        query FindScenes($filter: FindFilterType!) {
            findScenes(filter: $filter) {
                scenes {
                    id
                    title
                    files { basename }
                }
            }
        }
    """
    result = client.query(query, {"filter": {"per_page": -1}})
    scenes = result.get("findScenes", {}).get("scenes", [])

    # Build mapping of post_id -> scene
    post_id_to_scene: dict[str, dict] = {}
    # Pattern: "- {post_id} -" where post_id is 6+ alphanumeric chars
    pattern = re.compile(r" - (\w{6,}) - ")

    for scene in scenes:
        for f in scene.get("files", []):
            basename = f.get("basename", "")
            match = pattern.search(basename)
            if match:
                post_id = match.group(1)
                post_id_to_scene[post_id] = {
                    "id": scene["id"],
                    "title": scene["title"],
                }

    return post_id_to_scene


def main():
    parser = argparse.ArgumentParser(
        description="Archive saved posts already imported to Stashapp"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be archived without moving files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of files to process (0 = no limit)",
    )
    args = parser.parse_args()

    if not SAVED_POSTS_DIR.exists():
        print(f"No saved_posts directory found at {SAVED_POSTS_DIR}")
        return

    # Create archive directory
    if not args.dry_run:
        ARCHIVE_DIR.mkdir(exist_ok=True)

    # Connect to Stashapp
    print("Connecting to Stashapp...")
    try:
        client = StashappClient()
        version = client.get_version()
        print(f"Connected to Stashapp {version}")
    except Exception as e:
        print(f"ERROR: Failed to connect to Stashapp: {e}")
        return

    # Fetch all scenes and build post_id lookup
    print("\nFetching all scenes from Stashapp...")
    post_id_to_scene = get_all_scenes_with_post_ids(client)
    print(f"Found {len(post_id_to_scene)} scenes with Reddit post IDs")

    # Get all saved post JSON files
    json_files = list(SAVED_POSTS_DIR.glob("*.json"))
    print(f"\nFound {len(json_files)} saved post files")

    if args.limit > 0:
        json_files = json_files[:args.limit]
        print(f"Processing first {args.limit} files")

    archived_count = 0
    not_found_count = 0
    error_count = 0

    for i, json_file in enumerate(json_files):
        try:
            with open(json_file, encoding="utf-8") as f:
                post_data = json.load(f)

            post_id = post_data.get("id")
            if not post_id:
                print(f"[{i + 1}/{len(json_files)}] {json_file.name} - ERROR: no post ID")
                error_count += 1
                continue

            # Fast lookup in pre-fetched data
            scene = post_id_to_scene.get(post_id)

            if scene:
                print(f"[{i + 1}/{len(json_files)}] {json_file.name} - FOUND -> Scene {scene['id']}")
                if not args.dry_run:
                    dest = ARCHIVE_DIR / json_file.name
                    shutil.move(str(json_file), str(dest))
                archived_count += 1
            else:
                print(f"[{i + 1}/{len(json_files)}] {json_file.name} - Not in Stashapp")
                not_found_count += 1

        except Exception as e:
            print(f"[{i + 1}/{len(json_files)}] {json_file.name} - ERROR: {e}")
            error_count += 1

    print(f"\n--- Summary ---")
    print(f"{'Would archive' if args.dry_run else 'Archived'}: {archived_count}")
    print(f"Not in Stashapp: {not_found_count}")
    print(f"Errors: {error_count}")


if __name__ == "__main__":
    main()
