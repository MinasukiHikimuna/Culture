#!/usr/bin/env python3
"""
Cleanup Orphaned JSON Files from GWA Directory

Finds and removes orphaned JSON sidecar files from the legacy GWA directory.
These are JSON files whose corresponding audio files have been removed after
being imported to Stashapp.

Usage:
    uv run python cleanup_orphaned_json.py --mode summary
    uv run python cleanup_orphaned_json.py --mode unverified
    uv run python cleanup_orphaned_json.py --mode verified --dry-run
    uv run python cleanup_orphaned_json.py --mode verified
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from stashapi.stashapp import StashInterface


GWA_DIR = Path("/Volumes/Culture 1/Aural/GWA")


@dataclass
class OrphanedJson:
    """Info about an orphaned JSON file."""

    path: Path
    author: str
    title: str
    reddit_url: str | None
    post_id: str | None


@dataclass
class VerificationResult:
    """Result of verifying orphaned JSON files against Stashapp."""

    verified: list[OrphanedJson]
    unverified: list[OrphanedJson]
    without_post_id: list[OrphanedJson]


def get_stashapp_client() -> StashInterface:
    """Create Stashapp client for the aural instance."""
    load_dotenv()

    return StashInterface(
        {
            "scheme": os.getenv("AURAL_STASHAPP_SCHEME", "http"),
            "host": os.getenv("AURAL_STASHAPP_HOST", "localhost"),
            "port": os.getenv("AURAL_STASHAPP_PORT", "9999"),
            "ApiKey": os.getenv("AURAL_STASHAPP_API_KEY"),
        }
    )


def find_orphaned_json_files(gwa_dir: Path) -> list[OrphanedJson]:
    """Find JSON files in GWA directory that have no corresponding audio file."""
    orphans = []

    for json_path in gwa_dir.glob("*.json"):
        orphan = _parse_json_file(gwa_dir, json_path)
        if orphan:
            orphans.append(orphan)

    return orphans


def _parse_json_file(gwa_dir: Path, json_path: Path) -> OrphanedJson | None:
    """Parse a single JSON file and return OrphanedJson if it's orphaned."""
    base = json_path.stem
    has_m4a = (gwa_dir / f"{base}.m4a").exists()
    has_mp3 = (gwa_dir / f"{base}.mp3").exists()

    if has_m4a or has_mp3:
        return None

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not read {json_path.name}: {e}")
        return None

    reddit_url, post_id = _extract_reddit_info(data.get("urls", []))

    return OrphanedJson(
        path=json_path,
        author=data.get("author", "unknown"),
        title=data.get("title", "unknown"),
        reddit_url=reddit_url,
        post_id=post_id,
    )


def _extract_reddit_info(urls: list[str]) -> tuple[str | None, str | None]:
    """Extract Reddit URL and post ID from list of URLs."""
    for url in urls:
        if "reddit.com" in url and "/comments/" in url:
            match = re.search(r"/comments/([a-z0-9]+)/", url)
            post_id = match.group(1) if match else None
            return url, post_id
    return None, None


def verify_stashapp_import(stash: StashInterface, post_id: str) -> bool:
    """Check if a Reddit post has been imported to Stashapp."""
    scenes = stash.find_scenes(
        f={
            "url": {
                "value": "reddit.com/r/",
                "modifier": "INCLUDES",
            },
            "AND": {
                "url": {
                    "value": f"/comments/{post_id}/",
                    "modifier": "INCLUDES",
                }
            },
        },
        fragment="id",
    )
    return len(scenes) > 0


def verify_orphans(
    orphans: list[OrphanedJson], stash: StashInterface
) -> VerificationResult:
    """Verify orphaned JSON files against Stashapp."""
    with_post_id = [o for o in orphans if o.post_id]
    without_post_id = [o for o in orphans if not o.post_id]

    verified = []
    unverified = []

    print("Verifying imports...")
    for i, orphan in enumerate(with_post_id, 1):
        if i % 10 == 0 or i == len(with_post_id):
            print(f"  Checked {i}/{len(with_post_id)}...", end="\r")

        if verify_stashapp_import(stash, orphan.post_id):
            verified.append(orphan)
        else:
            unverified.append(orphan)

    print()
    return VerificationResult(
        verified=verified, unverified=unverified, without_post_id=without_post_id
    )


def handle_summary(orphans: list[OrphanedJson], result: VerificationResult) -> int:
    """Handle summary mode - show counts."""
    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")
    print(f"Total orphaned JSON files: {len(orphans)}")
    print(f"  - Verified in Stashapp:  {len(result.verified)} (safe to delete)")
    print(f"  - Not found in Stashapp: {len(result.unverified)} (needs review)")
    print(f"  - No Reddit post ID:     {len(result.without_post_id)}")
    return 0


def handle_unverified(result: VerificationResult) -> int:
    """Handle unverified mode - list files not found in Stashapp."""
    if not result.unverified:
        print("No unverified orphans found.")
        return 0

    print(f"\n{'=' * 60}")
    print(f"Unverified Orphans ({len(result.unverified)} files)")
    print(f"{'=' * 60}")
    print("These files are NOT found in Stashapp and need manual review:\n")

    for orphan in result.unverified:
        print(f"  {orphan.path.name}")
        print(f"    Author: {orphan.author}")
        print(f"    Post ID: {orphan.post_id}")
        if orphan.reddit_url:
            print(f"    URL: {orphan.reddit_url}")
        print()

    return 0


def handle_verified(result: VerificationResult, dry_run: bool) -> int:
    """Handle verified mode - delete files found in Stashapp."""
    if not result.verified:
        print("No verified orphans to delete.")
        return 0

    print(f"\n{'=' * 60}")
    print(f"Verified Orphans ({len(result.verified)} files)")
    print(f"{'=' * 60}")

    deleted_count = 0
    for orphan in result.verified:
        print(f"  {'[DRY RUN] ' if dry_run else ''}Delete: {orphan.path.name}")

        if not dry_run:
            try:
                orphan.path.unlink()
                deleted_count += 1
            except OSError as e:
                print(f"    Error: {e}")

    print(f"\n{'=' * 60}")
    if dry_run:
        print(f"[DRY RUN] Would delete {len(result.verified)} files.")
        print("Run without --dry-run to actually delete.")
    else:
        print(f"Deleted {deleted_count} files.")

    return 0


def main() -> int:
    args = parse_args()

    if not args.gwa_dir.exists():
        print(f"Error: GWA directory not found: {args.gwa_dir}")
        return 1

    print(f"Scanning for orphaned JSON files in: {args.gwa_dir}")
    orphans = find_orphaned_json_files(args.gwa_dir)

    if not orphans:
        print("No orphaned JSON files found.")
        return 0

    print(f"Found {len(orphans)} orphaned JSON files (no corresponding audio)\n")

    print("Connecting to Stashapp...")
    stash = get_stashapp_client()
    result = verify_orphans(orphans, stash)

    if result.without_post_id:
        print(f"Warning: {len(result.without_post_id)} files have no Reddit post ID")

    if args.mode == "summary":
        return handle_summary(orphans, result)
    if args.mode == "unverified":
        return handle_unverified(result)
    # verified
    return handle_verified(result, args.dry_run)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Cleanup orphaned JSON files from GWA directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  summary     Show counts of orphaned files by category
  verified    Process orphaned files that ARE found in Stashapp (safe to delete)
  unverified  List orphaned files that are NOT found in Stashapp (for review)

Examples:
  # See summary of all orphaned JSON files
  uv run python cleanup_orphaned_json.py --mode summary

  # List unverified orphans for manual review
  uv run python cleanup_orphaned_json.py --mode unverified

  # Dry run for verified orphans
  uv run python cleanup_orphaned_json.py --mode verified --dry-run

  # Actually delete verified orphans
  uv run python cleanup_orphaned_json.py --mode verified
""",
    )
    parser.add_argument(
        "--mode",
        choices=["summary", "verified", "unverified"],
        required=True,
        help="Which category of orphans to handle",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--gwa-dir",
        type=Path,
        default=GWA_DIR,
        help=f"GWA directory (default: {GWA_DIR})",
    )

    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
