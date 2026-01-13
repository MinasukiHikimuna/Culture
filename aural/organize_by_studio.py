#!/usr/bin/env python3
"""
Organize Stashapp files into studio subdirectories.

Moves files from the flat /Volumes/Culture 1/Aural_Stash/ directory
into subdirectories named after their Stashapp studio.

Usage:
    uv run python organize_by_studio.py --dry-run
    uv run python organize_by_studio.py --limit 5
    uv run python organize_by_studio.py
"""

import argparse
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from config import windows_path_to_local
from stashapp_importer import StashappClient


DEFAULT_SOURCE_DIR = Path("/Volumes/Culture 1/Aural_Stash")


def main():
    parser = argparse.ArgumentParser(
        description="Organize Stashapp files into studio subdirectories"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without moving files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of scenes to process (0 = no limit)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Source directory containing flat files",
    )
    args = parser.parse_args()

    source_dir = args.source_dir
    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        return 1

    print("Connecting to Stashapp...")
    client = StashappClient()
    version = get_version(client)
    print(f"Connected to Stashapp {version}")

    print("\nFetching scenes with studios...")
    all_scenes = get_scenes_with_studios(client)
    print(f"Found {len(all_scenes)} scenes with studios")

    print(f"\nFiltering to files in {source_dir}...")
    flat_scenes = filter_flat_directory_scenes(all_scenes, source_dir)
    print(f"Found {len(flat_scenes)} scenes with files in flat directory")

    if not flat_scenes:
        print("\nNo files to organize. Done!")
        return 0

    if args.limit > 0:
        flat_scenes = flat_scenes[: args.limit]
        print(f"Limited to {args.limit} scenes")

    scenes_by_studio = group_scenes_by_studio(flat_scenes)
    print(f"\nScenes grouped into {len(scenes_by_studio)} studios:")
    for studio, scenes in sorted(scenes_by_studio.items()):
        file_count = sum(len(s["files"]) for s in scenes)
        print(f"  {studio}: {len(scenes)} scenes, {file_count} files")

    print("\nPlanning file moves...")
    moves = plan_moves(scenes_by_studio, source_dir)
    conflicts = [m for m in moves if m["conflict"]]
    if conflicts:
        print(f"  {len(conflicts)} conflicts detected (will be renamed)")

    mode = "DRY-RUN" if args.dry_run else "EXECUTING"
    print(f"\n--- {mode} ---")
    success, skipped, errors = execute_moves(moves, args.dry_run)

    print("\n--- Summary ---")
    print(f"{'Would move' if args.dry_run else 'Moved'}: {success}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")

    if not args.dry_run and success > 0:
        print("\nNote: Run a Stashapp scan to update file paths in the database.")

    return 0 if errors == 0 else 1


def get_version(client: StashappClient) -> str:
    """Get Stashapp version."""
    query = "query { version { version } }"
    result = client.query(query)
    return result.get("version", {}).get("version", "unknown")


def get_scenes_with_studios(client: StashappClient) -> list[dict]:
    """Fetch all scenes that have a studio set and have files."""
    query = """
        query FindScenesWithStudios($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
            findScenes(scene_filter: $scene_filter, filter: $filter) {
                count
                scenes {
                    id
                    title
                    studio {
                        id
                        name
                    }
                    files {
                        id
                        path
                        basename
                    }
                }
            }
        }
    """
    result = client.query(
        query,
        {
            "scene_filter": {"studios": {"modifier": "NOT_NULL"}},
            "filter": {"per_page": -1},
        },
    )
    return result.get("findScenes", {}).get("scenes", [])


def filter_flat_directory_scenes(scenes: list[dict], source_dir: Path) -> list[dict]:
    """Filter to only scenes with files directly in source_dir (not in subdirs)."""
    filtered = []
    for scene in scenes:
        flat_files = []
        for f in scene.get("files", []):
            # Convert Windows path from Stashapp to local Mac path
            local_path = windows_path_to_local(f["path"])
            if local_path.parent == source_dir:
                # Store the local path for later use
                flat_files.append({**f, "local_path": local_path})

        if flat_files:
            filtered_scene = {**scene, "files": flat_files}
            filtered.append(filtered_scene)

    return filtered


def sanitize_studio_name(name: str) -> str:
    """Sanitize studio name for filesystem use."""
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
    safe_name = re.sub(r"_+", "_", safe_name)
    safe_name = safe_name.strip().strip("_")
    return safe_name or "Unknown_Studio"


def group_scenes_by_studio(scenes: list[dict]) -> dict[str, list[dict]]:
    """Group scenes by their sanitized studio name."""
    grouped = defaultdict(list)
    for scene in scenes:
        studio = scene.get("studio", {})
        studio_name = studio.get("name", "Unknown")
        safe_name = sanitize_studio_name(studio_name)
        grouped[safe_name].append(scene)
    return dict(grouped)


def plan_moves(
    scenes_by_studio: dict[str, list[dict]], source_dir: Path
) -> list[dict]:
    """Plan all file moves, detecting and handling conflicts."""
    moves = []
    destination_tracker: dict[str, Path] = {}

    for studio_name, scenes in scenes_by_studio.items():
        studio_dir = source_dir / studio_name

        for scene in scenes:
            for f in scene.get("files", []):
                source_path = f["local_path"]  # Use pre-computed local path
                basename = f["basename"]
                dest_path = studio_dir / basename

                conflict = False
                conflict_resolution = None

                if dest_path.exists():
                    conflict = True
                    dest_path, conflict_resolution = resolve_conflict(dest_path)

                if str(dest_path) in destination_tracker:
                    conflict = True
                    dest_path, conflict_resolution = resolve_conflict(dest_path)

                destination_tracker[str(dest_path)] = source_path

                moves.append(
                    {
                        "source": source_path,
                        "destination": dest_path,
                        "scene_id": scene["id"],
                        "studio": studio_name,
                        "conflict": conflict,
                        "conflict_resolution": conflict_resolution,
                    }
                )

    return moves


def resolve_conflict(dest_path: Path) -> tuple[Path, str]:
    """Find a non-conflicting filename."""
    stem = dest_path.stem
    suffix = dest_path.suffix
    parent = dest_path.parent

    counter = 2
    while True:
        new_name = f"{stem}_{counter}{suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path, f"renamed_to_{new_name}"
        counter += 1
        if counter > 100:
            raise RuntimeError(f"Could not find unique name for {dest_path}")


def execute_moves(moves: list[dict], dry_run: bool) -> tuple[int, int, int]:
    """Execute the planned moves. Returns (success, skipped, errors)."""
    success = 0
    skipped = 0
    errors = 0

    studios = {m["studio"] for m in moves}
    source_dir = moves[0]["source"].parent if moves else Path()

    if not dry_run:
        for studio in studios:
            studio_dir = source_dir / studio
            studio_dir.mkdir(exist_ok=True)

    for move in moves:
        source = move["source"]
        dest = move["destination"]
        prefix = "[DRY-RUN] " if dry_run else ""

        if not source.exists():
            print(f"{prefix}SKIP: Source not found: {source}")
            skipped += 1
            continue

        if move["conflict"]:
            print(
                f"{prefix}MOVE (conflict resolved): {source.name} -> "
                f"{dest.parent.name}/{dest.name}"
            )
        else:
            print(f"{prefix}MOVE: {source.name} -> {dest.parent.name}/")

        if not dry_run:
            try:
                shutil.move(str(source), str(dest))
                success += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                errors += 1
        else:
            success += 1

    return success, skipped, errors


if __name__ == "__main__":
    sys.exit(main())
