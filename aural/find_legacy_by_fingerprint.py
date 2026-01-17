#!/usr/bin/env python3
"""
Find Legacy Audio Files in Stashapp by Audio Fingerprint

Computes SHA-256 of original M4A audio files and checks if the fingerprint
matches any scene in Stashapp.

Usage:
    uv run python find_legacy_by_fingerprint.py "/Volumes/Culture 1/Aural/GWA/"
    uv run python find_legacy_by_fingerprint.py "/Volumes/Culture 1/Aural/GWA/" --limit 5
    uv run python find_legacy_by_fingerprint.py "/Volumes/Culture 1/Aural/GWA/" --delete
"""

import argparse
import hashlib
from pathlib import Path

from stashapp_importer import StashappClient
import sys


def compute_file_sha256(file_path: Path) -> str | None:
    """Compute SHA-256 hash of file."""
    try:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"  Error computing hash: {e}")
        return None


def find_scene_by_audio_fingerprint(client: StashappClient, sha256: str) -> dict | None:
    """Find a scene by audio SHA-256 fingerprint."""
    return client.find_scene_by_fingerprint("audio_sha256", sha256)


def find_audio_files(directory: Path) -> list[Path]:
    """Find all M4A audio files in directory."""
    return sorted(directory.glob("*.m4a"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find legacy audio files in Stashapp by fingerprint"
    )
    parser.add_argument("directory", help="Path to legacy GWA directory")
    parser.add_argument("--skip", type=int, default=0, help="Skip first N files")
    parser.add_argument("--limit", type=int, help="Max files to check")
    parser.add_argument("--delete", action="store_true", help="Delete matched files")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1

    # Find M4A audio files
    audio_files = find_audio_files(directory)
    print(f"Found {len(audio_files)} M4A audio files")

    if args.skip:
        audio_files = audio_files[args.skip:]
    if args.limit:
        audio_files = audio_files[: args.limit]

    if not audio_files:
        return 0

    # Initialize client
    client = StashappClient()

    # Check each file
    results = {"matched": [], "not_found": [], "error": []}

    for i, audio_path in enumerate(audio_files):
        print(f"\n[{i + 1}/{len(audio_files)}] {audio_path.name}")

        # Compute SHA-256 of the audio file
        sha256 = compute_file_sha256(audio_path)
        if not sha256:
            print("  Failed to compute hash")
            results["error"].append(str(audio_path))
            continue

        if args.verbose:
            print(f"  SHA-256: {sha256[:16]}...")

        # Search in Stashapp
        scene = find_scene_by_audio_fingerprint(client, sha256)
        if scene:
            print(f"  ✓ FOUND: Scene {scene['id']} - {scene['title'][:60]}")
            performers = [p["name"] for p in scene.get("performers", [])]
            if performers:
                print(f"    Performers: {', '.join(performers)}")
            results["matched"].append({
                "file": str(audio_path),
                "scene_id": scene["id"],
                "title": scene["title"],
            })
        else:
            print("  ✗ Not found in Stashapp")
            results["not_found"].append(str(audio_path))

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Matched: {len(results['matched'])}")
    print(f"Not found: {len(results['not_found'])}")
    print(f"Errors: {len(results['error'])}")

    if results["matched"]:
        print("\nMatched files (can be deleted):")
        for m in results["matched"]:
            print(f"  - {Path(m['file']).name}")
            print(f"    → Scene {m['scene_id']}: {m['title'][:50]}")

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

                # Also delete JSON sidecar if it exists
                json_sidecar = file_path.with_suffix(".json")
                if json_sidecar.exists():
                    json_sidecar.unlink()
                    deleted_count += 1
                    if args.verbose:
                        print(f"  Deleted: {json_sidecar.name}")
            except Exception as e:
                print(f"  Error deleting {file_path.name}: {e}")
        print(f"Deleted {deleted_count} files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
