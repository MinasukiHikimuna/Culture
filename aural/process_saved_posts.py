#!/usr/bin/env python3
"""
Process saved posts through the full pipeline.

Workflow:
1. Extract posts from saved_posts/ (read post IDs directly from JSON files)
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

SAVED_POSTS_DIR = Path("saved_posts")
SAVED_POSTS_ARCHIVE_DIR = Path("saved_posts_archived")
EXTRACTED_DATA_DIR = Path("extracted_data")
REDDIT_OUTPUT_DIR = EXTRACTED_DATA_DIR / "reddit"


def get_posts_from_saved_posts() -> dict[str, list[dict]]:
    """
    Scan saved_posts/ and extract posts grouped by username.

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


def run_analyze_download_import(
    users: list[str], posts_by_user: dict[str, list[dict]], dry_run: bool = False
) -> dict:
    """
    Run analyze_download_import.py for each user's extracted data.

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

    for username in sorted(users):
        user_dir = REDDIT_OUTPUT_DIR / username

        if not user_dir.exists():
            print(f"\n[SKIP] {username}: No extracted data in {user_dir}")
            results["skipped"].append(username)
            continue

        # Check if there are any JSON files
        json_files = list(user_dir.glob("*.json"))
        if not json_files:
            print(f"\n[SKIP] {username}: No JSON files in {user_dir}")
            results["skipped"].append(username)
            continue

        cmd = [
            "uv",
            "run",
            "python",
            "analyze_download_import.py",
            str(user_dir),
        ]

        print(f"\n[PROCESS] {username} ({len(json_files)} posts)")
        print(f"Command: {' '.join(cmd)}")

        if dry_run:
            print("[DRY RUN] Skipping execution")
            results["success"].append(username)
            continue

        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                results["success"].append(username)
                # Archive the saved post files for this user
                user_posts = posts_by_user.get(username, [])
                for post in user_posts:
                    post_file = post.get("file")
                    if post_file and post_file.exists():
                        if archive_saved_post(post_file, dry_run):
                            results["archived"] += 1
                            print(f"  Archived: {post_file.name}")
            else:
                results["failed"].append(username)
        except Exception as e:
            print(f"Error processing {username}: {e}", file=sys.stderr)
            results["failed"].append(username)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process saved posts through the full pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all users from saved_posts
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
        help="Comma-separated list of usernames to process (default: all from saved_posts)",
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

    # Stage 1: Get posts from saved_posts
    print(f"{'=' * 60}")
    print("Stage 1: Discovering Posts")
    print(f"{'=' * 60}")

    all_users = get_posts_from_saved_posts()
    if not all_users:
        print("No posts found in saved_posts/", file=sys.stderr)
        return 1

    total_posts = sum(len(posts) for posts in all_users.values())
    print(f"Found {len(all_users)} users with {total_posts} total posts")

    # Filter users if specified
    if args.users:
        filter_users = [u.strip() for u in args.users.split(",")]
        users_to_process = {u: all_users[u] for u in filter_users if u in all_users}
        missing = [u for u in filter_users if u not in all_users]
        if missing:
            print(f"Warning: Users not found in saved_posts: {missing}")
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
