#!/usr/bin/env python3
"""
Patreon Importer - Import Patreon audio files to Stashapp.

Converts WAV files to FLAC, wraps in MP4 with creator logo,
and imports to Stashapp with metadata from Patreon JSON exports.

Usage:
    uv run python patreon_importer.py <patreon_folder> --post-id <id>
    uv run python patreon_importer.py <patreon_folder> --list

Examples:
    # List all available posts
    uv run python patreon_importer.py "/path/to/Patreon - Creator/" --list

    # Import a specific post
    uv run python patreon_importer.py "/path/to/Patreon - Creator/" --post-id 109951629
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import oshash
from config import STASH_OUTPUT_DIR, local_path_to_windows
from stashapp_importer import (
    StashappClient,
    compute_file_sha256,
    convert_audio_to_video,
    extract_tags_from_title,
    match_tags_with_stash,
)


def load_patreon_metadata(directory: Path) -> tuple[dict, dict]:
    """Load all JSON files and build lookup dictionaries.

    Returns:
        posts: dict mapping post_id -> post data
        media: dict mapping media_id -> media data
    """
    posts = {}
    media = {}

    for json_file in directory.glob("*.json"):
        with json_file.open(encoding="utf-8") as f:
            data = json.load(f)

        for post in data.get("data", []):
            posts[post["id"]] = post

        for item in data.get("included", []):
            if item.get("type") == "media":
                media[item["id"]] = item

    return posts, media


def extract_audio_post(post: dict, media: dict) -> dict | None:
    """Extract audio post metadata. Returns None if not an audio post."""
    attrs = post.get("attributes", {})
    if attrs.get("post_type") != "audio_file":
        return None

    post_id = post["id"]

    # Get audio media ID from relationships
    audio_rel = post.get("relationships", {}).get("audio", {}).get("data")
    audio_media_id = audio_rel.get("id") if audio_rel else None

    # Get media details
    audio_media = media.get(audio_media_id, {}) if audio_media_id else {}
    media_attrs = audio_media.get("attributes", {})

    # Extract tags (strip "user_defined;" prefix)
    tag_data = (
        post.get("relationships", {}).get("user_defined_tags", {}).get("data", [])
    )
    tags = [t["id"].replace("user_defined;", "") for t in tag_data]

    # Parse date
    published_at = attrs.get("published_at", "")
    date_str = ""
    if published_at:
        try:
            dt = datetime.fromisoformat(published_at.replace("+00:00", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return {
        "post_id": post_id,
        "title": attrs.get("title", ""),
        "published_at": published_at,
        "date": date_str,
        "teaser": attrs.get("teaser_text", ""),
        "url": attrs.get("url", ""),
        "original_filename": media_attrs.get("file_name", ""),
        "duration_seconds": media_attrs.get("metadata", {}).get("duration_s"),
        "tags": tags,
    }


def convert_wav_to_flac(wav_path: Path, flac_path: Path) -> bool:
    """Convert WAV to FLAC with compression level 8."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(wav_path),
        "-c:a",
        "flac",
        "-compression_level",
        "8",
        str(flac_path),
    ]

    print("  Converting WAV to FLAC...")
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"  ffmpeg error: {e}")
        if e.stderr:
            print(f"  stderr: {e.stderr.decode()[:500]}")
        return False

    return flac_path.exists()


def format_filename(performer: str, date: str, post_id: str, title: str) -> str:
    """Generate Stashapp-compliant filename."""
    # Clean title: remove brackets and special chars
    clean_title = re.sub(r"\[[^\]]+\]", "", title)
    clean_title = re.sub(r"[^\w\s\-']", "", clean_title)
    clean_title = re.sub(r"\s+", " ", clean_title).strip()

    # Truncate if too long
    if len(clean_title) > 80:
        clean_title = clean_title[:80].rsplit(" ", 1)[0]

    return f"{performer} - {date} - {post_id} - {clean_title}.mp4"


def find_logo(directory: Path) -> Path | None:
    """Find logo.png in directory or parent."""
    logo_path = directory.parent / "logo.png"
    if logo_path.exists():
        return logo_path
    logo_path = directory / "logo.png"
    if logo_path.exists():
        return logo_path
    return None


def convert_to_video(
    wav_path: Path, flac_path: Path, mp4_path: Path, logo_path: Path
) -> tuple[bool, str]:
    """Convert WAV to FLAC to MP4. Returns (success, audio_sha256)."""
    if not convert_wav_to_flac(wav_path, flac_path):
        return False, ""

    # Compute checksum before wrapping
    audio_sha256 = compute_file_sha256(flac_path)

    if not convert_audio_to_video(
        flac_path, mp4_path, static_image=logo_path, preserve_audio=True
    ):
        flac_path.unlink(missing_ok=True)
        return False, ""

    # Clean up intermediate FLAC
    flac_path.unlink(missing_ok=True)
    return True, audio_sha256


def update_stashapp_scene(
    client: StashappClient,
    scene: dict,
    post_meta: dict,
    performer_name: str,
    studio_name: str,
    audio_sha256: str,
) -> None:
    """Update scene metadata in Stashapp."""
    scene_id = scene["id"]

    performer = client.find_or_create_performer(performer_name)
    studio = client.find_or_create_studio(studio_name)

    all_stash_tags = client.get_all_tags()
    title_tags = extract_tags_from_title(post_meta["title"])
    all_tags = list(set(title_tags + post_meta["tags"]))
    matched_tag_ids = match_tags_with_stash(all_tags, all_stash_tags)

    updates: dict = {
        "title": post_meta["title"],
        "date": post_meta["date"],
        "code": post_meta["post_id"],
        "performer_ids": [performer["id"]],
        "studio_id": studio["id"],
        "urls": [post_meta["url"]] if post_meta["url"] else [],
    }
    if matched_tag_ids:
        updates["tag_ids"] = matched_tag_ids

    # Build details with teaser and all tags in brackets (like Reddit posts)
    details_parts = []
    if post_meta["teaser"]:
        details_parts.append(post_meta["teaser"])
    if all_tags:
        tags_line = " ".join(f"[{tag}]" for tag in all_tags)
        details_parts.append(tags_line)
    if details_parts:
        updates["details"] = "\n\n".join(details_parts)

    client.update_scene(scene_id, updates)
    print("  Updated scene metadata")

    if scene.get("files"):
        file_id = scene["files"][0]["id"]
        client.set_file_fingerprint(file_id, "audio_sha256", audio_sha256)
        print(f"  Set audio fingerprint: {audio_sha256[:16]}...")


def import_post(  # noqa: PLR0911
    directory: Path,
    post_id: str,
    performer_name: str,
    studio_name: str,
    dry_run: bool = False,
) -> bool:
    """Import a single Patreon post to Stashapp."""
    print(f"\n{'=' * 60}")
    print(f"Importing post: {post_id}")
    print("=" * 60)

    # Load and validate metadata
    posts, media = load_patreon_metadata(directory)
    if post_id not in posts:
        print(f"Error: Post {post_id} not found in metadata")
        return False

    post_meta = extract_audio_post(posts[post_id], media)
    if not post_meta:
        print(f"Error: Post {post_id} is not an audio post")
        return False

    print(f"  Title: {post_meta['title']}")
    print(f"  Date: {post_meta['date']}")
    print(f"  Tags: {', '.join(post_meta['tags'])}")

    # Validate required files
    wav_path = directory / f"{post_id}.wav"
    if not wav_path.exists():
        print(f"Error: WAV file not found: {wav_path}")
        return False
    print(f"  WAV file: {wav_path.name}")

    logo_path = find_logo(directory)
    if not logo_path:
        print(f"Error: logo.png not found in {directory.parent} or {directory}")
        return False
    print(f"  Logo: {logo_path}")

    if dry_run:
        print("\n  [DRY RUN] Would perform the following:")
        print(f"    1. Convert {wav_path.name} to FLAC")
        print(f"    2. Wrap FLAC in MP4 with {logo_path.name}")
        print("    3. Import to Stashapp with metadata")
        return True

    if not STASH_OUTPUT_DIR:
        print("Error: STASH_OUTPUT_DIR not configured")
        return False

    # Set up output paths
    flac_path = directory / f"{post_id}.flac"
    output_filename = format_filename(
        performer_name, post_meta["date"], post_id, post_meta["title"]
    )
    performer_dir = STASH_OUTPUT_DIR / performer_name
    performer_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = performer_dir / output_filename

    # Convert audio
    success, audio_sha256 = convert_to_video(wav_path, flac_path, mp4_path, logo_path)
    if not success:
        print("Error: Conversion failed")
        return False
    print(f"  Created: {mp4_path}")

    file_oshash = oshash.oshash(str(mp4_path))

    # Import to Stashapp
    client = StashappClient()
    windows_path = local_path_to_windows(mp4_path)
    print(f"  Scanning: {windows_path}")
    client.trigger_scan([windows_path])

    if not client.wait_for_scan(timeout=60):
        print("  Warning: Scan did not complete within timeout")

    scene = client.find_scene_by_oshash(file_oshash)
    if not scene:
        print("  Error: Scene not found after scan")
        return False
    print(f"  Found scene: {scene['id']}")

    update_stashapp_scene(
        client, scene, post_meta, performer_name, studio_name, audio_sha256
    )

    print(f"\n  Successfully imported: {post_meta['title']}")
    return True


def list_posts(directory: Path):
    """List all audio posts in the directory."""
    posts, media = load_patreon_metadata(directory)

    audio_posts = []
    for post_id, post in posts.items():
        meta = extract_audio_post(post, media)
        if meta:
            wav_exists = (directory / f"{post_id}.wav").exists()
            audio_posts.append({**meta, "wav_exists": wav_exists})

    # Sort by date
    audio_posts.sort(key=lambda x: x.get("published_at", ""))

    print(f"\nFound {len(audio_posts)} audio posts:\n")
    print(f"{'ID':<12} {'Date':<12} {'WAV':<5} Title")
    print("-" * 80)

    for p in audio_posts:
        wav_status = "Yes" if p["wav_exists"] else "No"
        title = p["title"][:50] + "..." if len(p["title"]) > 50 else p["title"]
        print(f"{p['post_id']:<12} {p['date']:<12} {wav_status:<5} {title}")


def main():
    parser = argparse.ArgumentParser(
        description="Import Patreon audio files to Stashapp"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Patreon folder containing JSON metadata and WAV files",
    )
    parser.add_argument(
        "--post-id",
        type=str,
        help="Post ID to import",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available audio posts",
    )
    parser.add_argument(
        "--performer",
        type=str,
        required=True,
        help="Performer name (must match Stashapp)",
    )
    parser.add_argument(
        "--studio",
        type=str,
        default="Patreon",
        help="Studio name (default: Patreon)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )

    args = parser.parse_args()

    # Handle directory - could be the main folder or the JSON subfolder
    directory = args.directory
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory")
        sys.exit(1)

    # Check if this is the parent folder with JSON subfolder
    json_dir = directory / "JSON"
    if json_dir.is_dir():
        directory = json_dir

    if args.list:
        list_posts(directory)
        return

    if not args.post_id:
        print("Error: --post-id is required (or use --list to see available posts)")
        sys.exit(1)

    success = import_post(
        directory,
        args.post_id,
        args.performer,
        args.studio,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
