#!/usr/bin/env python3
"""
Backfill Stashapp scene IDs for existing releases.

Scans all release.json files and matches them against Stashapp
using the audio fingerprint (SHA256 checksum).

Usage:
    uv run python backfill_stashapp_ids.py [--dry-run]
"""

import argparse
import json
from pathlib import Path

import config as aural_config
from stashapp_importer import StashappClient
import sys


def backfill_stashapp_ids(dry_run: bool = False) -> dict:
    """
    Backfill stashapp_scene_id for releases that don't have it.

    Returns:
        Summary dict with counts and details
    """
    releases_dir = aural_config.RELEASES_DIR
    if not releases_dir.exists():
        print(f"Error: Releases directory not found: {releases_dir}")
        return {"error": "Releases directory not found"}

    # Initialize Stashapp client and test connection
    client = StashappClient()
    print("Testing Stashapp connection...")
    version = client.query("query { systemStatus { appSchema } }")
    print(f"Connected to Stashapp")

    # Find all release.json files
    release_files = list(releases_dir.glob("**/release.json"))
    print(f"Found {len(release_files)} release files\n")

    results = {
        "total": len(release_files),
        "already_has_id": 0,
        "matched": 0,
        "no_checksum": 0,
        "not_found": 0,
        "errors": 0,
        "details": [],
    }

    for release_path in release_files:
        try:
            release_data = json.loads(release_path.read_text(encoding="utf-8"))
            release_id = release_data.get("id", release_path.parent.name)

            # Skip if already has stashapp_scene_id
            if release_data.get("stashapp_scene_id"):
                results["already_has_id"] += 1
                continue

            # Get audio checksums from all sources
            audio_sources = release_data.get("audioSources", [])
            if not audio_sources:
                results["no_checksum"] += 1
                continue

            scene_ids = []
            for i, source in enumerate(audio_sources):
                checksum = source.get("audio", {}).get("checksum", {}).get("sha256")
                if not checksum:
                    continue

                # Look up scene by fingerprint
                scene = client.find_scene_by_fingerprint("audio_sha256", checksum)
                if scene:
                    scene_ids.append({"id": scene["id"], "index": i})

            if not scene_ids:
                results["not_found"] += 1
                results["details"].append(
                    {"release": release_id, "status": "not_found_in_stashapp"}
                )
                continue

            # Update release.json
            last_scene_id = scene_ids[-1]["id"]
            release_data["stashapp_scene_ids"] = [s["id"] for s in scene_ids]
            release_data["stashapp_scene_id"] = last_scene_id

            if dry_run:
                print(f"[DRY RUN] Would update {release_id}: scene {last_scene_id}")
            else:
                release_path.write_text(
                    json.dumps(release_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"Updated {release_id}: scene {last_scene_id}")

            results["matched"] += 1
            results["details"].append(
                {
                    "release": release_id,
                    "status": "matched",
                    "scene_id": last_scene_id,
                    "scene_count": len(scene_ids),
                }
            )

        except Exception as e:
            results["errors"] += 1
            results["details"].append(
                {"release": str(release_path), "status": "error", "error": str(e)}
            )
            print(f"Error processing {release_path}: {e}")

    # Summary
    print(f"\n{'=' * 50}")
    print("Backfill Summary")
    print(f"{'=' * 50}")
    print(f"Total releases:     {results['total']}")
    print(f"Already had ID:     {results['already_has_id']}")
    print(f"Matched & updated:  {results['matched']}")
    print(f"Not in Stashapp:    {results['not_found']}")
    print(f"No checksum:        {results['no_checksum']}")
    print(f"Errors:             {results['errors']}")

    if dry_run:
        print("\n[DRY RUN] No files were modified")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill Stashapp scene IDs for existing releases"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying files",
    )
    args = parser.parse_args()

    results = backfill_stashapp_ids(dry_run=args.dry_run)
    return 0 if results.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
