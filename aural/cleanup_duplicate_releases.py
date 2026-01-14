#!/usr/bin/env python3
"""
Cleanup Duplicate Release Directories

Finds and removes duplicate release directories created by LLM non-determinism.

This script handles cleanup in phases. Use --mode to select which case to handle:
- all-have-stash: All duplicates have the same stashapp_scene_id (safest)
- one-has-stash: One duplicate has stashapp_scene_id, others don't
- none-have-stash: No duplicates have stashapp_scene_id
- conflicts: Different stashapp_scene_ids (requires manual review)

Usage:
    uv run python cleanup_duplicate_releases.py --mode all-have-stash --dry-run
"""

import argparse
import json
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import config as aural_config


@dataclass
class ReleaseDir:
    """Info about a release directory."""

    path: Path
    post_id: str
    stashapp_scene_id: str | None
    aggregated_at: str | None
    audio_source_count: int
    has_release_json: bool


@dataclass
class DuplicateSet:
    """A set of duplicate directories for the same post."""

    key: str  # performer/post_id
    dirs: list[ReleaseDir]
    category: str  # all-have-stash, one-has-stash, none-have-stash, conflicts


def find_duplicates(releases_dir: Path) -> list[DuplicateSet]:
    """Find all duplicate release directories grouped by post_id."""
    # Group directories by (performer, post_id)
    by_key: dict[str, list[ReleaseDir]] = defaultdict(list)

    for performer_dir in releases_dir.iterdir():
        if not performer_dir.is_dir():
            continue

        for release_dir in performer_dir.iterdir():
            if not release_dir.is_dir():
                continue

            # Extract post_id (everything before first underscore)
            dir_name = release_dir.name
            post_id = dir_name.split("_")[0] if "_" in dir_name else dir_name

            # Read release.json if exists
            release_json = release_dir / "release.json"
            stashapp_scene_id = None
            aggregated_at = None
            audio_source_count = 0
            has_release_json = release_json.exists()

            if has_release_json:
                try:
                    data = json.loads(release_json.read_text(encoding="utf-8"))
                    stashapp_scene_id = data.get("stashapp_scene_id")
                    aggregated_at = data.get("aggregatedAt")
                    audio_source_count = len(data.get("audioSources", []))
                except (json.JSONDecodeError, OSError):
                    pass

            key = f"{performer_dir.name}/{post_id}"
            by_key[key].append(
                ReleaseDir(
                    path=release_dir,
                    post_id=post_id,
                    stashapp_scene_id=stashapp_scene_id,
                    aggregated_at=aggregated_at,
                    audio_source_count=audio_source_count,
                    has_release_json=has_release_json,
                )
            )

    # Categorize duplicates
    result = []
    for key, dirs in by_key.items():
        if len(dirs) < 2:
            continue

        scene_ids = {d.stashapp_scene_id for d in dirs if d.stashapp_scene_id}
        dirs_with_stash = sum(1 for d in dirs if d.stashapp_scene_id)

        if len(scene_ids) > 1:
            category = "conflicts"
        elif dirs_with_stash == len(dirs) and len(scene_ids) == 1:
            category = "all-have-stash"
        elif dirs_with_stash > 0:
            category = "one-has-stash"
        else:
            category = "none-have-stash"

        result.append(DuplicateSet(key=key, dirs=dirs, category=category))

    return result


def select_best_dir_all_have_stash(
    dirs: list[ReleaseDir],
) -> tuple[ReleaseDir, list[ReleaseDir]]:
    """
    Select best directory when all have the same stashapp_scene_id.
    Keep directory with richest metadata (most audio sources), oldest as tiebreaker.
    """
    dirs_sorted = sorted(
        dirs,
        key=lambda d: (
            -d.audio_source_count,  # Higher count first (more complete metadata)
            d.aggregated_at or "9999",  # Oldest as tiebreaker
            str(d.path),
        ),
    )
    return dirs_sorted[0], dirs_sorted[1:]


def select_best_dir_one_has_stash(
    dirs: list[ReleaseDir],
) -> tuple[ReleaseDir, list[ReleaseDir]]:
    """
    Select best directory when only one has stashapp_scene_id.
    Keep the one with stashapp_scene_id, delete the rest.
    """
    with_stash = [d for d in dirs if d.stashapp_scene_id]
    without_stash = [d for d in dirs if not d.stashapp_scene_id]

    # Keep the one with stash (prefer richest metadata if multiple)
    best = sorted(
        with_stash,
        key=lambda d: (-d.audio_source_count, d.aggregated_at or "9999"),
    )[0]

    # Delete all without stash + any extra with stash
    to_delete = without_stash + [d for d in with_stash if d != best]
    return best, to_delete


def calculate_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cleanup duplicate release directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  all-have-stash   All duplicates have the same stashapp_scene_id (safest)
  one-has-stash    One has stashapp_scene_id, others don't
  none-have-stash  No duplicates have stashapp_scene_id
  conflicts        Different stashapp_scene_ids (just reports, no deletion)
  summary          Show summary of all categories (no deletion)

Examples:
  # See summary of all duplicates
  uv run python cleanup_duplicate_releases.py --mode summary

  # Dry run for safest case
  uv run python cleanup_duplicate_releases.py --mode all-have-stash --dry-run

  # Actually delete (after reviewing dry run)
  uv run python cleanup_duplicate_releases.py --mode all-have-stash
""",
    )
    parser.add_argument(
        "--mode",
        choices=["all-have-stash", "one-has-stash", "none-have-stash", "conflicts", "summary"],
        required=True,
        help="Which category of duplicates to handle",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information about each duplicate set",
    )
    parser.add_argument(
        "--releases-dir",
        type=Path,
        default=aural_config.RELEASES_DIR,
        help=f"Releases directory (default: {aural_config.RELEASES_DIR})",
    )

    args = parser.parse_args()

    print(f"Scanning for duplicates in: {args.releases_dir}")
    all_duplicates = find_duplicates(args.releases_dir)

    if not all_duplicates:
        print("No duplicate directories found.")
        return 0

    # Count by category
    by_category: dict[str, list[DuplicateSet]] = defaultdict(list)
    for dup in all_duplicates:
        by_category[dup.category].append(dup)

    # Summary mode - just show counts
    if args.mode == "summary":
        print(f"\nFound {len(all_duplicates)} posts with duplicate directories:\n")
        for category in ["all-have-stash", "one-has-stash", "none-have-stash", "conflicts"]:
            dups = by_category.get(category, [])
            total_dirs = sum(len(d.dirs) for d in dups)
            extra_dirs = total_dirs - len(dups)  # dirs that would be deleted
            print(f"  {category}: {len(dups)} posts ({extra_dirs} extra directories)")
        return 0

    # Filter to selected mode
    duplicates = by_category.get(args.mode, [])

    if not duplicates:
        print(f"No duplicates found in category: {args.mode}")
        return 0

    print(f"Found {len(duplicates)} posts in category '{args.mode}'\n")

    # Handle conflicts mode - just report, no deletion
    if args.mode == "conflicts":
        print("Conflicts require manual review in Stashapp:\n")
        for dup in duplicates:
            print(f"  {dup.key}:")
            for d in dup.dirs:
                print(f"    {d.path.name}: stash_id={d.stashapp_scene_id}")
        return 0

    # Process duplicates
    total_to_delete = 0
    total_bytes_to_free = 0

    for dup in sorted(duplicates, key=lambda d: d.key):
        if args.mode == "all-have-stash":
            best, to_delete = select_best_dir_all_have_stash(dup.dirs)
        elif args.mode == "one-has-stash":
            best, to_delete = select_best_dir_one_has_stash(dup.dirs)
        else:
            # For other modes, we'll add handlers later
            print(f"Mode '{args.mode}' not yet implemented")
            return 1

        if args.verbose or args.dry_run:
            print(f"📁 {dup.key} ({len(dup.dirs)} directories)")
            print(f"   Keep: {best.path.name}")
            print(f"         stash_id={best.stashapp_scene_id}, created={best.aggregated_at}")

        for d in to_delete:
            size = calculate_size(d.path)
            total_to_delete += 1
            total_bytes_to_free += size

            if args.verbose or args.dry_run:
                print(f"   Delete: {d.path.name} ({format_size(size)})")

            if not args.dry_run:
                try:
                    shutil.rmtree(d.path)
                except OSError as e:
                    print(f"   Error deleting {d.path}: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")
    print(f"Duplicate sets processed: {len(duplicates)}")
    print(f"Directories to delete: {total_to_delete}")
    print(f"Space to free: {format_size(total_bytes_to_free)}")

    if args.dry_run:
        print("\n[DRY RUN] No files were deleted.")
        print("Run without --dry-run to actually delete the directories.")
    else:
        print(f"\nDeleted {total_to_delete} directories.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
