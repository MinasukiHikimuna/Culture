#!/usr/bin/env python3
"""
Process Legacy GWA Sidecar Files

Batch processes legacy audio files that have JSON sidecar metadata files.
These sidecars contain Reddit URLs that can be used to fetch full post data
and run through the existing import pipeline.

Usage:
    uv run python process_legacy_sidecars.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/"
    uv run python process_legacy_sidecars.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --dry-run
    uv run python process_legacy_sidecars.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --limit 5
"""

import argparse
import json
import re
import sys
from pathlib import Path

from reddit_extractor import RedditExtractor
from analyze_download_import import AnalyzeDownloadImportPipeline


def normalize_reddit_url(url: str) -> str:
    """Normalize Reddit URL to standard format."""
    if not url:
        return url

    # Convert old.reddit.com to www.reddit.com
    url = url.replace("old.reddit.com", "www.reddit.com")

    # Remove trailing ) and / characters
    url = url.rstrip(")/")

    return url


def extract_post_id_from_url(url: str) -> str | None:
    """Extract post ID from Reddit URL."""
    if not url:
        return None

    # Reddit URLs: https://www.reddit.com/r/subreddit/comments/post_id/title/
    match = re.search(r"/comments/([a-z0-9]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def find_legacy_sidecars(directory: Path) -> list[tuple[Path, Path | None]]:
    """
    Find all JSON sidecar files and their corresponding MP4 files.

    Returns list of tuples: (json_path, mp4_path or None)
    """
    sidecars = []

    for json_file in directory.glob("*.json"):
        # Find corresponding MP4 (same name, different extension)
        mp4_file = json_file.with_suffix(".mp4")
        if mp4_file.exists():
            sidecars.append((json_file, mp4_file))
        else:
            # MP4 might not exist, still process the JSON
            sidecars.append((json_file, None))

    return sorted(sidecars, key=lambda x: x[0].name)


def find_extracted_post(author: str, post_id: str, output_dir: Path) -> Path | None:
    """Find the extracted Reddit post JSON file."""
    # Check author directory first
    user_dir = output_dir / author
    if user_dir.exists():
        # Look for files matching post_id_*.json pattern
        for json_file in user_dir.glob(f"{post_id}_*.json"):
            return json_file

        # Also check old format: {post_id}.json
        old_format = user_dir / f"{post_id}.json"
        if old_format.exists():
            return old_format

    # Also check deleted_users directory (for deleted accounts)
    deleted_dir = output_dir / "deleted_users"
    if deleted_dir.exists():
        for json_file in deleted_dir.glob(f"{post_id}_*.json"):
            return json_file

        old_format = deleted_dir / f"{post_id}.json"
        if old_format.exists():
            return old_format

    return None


def process_legacy_sidecars(
    directory: Path,
    dry_run: bool = False,
    limit: int | None = None,
    skip_import: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Process all legacy JSON sidecars in a directory.

    Args:
        directory: Path to legacy GWA directory
        dry_run: If True, only show what would be done
        limit: Maximum number of files to process
        skip_import: If True, skip Stashapp import step
        verbose: If True, show detailed progress

    Returns:
        Summary dict with processed, skipped, failed counts
    """
    results = {
        "processed": [],
        "skipped": [],
        "failed": [],
        "deleted": [],
    }

    # Find all sidecar files
    sidecars = find_legacy_sidecars(directory)
    total = len(sidecars)

    if limit:
        sidecars = sidecars[:limit]

    print(f"\nFound {total} legacy sidecar files")
    if limit:
        print(f"Processing first {limit} files")
    print("=" * 60)

    # Initialize extractors
    reddit_output_dir = Path("extracted_data/reddit")
    extractor = RedditExtractor(str(reddit_output_dir))

    if not dry_run:
        print("Setting up Reddit API connection...")
        extractor.setup_reddit()

    # Initialize pipeline
    pipeline = AnalyzeDownloadImportPipeline({
        "skip_import": skip_import,
        "verbose": verbose,
    })

    for i, (json_path, mp4_path) in enumerate(sidecars):
        progress = f"[{i + 1}/{len(sidecars)}]"
        print(f"\n{progress} Processing: {json_path.name}")

        try:
            # Read sidecar JSON
            sidecar_data = json.loads(json_path.read_text(encoding="utf-8"))

            # Extract Reddit URL (first URL that contains reddit.com)
            urls = sidecar_data.get("urls", [])
            reddit_url = None
            for url in urls:
                if "reddit.com" in url:
                    reddit_url = normalize_reddit_url(url)
                    break

            if not reddit_url:
                print(f"  No Reddit URL found in sidecar")
                results["failed"].append({
                    "file": str(json_path),
                    "error": "No Reddit URL in sidecar",
                })
                continue

            # Extract post ID
            post_id = extract_post_id_from_url(reddit_url)
            if not post_id:
                print(f"  Could not extract post ID from URL: {reddit_url}")
                results["failed"].append({
                    "file": str(json_path),
                    "error": f"Could not extract post ID from: {reddit_url}",
                })
                continue

            author = sidecar_data.get("author", "unknown")

            if dry_run:
                print(f"  Would fetch: {reddit_url}")
                print(f"  Post ID: {post_id}, Author: {author}")
                results["processed"].append({
                    "file": str(json_path),
                    "reddit_url": reddit_url,
                    "post_id": post_id,
                })
                continue

            # Check if already extracted
            existing_post = find_extracted_post(author, post_id, reddit_output_dir)

            if existing_post:
                print(f"  Reddit post already extracted: {existing_post.name}")
                post_json_path = existing_post
            else:
                # Fetch Reddit post data
                print(f"  Fetching Reddit post: {reddit_url}")
                reddit_data = extractor.get_post_data(post_id)

                if not reddit_data:
                    print(f"  Failed to fetch Reddit post (may be deleted)")
                    results["failed"].append({
                        "file": str(json_path),
                        "error": "Failed to fetch Reddit post",
                        "reddit_url": reddit_url,
                    })
                    continue

                # Create enriched entry and save
                enriched_entry = {
                    "post_id": post_id,
                    "reddit_url": reddit_url,
                    "username": reddit_data.get("author", "unknown"),
                    "reddit_data": reddit_data,
                }
                extractor.save_individual_post(enriched_entry)

                # Find the saved file
                actual_author = reddit_data.get("author", author)
                post_json_path = find_extracted_post(actual_author, post_id, reddit_output_dir)

                if not post_json_path:
                    print(f"  Could not find saved post file")
                    results["failed"].append({
                        "file": str(json_path),
                        "error": "Could not find saved post file after extraction",
                    })
                    continue

            # Run the full pipeline
            print(f"  Running import pipeline: {post_json_path.name}")
            result = pipeline.process_post(post_json_path, f"{progress} ")

            if result.get("success"):
                results["processed"].append({
                    "file": str(json_path),
                    "post_json": str(post_json_path),
                    "stash_scene_id": result.get("stashSceneId"),
                })

                # Cleanup legacy files on success
                if result.get("stashSceneId") and not result.get("skipped"):
                    print(f"  Cleaning up legacy files...")

                    # Delete MP4
                    if mp4_path and mp4_path.exists():
                        mp4_path.unlink()
                        print(f"  Deleted: {mp4_path.name}")
                        results["deleted"].append(str(mp4_path))

                    # Delete JSON sidecar
                    if json_path.exists():
                        json_path.unlink()
                        print(f"  Deleted: {json_path.name}")
                        results["deleted"].append(str(json_path))

            elif result.get("skipped"):
                results["skipped"].append({
                    "file": str(json_path),
                    "reason": result.get("reason", "already processed"),
                })
            else:
                results["failed"].append({
                    "file": str(json_path),
                    "error": result.get("error"),
                    "stage": result.get("stage"),
                })

        except Exception as e:
            print(f"  Error: {e}")
            results["failed"].append({
                "file": str(json_path),
                "error": str(e),
            })

    # Print summary
    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")
    print(f"Processed: {len(results['processed'])}")
    print(f"Skipped: {len(results['skipped'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Files deleted: {len(results['deleted'])}")

    if results["failed"]:
        print("\nFailed files:")
        for fail in results["failed"]:
            print(f"  - {Path(fail['file']).name}: {fail.get('error', 'unknown error')}")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process legacy GWA sidecar files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all legacy sidecars
  uv run python process_legacy_sidecars.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/"

  # Dry run to see what would be processed
  uv run python process_legacy_sidecars.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --dry-run

  # Limit to first N files (for testing)
  uv run python process_legacy_sidecars.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --limit 5

  # Process without importing to Stashapp
  uv run python process_legacy_sidecars.py "/Volumes/Culture 1/Aural_Stash_Legacy/GWA/" --skip-import
""",
    )
    parser.add_argument(
        "directory",
        help="Path to legacy GWA directory containing JSON sidecars",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually processing",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of files to process",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Skip Stashapp import step",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress",
    )

    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1

    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}")
        return 1

    try:
        results = process_legacy_sidecars(
            directory,
            dry_run=args.dry_run,
            limit=args.limit,
            skip_import=args.skip_import,
            verbose=args.verbose,
        )

        # Return non-zero if any failures
        return 1 if results["failed"] else 0

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
