#!/usr/bin/env python3
"""
Reset Deleted Posts Script

Finds posts that were incorrectly marked as processed (with reason 'other_post_type'
or 'no_audio_urls') but actually have deleted/removed Reddit content, and removes
them from processed_posts.json so they can be properly handled.

Usage:
    uv run python reset_deleted_posts.py              # Dry run - show what would be reset
    uv run python reset_deleted_posts.py --execute    # Actually reset the posts
"""

import argparse
import json
from pathlib import Path

DATA_DIR = Path("data")
EXTRACTED_DATA_DIR = Path("extracted_data/reddit")


def find_incorrectly_processed_posts() -> list[dict]:
    """
    Find posts marked as processed with 'other_post_type' or 'no_audio_urls'
    that actually have [removed] or [deleted] selftext.
    """
    processed_path = DATA_DIR / "processed_posts.json"
    if not processed_path.exists():
        print("Error: processed_posts.json not found")
        return []

    processed = json.loads(processed_path.read_text(encoding="utf-8"))
    problematic = []

    for post_id, record in processed.get("posts", {}).items():
        reason = record.get("reason", "")
        if reason not in ("other_post_type", "no_audio_urls"):
            continue

        # Find the Reddit JSON file
        found = list(EXTRACTED_DATA_DIR.rglob(f"{post_id}_*.json"))
        if not found:
            found = list(EXTRACTED_DATA_DIR.rglob(f"{post_id}.json"))

        if not found:
            continue

        # Filter out enriched files
        found = [f for f in found if "_enriched" not in f.name]
        if not found:
            continue

        try:
            post_data = json.loads(found[0].read_text(encoding="utf-8"))
            reddit_data = post_data.get("reddit_data", {})
            selftext = reddit_data.get("selftext", "")
            title = reddit_data.get("title", "")

            if selftext in ("[removed]", "[deleted]"):
                problematic.append({
                    "post_id": post_id,
                    "reason": reason,
                    "selftext": selftext,
                    "title": title[:60] + "..." if len(title) > 60 else title,
                    "file": found[0],
                })
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return problematic


def reset_posts(post_ids: list[str], dry_run: bool) -> int:
    """Remove posts from processed_posts.json."""
    processed_path = DATA_DIR / "processed_posts.json"
    processed = json.loads(processed_path.read_text(encoding="utf-8"))

    count = 0
    for post_id in post_ids:
        if post_id in processed.get("posts", {}):
            if not dry_run:
                del processed["posts"][post_id]
            count += 1

    if not dry_run and count > 0:
        processed_path.write_text(
            json.dumps(processed, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Reset incorrectly processed deleted posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script finds posts that were marked as 'other_post_type' or 'no_audio_urls'
but actually have [removed] or [deleted] selftext. These posts were incorrectly
classified because the LLM couldn't analyze the deleted content.

After resetting, the new detection logic will properly identify them as
'content_deleted' and keep legacy files for manual curation.

Examples:
  uv run python reset_deleted_posts.py              # Show what would be reset
  uv run python reset_deleted_posts.py --execute    # Actually reset
""",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually reset posts (default is dry-run)",
    )

    args = parser.parse_args()
    dry_run = not args.execute

    print("Scanning for incorrectly processed posts...\n")
    problematic = find_incorrectly_processed_posts()

    if not problematic:
        print("No incorrectly processed posts found.")
        return 0

    print(f"Found {len(problematic)} posts incorrectly marked as processed:\n")
    for p in problematic:
        print(f"  {p['post_id']}: {p['reason']}")
        print(f"    selftext: {p['selftext']}")
        print(f"    title: {p['title']}")
        print()

    if dry_run:
        print("=" * 60)
        print("DRY RUN - No changes made")
        print("=" * 60)
        print(f"\nWould reset {len(problematic)} posts from processed_posts.json")
        print("\nRun with --execute to apply changes")
    else:
        post_ids = [p["post_id"] for p in problematic]
        count = reset_posts(post_ids, dry_run=False)
        print("=" * 60)
        print(f"Reset {count} posts from processed_posts.json")
        print("=" * 60)
        print("\nThese posts will now be properly detected as 'content_deleted'")
        print("when re-processed, and legacy files will be kept for manual curation.")

    return 0


if __name__ == "__main__":
    exit(main())
