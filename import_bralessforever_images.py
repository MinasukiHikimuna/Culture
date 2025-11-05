#!/usr/bin/env python3
"""
Copy Braless Forever performer images to the standard Ripping location.

This script:
1. Queries all Braless Forever performers from CE database
2. Finds source images in /Volumes/Upload/Braless Forever/Braless Forever/models/{site_uuid}/
3. Copies them to /Volumes/Ripping/Braless Forever/Performers/{ce_uuid}/{ce_uuid}.{ext}

Usage:
    uv run python import_bralessforever_images.py
"""

import shutil
from pathlib import Path

from culture_cli.modules.ce.utils.config import config


def find_source_image(site_uuid: str, source_base: Path) -> Path | None:
    """Find the source image for a performer, checking multiple formats."""
    possible_files = [
        source_base / site_uuid / f"{site_uuid}_avatar.jpg",
        source_base / site_uuid / f"{site_uuid}_avatar.png",
        source_base / site_uuid / f"{site_uuid}.jpg",
        source_base / site_uuid / f"{site_uuid}.png",
    ]

    for image_path in possible_files:
        if image_path.exists():
            return image_path

    return None


def get_bralessforever_site(client):
    """Get Braless Forever site information from database."""
    print("i Fetching Braless Forever site information...")
    sites_df = client.get_sites()

    site_matches = sites_df.filter(
        sites_df["ce_sites_short_name"] == "bralessforever"
    )

    if len(site_matches) == 0:
        print("✗ Could not find Braless Forever site in database")
        return None

    site = site_matches.head(1).to_dicts()[0]
    print(f"✓ Found site: {site['ce_sites_name']} ({site['ce_sites_uuid']})")
    return site


def process_performer(performer, source_base, dest_base, stats):
    """Process a single performer's image."""
    ce_uuid = performer["ce_performers_uuid"]
    site_uuid_short = performer["ce_performers_short_name"]
    name = performer["ce_performers_name"]

    source_image = find_source_image(site_uuid_short, source_base)

    if not source_image:
        print(f"SKIP: {name:30} - No source image found")
        stats["skipped_no_source"] += 1
        stats["missing_performers"].append(name)
        return

    ext = source_image.suffix
    dest_dir = dest_base / ce_uuid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_image = dest_dir / f"{ce_uuid}{ext}"

    if dest_image.exists():
        print(f"EXISTS: {name:30} - Already copied")
        stats["skipped_exists"] += 1
        return

    try:
        shutil.copy2(source_image, dest_image)
        print(f"COPIED: {name:30} - {ce_uuid}{ext}")
        stats["copied"] += 1
    except Exception as e:
        print(f"ERROR: {name:30} - {e}")


def print_summary(total_performers, stats):
    """Print processing summary."""
    print("-" * 80)
    print("\nSummary:")
    print(f"  Total performers: {total_performers}")
    print(f"  Copied: {stats['copied']}")
    print(f"  Already exists: {stats['skipped_exists']}")
    print(f"  Missing source: {stats['skipped_no_source']}")

    if stats["missing_performers"]:
        print("\nPerformers without source images:")
        for name in stats["missing_performers"]:
            print(f"  - {name}")


def main():
    """Copy Braless Forever performer images to standard location."""
    client = config.get_client()
    site = get_bralessforever_site(client)

    if not site:
        return

    print("i Fetching performers from database...")
    performers_df = client.get_performers(site["ce_sites_uuid"])
    total_performers = len(performers_df)
    print(f"✓ Found {total_performers} performer(s)")

    source_base = Path("/Volumes/Upload/Braless Forever/Braless Forever/models")
    dest_base = Path("/Volumes/Ripping/Braless Forever/Performers")

    stats = {
        "copied": 0,
        "skipped_no_source": 0,
        "skipped_exists": 0,
        "missing_performers": [],
    }

    print("\nProcessing performers...")
    print("-" * 80)

    for performer in performers_df.iter_rows(named=True):
        process_performer(performer, source_base, dest_base, stats)

    print_summary(total_performers, stats)


if __name__ == "__main__":
    main()
