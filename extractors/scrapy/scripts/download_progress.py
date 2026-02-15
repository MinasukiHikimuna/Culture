#!/usr/bin/env python3
"""
Download progress visualization script.

Shows how many releases have videos/galleries available vs downloaded for a given site.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field

import psycopg

DB_URL = "postgresql://ce_admin:gTmtNikmpEGf26Fb@fraktal.piilukko.fi:5434/cultureextractor"


@dataclass
class ReleaseStatus:
    uuid: str
    name: str
    release_date: str
    url: str
    performers: list[str]
    has_video_available: bool
    has_video_downloaded: bool
    has_gallery_available: bool
    has_gallery_downloaded: bool


@dataclass
class DownloadStats:
    site_name: str
    total_releases: int
    has_video_available: int
    has_video_downloaded: int
    has_gallery_available: int
    has_gallery_downloaded: int
    releases: list[ReleaseStatus] = field(default_factory=list)


def get_sites(conn) -> list[tuple[str, str]]:
    """Get all sites from the database."""
    with conn.cursor() as cur:
        cur.execute("SELECT uuid, name FROM sites ORDER BY name")
        return cur.fetchall()


def has_video_file(files: list[dict]) -> bool:
    """Check if any file is a video file."""
    return any(
        f.get("$type") == "AvailableVideoFile"
        or f.get("__type__") == "AvailableVideoFile"
        or f.get("FileType") == "video"
        or f.get("file_type") == "video"
        for f in files
    )


def has_gallery_file(files: list[dict]) -> bool:
    """Check if any file is a gallery zip file."""
    return any(
        f.get("$type") == "AvailableGalleryZipFile"
        or f.get("__type__") == "AvailableGalleryZipFile"
        or (f.get("FileType") == "zip" and f.get("ContentType") == "gallery")
        or (f.get("file_type") == "zip" and f.get("content_type") == "gallery")
        for f in files
    )


def get_download_stats(conn, site_name: str) -> DownloadStats | None:
    """Get download statistics for a specific site."""
    with conn.cursor() as cur:
        # Get site UUID
        cur.execute("SELECT uuid FROM sites WHERE name = %s", (site_name,))
        row = cur.fetchone()
        if not row:
            return None
        site_uuid = row[0]

        # Get all releases with their available_files and performers
        cur.execute(
            """
            SELECT r.uuid, r.name, r.release_date, r.url, r.available_files,
                   (SELECT array_agg(p.name)
                    FROM release_entity_site_performer_entity rp
                    JOIN performers p ON rp.performers_uuid = p.uuid
                    WHERE rp.releases_uuid = r.uuid) as performers
            FROM releases r
            WHERE r.site_uuid = %s
            ORDER BY r.release_date DESC
            """,
            (site_uuid,),
        )
        releases = cur.fetchall()

        # Get all downloads for this site
        cur.execute(
            """
            SELECT d.release_uuid, d.file_type
            FROM downloads d
            JOIN releases r ON d.release_uuid = r.uuid
            WHERE r.site_uuid = %s
            """,
            (site_uuid,),
        )
        downloads = cur.fetchall()

        # Build set of (release_uuid, file_type) for quick lookup
        downloaded = set()
        for release_uuid, file_type in downloads:
            downloaded.add((release_uuid, file_type))

        # Count available and downloaded
        total = len(releases)
        count_video_available = 0
        count_video_downloaded = 0
        count_gallery_available = 0
        count_gallery_downloaded = 0
        release_statuses = []

        for release_uuid, name, release_date, url, available_files, performers in releases:
            files = [] if not available_files else available_files if isinstance(available_files, list) else json.loads(available_files)

            has_video = has_video_file(files)
            has_gallery = has_gallery_file(files)
            video_downloaded = (release_uuid, "video") in downloaded
            gallery_downloaded = (release_uuid, "zip") in downloaded

            if has_video:
                count_video_available += 1
                if video_downloaded:
                    count_video_downloaded += 1

            if has_gallery:
                count_gallery_available += 1
                if gallery_downloaded:
                    count_gallery_downloaded += 1

            release_statuses.append(
                ReleaseStatus(
                    uuid=release_uuid,
                    name=name,
                    release_date=str(release_date),
                    url=url,
                    performers=performers or [],
                    has_video_available=has_video,
                    has_video_downloaded=video_downloaded,
                    has_gallery_available=has_gallery,
                    has_gallery_downloaded=gallery_downloaded,
                )
            )

        return DownloadStats(
            site_name=site_name,
            total_releases=total,
            has_video_available=count_video_available,
            has_video_downloaded=count_video_downloaded,
            has_gallery_available=count_gallery_available,
            has_gallery_downloaded=count_gallery_downloaded,
            releases=release_statuses,
        )


def progress_bar(current: int, total: int, width: int = 30) -> str:
    """Create a text progress bar."""
    if total == 0:
        return f"[{'─' * width}] N/A"

    pct = current / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct * 100:5.1f}%"


def print_release_list(
    releases: list[ReleaseStatus], missing_only: bool = False
) -> None:
    """Print a list of releases with their download status."""
    for r in releases:
        # Determine if this release is missing anything
        missing_video = r.has_video_available and not r.has_video_downloaded
        missing_gallery = r.has_gallery_available and not r.has_gallery_downloaded

        if missing_only and not missing_video and not missing_gallery:
            continue

        # Build status indicators - show what's available and download status
        status_parts = []
        if r.has_video_available:
            status_parts.append("Video" + ("" if r.has_video_downloaded else " ✗"))
        if r.has_gallery_available:
            status_parts.append("Gallery" + ("" if r.has_gallery_downloaded else " ✗"))

        status_str = f"[{', '.join(status_parts)}]" if status_parts else "[None]"

        performers_str = ", ".join(r.performers) if r.performers else ""
        print(f"  {r.release_date}  {status_str}  {r.name} ({r.uuid})")
        if performers_str:
            print(f"      {performers_str}")
        print(f"      {r.url}")
        print()


def print_stats(
    stats: DownloadStats, show_releases: bool = False, missing_only: bool = False
) -> None:
    """Print download statistics with progress bars."""
    if show_releases:
        print(f"\n{'=' * 70}")
        print(f"  Releases for {stats.site_name}")
        print(f"{'=' * 70}")
        print()
        print_release_list(stats.releases, missing_only=missing_only)
        print()

    print(f"{'=' * 60}")
    print(f"  Site: {stats.site_name}")
    print(f"{'=' * 60}")
    print(f"\n  Total releases: {stats.total_releases}\n")

    # Video stats
    print("  Videos:")
    print(f"    Available: {stats.has_video_available:4d} / {stats.total_releases}")
    print(f"    Downloaded: {stats.has_video_downloaded:4d} / {stats.has_video_available}")
    print(
        f"    Progress:  {progress_bar(stats.has_video_downloaded, stats.has_video_available)}"
    )
    print()

    # Gallery stats
    print("  Galleries:")
    print(f"    Available: {stats.has_gallery_available:4d} / {stats.total_releases}")
    print(
        f"    Downloaded: {stats.has_gallery_downloaded:4d} / {stats.has_gallery_available}"
    )
    print(
        f"    Progress:  {progress_bar(stats.has_gallery_downloaded, stats.has_gallery_available)}"
    )
    print()

    # Summary
    video_missing = stats.has_video_available - stats.has_video_downloaded
    gallery_missing = stats.has_gallery_available - stats.has_gallery_downloaded
    print(f"  Missing: {video_missing} videos, {gallery_missing} galleries")
    print()


def main():
    parser = argparse.ArgumentParser(description="Show download progress for a site")
    parser.add_argument("site", nargs="?", help="Site name (e.g., sensual.love)")
    parser.add_argument(
        "--list", "-l", action="store_true", help="List all available sites"
    )
    parser.add_argument(
        "--summary-only",
        "-s",
        action="store_true",
        help="Only show summary, hide release list",
    )
    parser.add_argument(
        "--missing",
        "-m",
        action="store_true",
        help="Only show releases with missing downloads",
    )
    args = parser.parse_args()

    with psycopg.connect(DB_URL) as conn:
        if args.list:
            sites = get_sites(conn)
            print("\nAvailable sites:")
            for _uuid, name in sites:
                print(f"  - {name}")
            print()
            return

        if not args.site:
            parser.print_help()
            sys.exit(1)

        stats = get_download_stats(conn, args.site)
        if not stats:
            print(f"Error: Site '{args.site}' not found")
            print("Use --list to see available sites")
            sys.exit(1)

        show_releases = not args.summary_only
        print_stats(stats, show_releases=show_releases, missing_only=args.missing)


if __name__ == "__main__":
    main()
