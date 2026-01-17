#!/usr/bin/env python3
"""
Reset Post Script

Finds and optionally deletes all files associated with a Reddit post ID,
allowing it to be re-processed from scratch.

Usage:
    python reset_post.py <post_id> [post_id...] [--execute]

By default runs in dry-run mode showing what would be deleted.
Use --execute to actually delete the files.
"""

import argparse
import json
import os
import shutil
from pathlib import Path

import config as aural_config
import httpx
from dotenv import load_dotenv


load_dotenv()

AURAL_STASH_PATH = aural_config.STASH_OUTPUT_DIR
DATA_DIR = aural_config.RELEASES_DIR.parent
ANALYSIS_DIR = aural_config.ANALYSIS_DIR
EXTRACTED_DATA_DIR = aural_config.REDDIT_INDEX_DIR

# Stashapp configuration
STASH_URL = os.getenv("STASHAPP_URL")
STASH_API_KEY = os.getenv("STASHAPP_API_KEY")


def stashapp_query(query: str, variables: dict | None = None) -> dict | None:
    """Execute a GraphQL query against Stashapp."""
    if not STASH_URL or not STASH_API_KEY:
        return None

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                STASH_URL,
                json={"query": query, "variables": variables or {}},
                headers={"ApiKey": STASH_API_KEY, "Content-Type": "application/json"},
            )
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass
    return None


def find_stashapp_scenes(post_id: str) -> list[dict]:
    """Find Stashapp scenes that have a URL containing the post ID."""
    query = """
    query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType) {
        findScenes(filter: $filter, scene_filter: $scene_filter) {
            scenes {
                id
                title
                urls
            }
        }
    }
    """
    variables = {
        "filter": {"per_page": 100},
        "scene_filter": {"url": {"modifier": "INCLUDES", "value": post_id}},
    }

    result = stashapp_query(query, variables)
    if result and "data" in result:
        return result["data"]["findScenes"]["scenes"]
    return []


def delete_stashapp_scene(scene_id: str, delete_file: bool = True) -> bool:
    """Delete a scene from Stashapp."""
    mutation = """
    mutation SceneDestroy($input: SceneDestroyInput!) {
        sceneDestroy(input: $input)
    }
    """
    variables = {
        "input": {
            "id": scene_id,
            "delete_file": delete_file,
            "delete_generated": True,
        }
    }

    result = stashapp_query(mutation, variables)
    return result is not None and "data" in result


def find_source_post_file(post_id: str) -> Path | None:
    """Search aural_data/index/reddit/<author>/<postId>_*.json"""
    if not EXTRACTED_DATA_DIR.exists():
        return None

    for author_dir in EXTRACTED_DATA_DIR.iterdir():
        if not author_dir.is_dir():
            continue

        for f in author_dir.iterdir():
            if (
                f.name.startswith(f"{post_id}_")
                and f.suffix == ".json"
                and "_enriched" not in f.name
            ):
                return f

    return None


def find_files_for_post(post_id: str) -> dict:
    """Find all files related to a post ID."""
    files = {
        "analysis_files": [],
        "release_dir": None,
        "aural_stash_files": [],
        "processed_entry": False,
        "stashapp_scenes": [],
    }

    # 1. Find analysis files matching the post ID
    if ANALYSIS_DIR.exists():
        for f in ANALYSIS_DIR.iterdir():
            if f.name.startswith(f"{post_id}_") and f.name.endswith("_analysis.json"):
                files["analysis_files"].append(f)

    # 2. Find release directory - search through all authors
    releases_dir = DATA_DIR / "releases"
    if releases_dir.exists():
        for author_dir in releases_dir.iterdir():
            if not author_dir.is_dir():
                continue

            for release in author_dir.iterdir():
                if release.name.startswith(f"{post_id}_"):
                    files["release_dir"] = release
                    break

            if files["release_dir"]:
                break

    # 3. Find Aural_Stash MP4 files containing the post ID
    if AURAL_STASH_PATH.exists():
        for f in AURAL_STASH_PATH.iterdir():
            if post_id in f.name and f.suffix == ".mp4":
                files["aural_stash_files"].append(f)

    # 4. Check processed_posts.json
    processed_path = DATA_DIR / "processed_posts.json"
    if processed_path.exists():
        try:
            with open(processed_path) as f:
                processed = json.load(f)
            if processed.get("posts", {}).get(post_id):
                files["processed_entry"] = True
        except (json.JSONDecodeError, IOError):
            pass

    # 5. Find Stashapp scenes with URLs containing the post ID
    files["stashapp_scenes"] = find_stashapp_scenes(post_id)

    return files


def delete_files(files: dict, post_id: str, dry_run: bool) -> int:
    """Delete or report files to be deleted."""
    action = "Would delete" if dry_run else "Deleting"
    count = 0

    # Analysis files
    for f in files["analysis_files"]:
        print(f"  {action}: {f}")
        if not dry_run:
            f.unlink()
        count += 1

    # Release directory
    if files["release_dir"]:
        print(f"  {action}: {files['release_dir']}/")
        if not dry_run:
            shutil.rmtree(files["release_dir"])
        count += 1

    # Aural_Stash files
    for f in files["aural_stash_files"]:
        print(f"  {action}: {f}")
        if not dry_run:
            f.unlink()
        count += 1

    # Processed entry
    if files["processed_entry"]:
        print(f"  {action}: processed_posts.json entry for {post_id}")
        if not dry_run:
            processed_path = DATA_DIR / "processed_posts.json"
            with open(processed_path) as f:
                processed = json.load(f)
            del processed["posts"][post_id]
            with open(processed_path, "w") as f:
                json.dump(processed, f, indent=2)
        count += 1

    # Stashapp scenes
    for scene in files["stashapp_scenes"]:
        scene_id = scene["id"]
        title = scene.get("title", "Untitled")[:50]
        print(f"  {action}: Stashapp scene {scene_id} ({title}...)")
        if not dry_run:
            if delete_stashapp_scene(scene_id, delete_file=True):
                pass  # Success
            else:
                print(f"    ⚠️  Failed to delete scene {scene_id}")
        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Reset Post - Clear all files for a Reddit post ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Files checked:
  - aural_data/analysis/<post_id>_*_analysis.json
  - aural_data/releases/<author>/<post_id>_*/
  - /Volumes/Culture 1/Aural_Stash/*<post_id>*.mp4
  - aural_data/tracking/processed_posts.json entry
  - Stashapp scenes with URLs containing the post ID

Examples:
  python reset_post.py 1e1olrf              # Show what would be deleted
  python reset_post.py 1e1olrf --execute    # Actually delete
  python reset_post.py 1dknr0o 1e1olrf 1e109z3 --execute  # Multiple posts
""",
    )
    parser.add_argument("post_ids", nargs="+", help="Reddit post ID(s) to reset")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete files (default is dry-run)",
    )

    args = parser.parse_args()
    dry_run = not args.execute

    if dry_run:
        print("DRY RUN - No files will be deleted\n")

    total_count = 0
    reimport_commands = []

    for post_id in args.post_ids:
        print(f"\n📋 Post: {post_id}")
        files = find_files_for_post(post_id)
        source_file = find_source_post_file(post_id)

        has_files = (
            files["analysis_files"]
            or files["release_dir"]
            or files["aural_stash_files"]
            or files["processed_entry"]
            or files["stashapp_scenes"]
        )

        if not has_files:
            print("  No files found for this post ID")
            continue

        count = delete_files(files, post_id, dry_run)
        print(f"  Total: {count} item(s)")
        total_count += count

        if source_file:
            reimport_commands.append(
                f"uv run python analyze_download_import.py ./{source_file} --force"
            )

    if len(args.post_ids) > 1:
        print(f"\n{'─' * 40}")
        print(f"Grand total: {total_count} item(s)")

    if dry_run and total_count > 0:
        print("\nRun with --execute to delete these files")

    # Show re-import commands
    if reimport_commands:
        print(f"\n{'═' * 60}")
        print("To re-import after reset:")
        print("═" * 60)
        for cmd in reimport_commands:
            print(cmd)


if __name__ == "__main__":
    main()
