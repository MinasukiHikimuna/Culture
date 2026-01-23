#!/usr/bin/env python3
"""
Fix Patreon Metadata - Update existing Patreon scenes with studio code and tags.

One-off script to backfill metadata for previously imported Patreon scenes.

Usage:
    uv run python fix_patreon_metadata.py --dry-run
    uv run python fix_patreon_metadata.py
"""

import argparse
import re
import sys
from pathlib import Path

from patreon_importer import extract_audio_post, load_patreon_metadata
from stashapp_importer import (
    StashappClient,
    extract_tags_from_title,
    match_tags_with_stash,
)


# Mapping of performer name to their Patreon JSON directory
PERFORMER_DIRS = {
    "Pippits": Path("/Volumes/Culture 1/Aural_NEEDS_MANUAL_IMPORT/Patreon - Pippits/JSON"),
    "Elly Belle": Path(
        "/Volumes/Culture 1/Aural_NEEDS_MANUAL_IMPORT/Patreon - Elly Belle/JSON"
    ),
}


def extract_post_id(scene: dict) -> str | None:
    """Extract Patreon post ID from scene URL or filename."""
    # Try URL first: https://www.patreon.com/posts/title-slug-109951629
    for url in scene.get("urls", []):
        if "patreon.com/posts/" in url:
            match = re.search(r"-(\d{8,})$", url)
            if match:
                return match.group(1)

    # Fallback to filename: "Performer - 2024-08-12 - 109951629 - Title.mp4"
    for f in scene.get("files", []):
        basename = f.get("basename", "")
        match = re.search(r"- (\d{8,}) -", basename)
        if match:
            return match.group(1)

    return None


def get_performer_from_scene(scene: dict) -> str | None:
    """Get performer name from scene."""
    performers = scene.get("performers", [])
    if performers:
        return performers[0].get("name")
    return None


def build_details(post_meta: dict, all_tags: list[str]) -> str:
    """Build details field with teaser and tags in brackets."""
    parts = []
    if post_meta.get("teaser"):
        parts.append(post_meta["teaser"])
    if all_tags:
        tags_line = " ".join(f"[{tag}]" for tag in all_tags)
        parts.append(tags_line)
    return "\n\n".join(parts)


def fix_scene(
    client: StashappClient,
    scene: dict,
    post_meta: dict,
    all_stash_tags: list[dict],
    dry_run: bool,
) -> bool:
    """Fix a single scene's metadata. Returns True if updated."""
    scene_id = scene["id"]
    post_id = post_meta["post_id"]

    # Extract and match tags
    title_tags = extract_tags_from_title(post_meta["title"])
    all_tags = list(set(title_tags + post_meta["tags"]))
    matched_tag_ids = match_tags_with_stash(all_tags, all_stash_tags)

    # Build updates
    updates = {"code": post_id}

    if matched_tag_ids:
        updates["tag_ids"] = matched_tag_ids

    details = build_details(post_meta, all_tags)
    if details:
        updates["details"] = details

    if dry_run:
        print(f"  [DRY RUN] Would update scene {scene_id}:")
        print(f"    code: {post_id}")
        print(f"    tags: {len(matched_tag_ids)} matched")
        print(f"    details: {len(details)} chars")
        return True

    client.update_scene(scene_id, updates)
    print(f"  Updated scene {scene_id}: code={post_id}, {len(matched_tag_ids)} tags")
    return True


def load_all_patreon_metadata() -> tuple[dict, dict]:
    """Load Patreon metadata from all performer directories."""
    print("Loading Patreon metadata...")
    all_posts = {}
    all_media = {}
    for performer, directory in PERFORMER_DIRS.items():
        if not directory.exists():
            print(f"  Warning: {directory} not found, skipping {performer}")
            continue
        posts, media = load_patreon_metadata(directory)
        all_posts.update(posts)
        all_media.update(media)
        print(f"  {performer}: {len(posts)} posts loaded")
    return all_posts, all_media


def fetch_patreon_scenes(client: StashappClient, studio_id: str) -> list[dict]:
    """Fetch all scenes from the Patreon studio."""
    print("\nFetching Patreon scenes...")
    query = """
        query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
            findScenes(scene_filter: $scene_filter, filter: $filter) {
                scenes {
                    id
                    title
                    code
                    urls
                    performers { name }
                    files { basename }
                }
            }
        }
    """
    result = client.query(
        query,
        {
            "scene_filter": {"studios": {"value": [studio_id], "modifier": "INCLUDES"}},
            "filter": {"per_page": -1},
        },
    )
    scenes = result.get("findScenes", {}).get("scenes", [])
    print(f"  Found {len(scenes)} Patreon scenes")
    return scenes


def process_scene(
    scene: dict,
    all_posts: dict,
    all_media: dict,
    client: StashappClient,
    all_stash_tags: list[dict],
    dry_run: bool,
) -> str:
    """Process a single scene. Returns 'updated', 'skipped', or 'not_found'."""
    scene_id = scene["id"]
    title = scene.get("title", "")[:50]

    if scene.get("code"):
        return "skipped"

    post_id = extract_post_id(scene)
    if not post_id:
        print(f"  Scene {scene_id}: Could not extract post ID from {title}...")
        return "not_found"

    if post_id not in all_posts:
        print(f"  Scene {scene_id}: Post {post_id} not in metadata")
        return "not_found"

    post_meta = extract_audio_post(all_posts[post_id], all_media)
    if not post_meta:
        print(f"  Scene {scene_id}: Post {post_id} is not an audio post")
        return "not_found"

    fix_scene(client, scene, post_meta, all_stash_tags, dry_run)
    return "updated"


def main():
    parser = argparse.ArgumentParser(
        description="Fix metadata for existing Patreon scenes"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    args = parser.parse_args()

    all_posts, all_media = load_all_patreon_metadata()
    if not all_posts:
        print("Error: No Patreon metadata found")
        sys.exit(1)

    print("\nConnecting to Stashapp...")
    client = StashappClient()

    studio = client.find_studio("Patreon")
    if not studio:
        print("Error: Patreon studio not found")
        sys.exit(1)
    print(f"  Found studio: {studio['name']} (ID: {studio['id']})")

    all_stash_tags = client.get_all_tags()
    print(f"  Loaded {len(all_stash_tags)} Stashapp tags")

    scenes = fetch_patreon_scenes(client, studio["id"])

    print("\nProcessing scenes...")
    counts = {"updated": 0, "skipped": 0, "not_found": 0}
    for scene in scenes:
        result = process_scene(
            scene, all_posts, all_media, client, all_stash_tags, args.dry_run
        )
        counts[result] += 1

    print(f"\n{'=' * 40}")
    print("Summary:")
    print(f"  Updated: {counts['updated']}")
    print(f"  Skipped (already has code): {counts['skipped']}")
    print(f"  Not found in metadata: {counts['not_found']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes were made")


if __name__ == "__main__":
    main()
