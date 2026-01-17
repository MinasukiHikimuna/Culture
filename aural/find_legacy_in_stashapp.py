#!/usr/bin/env python3
"""
Find Legacy Stash Files in Stashapp by Name Match

For legacy MP4/M4A files in Aural_Stash_Legacy, find matching scenes in Stashapp
by performer and title similarity.

Usage:
    uv run python find_legacy_in_stashapp.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/"
    uv run python find_legacy_in_stashapp.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --limit 10
    uv run python find_legacy_in_stashapp.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --delete
    uv run python find_legacy_in_stashapp.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --filter "AprilW9"
"""

import argparse
import re
import unicodedata
from pathlib import Path

from stashapp_importer import StashappClient


def normalize_text(text: str) -> str:
    """Normalize text for comparison by removing special chars and lowercasing."""
    if not text:
        return ""
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    # Remove common variations
    text = text.lower()
    # Remove special characters but keep alphanumeric and spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title_from_stashapp_title(full_title: str) -> str:
    """Extract the core title from a Stashapp scene title, removing tags."""
    # Remove [tag] patterns like [F4M], [Script Fill], etc.
    title = re.sub(r"\[.*?\]", "", full_title)
    # Remove extra whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def parse_legacy_filename(filename: str) -> tuple[str, str] | None:
    """Parse legacy filename into (performer, title).

    Handles formats:
    - "Performer - Title.mp4"
    - "Performer - Date - Title.mp4" (e.g., "Anonymous_Ghuleh - 2018-06-19 - Title.mp4")
    """
    stem = Path(filename).stem

    # Try pattern with date first: "Performer - YYYY-MM-DD - Title"
    match = re.match(r"^(.+?)\s*-\s*\d{4}-\d{2}-\d{2}\s*-\s*(.+)$", stem)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # Standard pattern: "Performer - Title"
    match = re.match(r"^(.+?)\s*-\s*(.+)$", stem)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return None


def calculate_title_match_score(legacy_title: str, stashapp_title: str) -> float:
    """Calculate how well two titles match (0.0 to 1.0)."""
    norm_legacy = normalize_text(legacy_title)
    core_stashapp = extract_title_from_stashapp_title(stashapp_title)
    norm_stashapp = normalize_text(core_stashapp)

    if not norm_legacy or not norm_stashapp:
        return 0.0

    # Exact match
    if norm_legacy == norm_stashapp:
        return 1.0

    # Substring match
    if norm_legacy in norm_stashapp or norm_stashapp in norm_legacy:
        return min(len(norm_legacy), len(norm_stashapp)) / max(len(norm_legacy), len(norm_stashapp))

    # Word overlap
    legacy_words = set(norm_legacy.split())
    stashapp_words = set(norm_stashapp.split())

    if len(legacy_words) >= 2:
        common = legacy_words & stashapp_words
        # Score based on proportion of matching words
        if common:
            return len(common) / max(len(legacy_words), len(stashapp_words))

    return 0.0


def find_matching_scene(
    client: StashappClient,
    performer: str,
    title: str,
    performer_scenes_cache: dict[str, list[dict]],
    min_score: float = 0.9,
    verbose: bool = False,
) -> dict | None:
    """Find a matching scene in Stashapp for the given performer and title."""
    # Get scenes for performer (with caching)
    if performer not in performer_scenes_cache:
        if verbose:
            print(f"  Fetching scenes for performer: {performer}")
        scenes = client.find_scenes_by_performer(performer)
        performer_scenes_cache[performer] = scenes
        if verbose:
            print(f"  Found {len(scenes)} scenes")

    scenes = performer_scenes_cache[performer]
    if not scenes:
        return None

    # Find best matching scene
    best_match = None
    best_score = 0.0

    for scene in scenes:
        scene_title = scene.get("title", "")
        score = calculate_title_match_score(title, scene_title)

        if score > best_score:
            best_score = score
            best_match = scene
            if verbose and score > 0.3:
                print(f"    Score {score:.2f}: {scene_title[:60]}")

    if best_score >= min_score:
        return {"scene": best_match, "score": best_score}

    return None


def find_media_files(directory: Path) -> list[Path]:
    """Find all MP4 and M4A files in directory."""
    files = []
    for ext in ["*.mp4", "*.m4a"]:
        files.extend(directory.glob(ext))
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find legacy stash files in Stashapp by name match"
    )
    parser.add_argument("directory", help="Path to legacy directory")
    parser.add_argument("--filter", type=str, help="Only process files containing this string (case-insensitive)")
    parser.add_argument("--limit", type=int, help="Max files to check")
    parser.add_argument("--delete", action="store_true", help="Delete matched files")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--min-score", type=float, default=0.9, help="Minimum match score (default: 0.9)")

    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1

    # Find media files
    media_files = find_media_files(directory)
    print(f"Found {len(media_files)} media files")

    # Apply filter if specified
    if args.filter:
        filter_lower = args.filter.lower()
        media_files = [f for f in media_files if filter_lower in f.name.lower()]
        print(f"Filtered to {len(media_files)} files matching '{args.filter}'")

    if args.limit:
        media_files = media_files[: args.limit]

    if not media_files:
        return 0

    # Initialize client
    client = StashappClient()
    performer_scenes_cache: dict[str, list[dict]] = {}

    # Check each file
    results = {"matched": [], "not_found": [], "parse_error": []}

    for i, media_path in enumerate(media_files):
        print(f"\n[{i + 1}/{len(media_files)}] {media_path.name}")

        # Parse filename
        parsed = parse_legacy_filename(media_path.name)
        if not parsed:
            print("  Could not parse filename")
            results["parse_error"].append(str(media_path))
            continue

        performer, title = parsed
        if args.verbose:
            print(f"  Performer: {performer}")
            print(f"  Title: {title}")

        # Find matching scene
        match = find_matching_scene(
            client, performer, title, performer_scenes_cache, args.min_score, args.verbose
        )

        if match:
            scene = match["scene"]
            score = match["score"]
            performers = [p["name"] for p in scene.get("performers", [])]
            print(f"  ✓ FOUND ({score:.2f}): Scene {scene['id']} - {scene['title'][:50]}")
            if performers:
                print(f"    Performers: {', '.join(performers)}")
            results["matched"].append({
                "file": str(media_path),
                "scene_id": scene["id"],
                "title": scene["title"],
                "performers": performers,
                "score": score,
            })
        else:
            print("  ✗ Not found in Stashapp")
            results["not_found"].append({"file": str(media_path), "performer": performer, "title": title})

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Matched: {len(results['matched'])}")
    print(f"Not found: {len(results['not_found'])}")
    print(f"Parse errors: {len(results['parse_error'])}")

    if results["matched"]:
        print("\nMatched files (can be deleted):")
        for m in results["matched"]:
            print(f"  - {Path(m['file']).name}")
            performers_str = f" [{', '.join(m['performers'])}]" if m.get("performers") else ""
            print(f"    → Scene {m['scene_id']}: {m['title'][:50]}{performers_str} (score: {m['score']:.2f})")

    if results["not_found"]:
        print("\nNot found (could be imported):")
        for m in results["not_found"][:20]:
            print(f"  - {Path(m['file']).name}")
        if len(results["not_found"]) > 20:
            print(f"  ... and {len(results['not_found']) - 20} more")

    # Delete matched files if requested
    if args.delete and results["matched"]:
        print(f"\nDeleting {len(results['matched'])} matched files...")
        deleted_count = 0
        for m in results["matched"]:
            file_path = Path(m["file"])
            try:
                file_path.unlink()
                deleted_count += 1
                if args.verbose:
                    print(f"  Deleted: {file_path.name}")
            except Exception as e:
                print(f"  Error deleting {file_path.name}: {e}")
        print(f"Deleted {deleted_count} files")

    return 0


if __name__ == "__main__":
    exit(main())
