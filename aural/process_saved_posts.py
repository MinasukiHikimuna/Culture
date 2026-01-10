#!/usr/bin/env python3
"""
Process saved posts through the full pipeline.

Workflow:
1. Extract posts from aural_data/sources/reddit_saved/pending/ (read post IDs directly from JSON files)
2. Run reddit_extractor.py for each post ID (batch)
3. Run analyze_download_import.py for each user

Usage:
    uv run python process_saved_posts.py                           # Full pipeline
    uv run python process_saved_posts.py --users Agreeable-Cat-95  # Specific user(s)
    uv run python process_saved_posts.py --dry-run                 # Preview only
    uv run python process_saved_posts.py --extract-only            # Only run extraction
    uv run python process_saved_posts.py --analyze-only            # Only run analysis
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import config as aural_config

SAVED_POSTS_DIR = aural_config.REDDIT_SAVED_PENDING_DIR
SAVED_POSTS_ARCHIVE_DIR = aural_config.REDDIT_SAVED_ARCHIVED_DIR
EXTRACTED_DATA_DIR = aural_config.INDEX_DIR
REDDIT_OUTPUT_DIR = aural_config.REDDIT_INDEX_DIR
PROCESSED_POSTS_FILE = aural_config.RELEASES_DIR.parent / "processed_posts.json"


def load_processed_posts() -> dict:
    """Load processed posts tracking data."""
    try:
        return json.loads(PROCESSED_POSTS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posts": {}, "lastUpdated": None}


def is_post_processed(post_id: str, processed_data: dict) -> bool:
    """Check if a post has already been successfully processed."""
    record = processed_data.get("posts", {}).get(post_id)
    if not record:
        return False
    # Processed if: successful import with scene ID, OR intentionally skipped
    return (
        record.get("success") is True and record.get("stashSceneId") is not None
    ) or (record.get("success") is True and record.get("stage") == "skipped")


def get_posts_from_saved_posts() -> dict[str, list[dict]]:
    """
    Scan reddit_saved/pending/ and extract posts grouped by username.

    Returns:
        Dict mapping username to list of post info dicts with 'id' and 'file' keys
    """
    users: dict[str, list[dict]] = {}

    if not SAVED_POSTS_DIR.exists():
        print(f"Error: {SAVED_POSTS_DIR} directory not found", file=sys.stderr)
        return users

    for file in SAVED_POSTS_DIR.glob("*.json"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            author = data.get("author", "unknown")
            post_id = data.get("id")
            if post_id:
                if author not in users:
                    users[author] = []
                users[author].append({"id": post_id, "file": file})
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read {file}: {e}", file=sys.stderr)

    return users


def post_already_extracted(post_id: str, username: str) -> bool:
    """Check if a post has already been extracted to reddit output directory."""
    user_dir = REDDIT_OUTPUT_DIR / username
    if not user_dir.exists():
        return False
    # Check for any file starting with the post_id
    return any(user_dir.glob(f"{post_id}*.json"))


def run_reddit_extractor_for_posts(
    posts: list[dict], username: str, dry_run: bool = False
) -> dict:
    """
    Run reddit_extractor.py for each post ID.

    Args:
        posts: List of post info dicts with 'id' key
        username: Username for display
        dry_run: If True, only print the commands

    Returns:
        Dict with success/failed/skipped counts
    """
    results = {"success": 0, "failed": 0, "skipped": 0}

    for post in posts:
        post_id = post["id"]

        # Check if already extracted
        if post_already_extracted(post_id, username):
            print(f"  [SKIP] {post_id} - already extracted")
            results["skipped"] += 1
            continue

        cmd = [
            "uv",
            "run",
            "python",
            "reddit_extractor.py",
            post_id,
            "-o",
            str(REDDIT_OUTPUT_DIR),
        ]

        print(f"  [EXTRACT] {post_id}")

        if dry_run:
            results["success"] += 1
            continue

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                results["success"] += 1
            else:
                print(f"    Error: {result.stderr.strip()[:100]}")
                results["failed"] += 1
        except Exception as e:
            print(f"    Error: {e}")
            results["failed"] += 1

    return results


def archive_saved_post(post_file: Path, dry_run: bool = False) -> bool:
    """Move a saved post JSON file to the archive directory."""
    if dry_run:
        return True

    SAVED_POSTS_ARCHIVE_DIR.mkdir(exist_ok=True)
    dest = SAVED_POSTS_ARCHIVE_DIR / post_file.name
    try:
        shutil.move(str(post_file), str(dest))
        return True
    except Exception as e:
        print(f"    Warning: Could not archive {post_file.name}: {e}")
        return False


def find_extracted_post_files(post_ids: list[str], username: str) -> list[Path]:
    """Find the extracted JSON files for specific post IDs."""
    user_dir = REDDIT_OUTPUT_DIR / username
    if not user_dir.exists():
        return []

    found_files = []
    for post_id in post_ids:
        # Check for any file starting with the post_id
        matches = list(user_dir.glob(f"{post_id}*.json"))
        found_files.extend(matches)
    return found_files


def run_analyze_download_import(
    users: list[str], posts_by_user: dict[str, list[dict]], dry_run: bool = False
) -> dict:
    """
    Run analyze_download_import.py for each user's saved posts only.

    Args:
        users: List of usernames to process
        posts_by_user: Dict mapping username to list of post info dicts
        dry_run: If True, only print the commands

    Returns:
        Dict with results per user
    """
    print(f"\n{'=' * 60}")
    print("Stage 3: Analyze, Download, and Import")
    print(f"{'=' * 60}")

    results = {"success": [], "failed": [], "skipped": [], "archived": 0}

    # Load processed posts once for checking already-processed posts
    processed_data = load_processed_posts()

    for username in sorted(users):
        user_posts = posts_by_user.get(username, [])
        if not user_posts:
            print(f"\n[SKIP] {username}: No saved posts")
            results["skipped"].append(username)
            continue

        # Build a mapping from post_id to saved post info
        post_id_to_saved = {p["id"]: p for p in user_posts}

        # Archive already-processed posts first
        posts_to_process = []
        for post in user_posts:
            post_id = post["id"]
            if is_post_processed(post_id, processed_data):
                saved_post_file = post.get("file")
                if saved_post_file and saved_post_file.exists():
                    if archive_saved_post(saved_post_file, dry_run):
                        results["archived"] += 1
                        print(f"  [ALREADY PROCESSED] Archived: {saved_post_file.name}")
            else:
                posts_to_process.append(post)

        # Update user_posts to only include unprocessed posts
        if not posts_to_process:
            print(f"\n[SKIP] {username}: All posts already processed and archived")
            results["success"].append(username)
            continue

        # Find the extracted JSON files for the remaining post IDs only
        post_ids = [p["id"] for p in posts_to_process]
        post_files = find_extracted_post_files(post_ids, username)

        if not post_files:
            print(f"\n[SKIP] {username}: No extracted data found for saved posts")
            results["skipped"].append(username)
            continue

        print(f"\n[PROCESS] {username} ({len(post_files)} posts)")

        if dry_run:
            for pf in post_files:
                print(f"  [DRY RUN] Would process: {pf.name}")
            results["success"].append(username)
            continue

        # Process each post file individually and archive on success
        user_had_success = False
        user_had_failure = False
        for post_file in post_files:
            # Extract post_id from filename (format: {post_id}_*.json)
            post_id = post_file.stem.split("_")[0]

            cmd = [
                "uv",
                "run",
                "python",
                "analyze_download_import.py",
                str(post_file),
            ]
            print(f"  Processing: {post_file.name}")

            try:
                result = subprocess.run(cmd, check=False)
                if result.returncode == 0:
                    user_had_success = True
                    # Archive this specific saved post on success
                    saved_post = post_id_to_saved.get(post_id)
                    if saved_post:
                        saved_post_file = saved_post.get("file")
                        if saved_post_file and saved_post_file.exists():
                            if archive_saved_post(saved_post_file, dry_run):
                                results["archived"] += 1
                                print(f"  Archived: {saved_post_file.name}")
                else:
                    print(f"    Failed to process {post_file.name}")
                    user_had_failure = True
            except Exception as e:
                print(f"    Error: {e}")
                user_had_failure = True

        # Track user-level results (a user can be in both if some posts succeeded and others failed)
        if user_had_success and not user_had_failure:
            results["success"].append(username)
        elif user_had_failure and not user_had_success:
            results["failed"].append(username)
        elif user_had_success and user_had_failure:
            # Partial success - count as success but note in output
            results["success"].append(username)
            print(f"  Note: Some posts for {username} failed but others succeeded")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process saved posts through the full pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all users from reddit_saved/pending
  uv run python process_saved_posts.py

  # Process specific users
  uv run python process_saved_posts.py --users Agreeable-Cat-95,SweetnEvil86

  # Preview what would be processed
  uv run python process_saved_posts.py --dry-run

  # Only run reddit extraction (skip analyze/import)
  uv run python process_saved_posts.py --extract-only

  # Only run analyze/import (skip reddit extraction)
  uv run python process_saved_posts.py --analyze-only
""",
    )
    parser.add_argument(
        "--users",
        help="Comma-separated list of usernames to process (default: all from reddit_saved/pending)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview commands without executing",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only run reddit extraction, skip analyze/import",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only run analyze/import, skip reddit extraction",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of users to process (0 = no limit)",
    )

    args = parser.parse_args()

    # Stage 1: Get posts from reddit_saved/pending
    print(f"{'=' * 60}")
    print("Stage 1: Discovering Posts")
    print(f"{'=' * 60}")

    all_users = get_posts_from_saved_posts()
    if not all_users:
        print("No posts found in reddit_saved/pending/", file=sys.stderr)
        return 1

    total_posts = sum(len(posts) for posts in all_users.values())
    print(f"Found {len(all_users)} users with {total_posts} total posts")

    # Filter users if specified
    if args.users:
        filter_users = [u.strip() for u in args.users.split(",")]
        users_to_process = {u: all_users[u] for u in filter_users if u in all_users}
        missing = [u for u in filter_users if u not in all_users]
        if missing:
            print(f"Warning: Users not found in reddit_saved/pending: {missing}")
        if not users_to_process:
            print("No matching users to process", file=sys.stderr)
            return 1
    else:
        users_to_process = all_users

    # Apply limit if specified
    if args.limit > 0:
        sorted_users = sorted(users_to_process.keys())[:args.limit]
        users_to_process = {u: users_to_process[u] for u in sorted_users}
        print(f"Limiting to first {args.limit} users")

    print(f"Users to process: {len(users_to_process)}")
    for user in sorted(users_to_process.keys()):
        print(f"  - {user} ({len(users_to_process[user])} posts)")

    # Stage 2: Reddit extraction (per post ID)
    extract_totals = {"success": 0, "failed": 0, "skipped": 0}
    if not args.analyze_only:
        print(f"\n{'=' * 60}")
        print("Stage 2: Reddit Extraction")
        print(f"{'=' * 60}")

        for username in sorted(users_to_process.keys()):
            posts = users_to_process[username]
            print(f"\n[{username}] ({len(posts)} posts)")

            results = run_reddit_extractor_for_posts(posts, username, args.dry_run)
            extract_totals["success"] += results["success"]
            extract_totals["failed"] += results["failed"]
            extract_totals["skipped"] += results["skipped"]

        print(f"\nExtraction summary: {extract_totals['success']} extracted, "
              f"{extract_totals['skipped']} skipped, {extract_totals['failed']} failed")

    # Stage 3: Analyze, download, import
    if not args.extract_only:
        results = run_analyze_download_import(
            list(users_to_process.keys()), users_to_process, args.dry_run
        )

        # Summary
        print(f"\n{'=' * 60}")
        print("Analysis Summary")
        print(f"{'=' * 60}")
        print(f"Successful: {len(results['success'])}")
        print(f"Failed: {len(results['failed'])}")
        print(f"Skipped: {len(results['skipped'])}")
        print(f"Archived: {results['archived']}")

        if results["failed"]:
            print("\nFailed users:")
            for user in results["failed"]:
                print(f"  - {user}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
