#!/usr/bin/env python3
"""
Generate CSV report matching Patreon WAV files to their JSON metadata.

Patreon exports store audio posts with numeric post IDs as filenames.
This script matches WAV files to their metadata from the JSON exports.

Usage:
    uv run python patreon_metadata_report.py /path/to/patreon/folder > report.csv
    uv run python patreon_metadata_report.py /path/to/patreon/folder --output report.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def load_json_files(directory: Path) -> tuple[dict, dict]:
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


def extract_audio_posts(posts: dict, media: dict) -> list[dict]:
    """Extract audio posts with their metadata."""
    audio_posts = []

    for post_id, post in posts.items():
        attrs = post.get("attributes", {})
        if attrs.get("post_type") != "audio_file":
            continue

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

        audio_posts.append(
            {
                "post_id": post_id,
                "title": attrs.get("title", ""),
                "published_at": attrs.get("published_at", ""),
                "teaser": attrs.get("teaser_text", ""),
                "url": attrs.get("url", ""),
                "original_filename": media_attrs.get("file_name", ""),
                "duration_seconds": media_attrs.get("metadata", {}).get("duration_s", ""),
                "tags": "|".join(tags),
            }
        )

    return audio_posts


def generate_report(directory: Path, output_file: Path | None = None):
    """Generate CSV report for the given directory."""
    posts, media = load_json_files(directory)
    audio_posts = extract_audio_posts(posts, media)

    # Build lookup by post_id
    post_lookup = {p["post_id"]: p for p in audio_posts}

    # Find all WAV files
    wav_files = list(directory.glob("*.wav"))
    wav_ids = {f.stem for f in wav_files}

    # All post IDs from metadata
    metadata_ids = set(post_lookup.keys())

    # Combine: files that exist + metadata entries without files
    all_ids = wav_ids | metadata_ids

    rows = []
    for post_id in sorted(all_ids, key=int):
        wav_path = directory / f"{post_id}.wav"
        file_exists = wav_path.exists()

        if post_id in post_lookup:
            row = {
                "file_path": str(wav_path) if file_exists else "",
                "file_exists": file_exists,
                **post_lookup[post_id],
            }
        else:
            # WAV file without metadata (orphan)
            row = {
                "file_path": str(wav_path),
                "file_exists": True,
                "post_id": post_id,
                "title": "",
                "published_at": "",
                "teaser": "",
                "url": "",
                "original_filename": "",
                "duration_seconds": "",
                "tags": "",
            }
        rows.append(row)

    # Output
    fieldnames = [
        "file_path",
        "post_id",
        "title",
        "published_at",
        "teaser",
        "original_filename",
        "duration_seconds",
        "tags",
        "url",
        "file_exists",
    ]

    if output_file:
        with output_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary to stderr
    matched = sum(1 for r in rows if r["file_exists"] and r["title"])
    missing_files = sum(1 for r in rows if not r["file_exists"])
    orphan_files = sum(1 for r in rows if r["file_exists"] and not r["title"])

    print(f"Total entries: {len(rows)}", file=sys.stderr)
    print(f"Matched (file + metadata): {matched}", file=sys.stderr)
    print(f"Missing files (metadata only): {missing_files}", file=sys.stderr)
    print(f"Orphan files (no metadata): {orphan_files}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Generate CSV report matching Patreon WAV files to JSON metadata"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing WAV files and JSON metadata",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output CSV file (default: stdout)",
    )

    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    generate_report(args.directory, args.output)


if __name__ == "__main__":
    main()
