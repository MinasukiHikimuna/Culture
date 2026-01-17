#!/usr/bin/env python3
"""
Skip Post Script

Mark Reddit posts as permanently skipped in the tracking system.
This prevents analyze_download_import.py from retrying posts with
permanently unavailable audio sources.

Usage:
    python skip_post.py <post_id> [post_id...] [--reason REASON] [--execute]

By default runs in dry-run mode showing what would be marked.
Use --execute to actually mark the posts.

To undo a skip, use reset_post.py.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import config as aural_config


# Use same data_dir as analyze_download_import.py
DATA_DIR = aural_config.RELEASES_DIR.parent
EXTRACTED_DATA_DIR = aural_config.REDDIT_INDEX_DIR


def load_processed_posts() -> dict:
    """Load the processed posts tracking file."""
    tracking_path = DATA_DIR / "processed_posts.json"
    if tracking_path.exists():
        return json.loads(tracking_path.read_text(encoding="utf-8"))
    return {"posts": {}, "lastUpdated": None}


def save_processed_posts(data: dict) -> None:
    """Save the processed posts tracking file."""
    tracking_path = DATA_DIR / "processed_posts.json"
    data["lastUpdated"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    tracking_path.parent.mkdir(parents=True, exist_ok=True)
    tracking_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def find_source_post_file(post_id: str) -> Path | None:
    """Search aural_data/index/reddit/<author>/<postId>_*.json"""
    if not EXTRACTED_DATA_DIR.exists():
        return None

    for author_dir in EXTRACTED_DATA_DIR.iterdir():
        if not author_dir.is_dir():
            continue

        for f in author_dir.iterdir():
            if (
                f.name.startswith(f"{post_id}_")
                and f.suffix == ".json"
                and "_enriched" not in f.name
            ):
                return f

    return None


def get_post_title(post_file: Path | None) -> str | None:
    """Extract the title from a post file."""
    if not post_file or not post_file.exists():
        return None
    try:
        data = json.loads(post_file.read_text(encoding="utf-8"))
        return data.get("reddit_data", {}).get("title")
    except (OSError, json.JSONDecodeError):
        return None


def get_current_status(post_id: str, processed: dict) -> dict | None:
    """Get current tracking status for a post."""
    return processed.get("posts", {}).get(post_id)


def mark_post_skipped(
    post_id: str, reason: str, processed: dict, dry_run: bool
) -> bool:
    """Mark a post as skipped in the tracking data."""
    action = "Would mark" if dry_run else "Marking"

    current = get_current_status(post_id, processed)
    if current:
        if current.get("stage") == "skipped" and current.get("reason") == reason:
            print(f"  Already marked as skipped with reason: {reason}")
            return False
        if current.get("stashSceneId"):
            print(f"  ⚠️  Post has Stashapp scene ID: {current['stashSceneId']}")
            print("      Use reset_post.py first if you want to skip this post")
            return False

    print(f"  {action} as skipped (reason: {reason})")

    if not dry_run:
        processed["posts"][post_id] = {
            "processedAt": datetime.now(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "releaseId": None,
            "releaseDir": None,
            "stashSceneId": None,
            "audioSourceCount": 0,
            "success": True,
            "stage": "skipped",
            "reason": reason,
        }

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Skip Post - Mark posts as permanently skipped",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Common reasons:
  permanently_broken  - Audio sources are permanently unavailable (default)
  audio_deleted       - Specific audio URLs are dead
  manual_skip         - User chose to skip
  duplicate           - Duplicate of another post

Examples:
  python skip_post.py n3ii7z                          # Show what would be marked
  python skip_post.py n3ii7z --execute                # Actually mark
  python skip_post.py n3ii7z --reason audio_deleted   # Custom reason
  python skip_post.py n3ii7z abc123 --execute         # Multiple posts

To undo a skip:
  python reset_post.py n3ii7z --execute
""",
    )
    parser.add_argument("post_ids", nargs="+", help="Reddit post ID(s) to skip")
    parser.add_argument(
        "--reason",
        default="permanently_broken",
        help="Reason for skipping (default: permanently_broken)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually mark posts (default is dry-run)",
    )

    args = parser.parse_args()
    dry_run = not args.execute

    if dry_run:
        print("DRY RUN - No changes will be made\n")

    processed = load_processed_posts()
    marked_count = 0

    for post_id in args.post_ids:
        source_file = find_source_post_file(post_id)
        title = get_post_title(source_file)

        print(f"\n📋 Post: {post_id}")
        if title:
            # Truncate long titles
            display_title = title[:70] + "..." if len(title) > 70 else title
            print(f"   Title: {display_title}")
        if source_file:
            print(f"   Source: {source_file}")

        if mark_post_skipped(post_id, args.reason, processed, dry_run):
            marked_count += 1

    if not dry_run and marked_count > 0:
        save_processed_posts(processed)
        print(f"\n✅ Marked {marked_count} post(s) as skipped")
    elif dry_run and marked_count > 0:
        print(f"\nWould mark {marked_count} post(s) as skipped")
        print("Run with --execute to apply changes")
    else:
        print("\nNo posts marked")


if __name__ == "__main__":
    main()
