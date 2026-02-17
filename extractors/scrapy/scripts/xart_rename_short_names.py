#!/usr/bin/env python3
"""Rename all X-Art release short_names to include a -video or -gallery suffix.

This disambiguates releases that exist as both a video and gallery on X-Art's
site (same slug, different content) and makes all short_names consistent.

The suffix is derived from the release URL:
  /members/videos/{slug}    → {slug}-video
  /members/galleries/{slug} → {slug}-gallery

Usage:
    python scripts/xart_rename_short_names.py          # dry run (default)
    python scripts/xart_rename_short_names.py --execute # actually rename
"""

import argparse

import psycopg

DB_URL = "postgresql://ce_admin:gTmtNikmpEGf26Fb@fraktal.piilukko.fi:5434/cultureextractor"


def get_suffix(url: str) -> str:
    if "/galleries/" in url:
        return "-gallery"
    return "-video"


def find_releases_to_rename(conn) -> list[dict]:
    """Find all X-Art releases that need renaming."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT uuid, short_name, url, release_date, name
            FROM releases
            WHERE site_uuid = (SELECT uuid FROM sites WHERE short_name = 'xart')
            ORDER BY short_name, url
            """,
        )
        rows = cur.fetchall()

    to_rename = []
    for uuid, short_name, url, release_date, name in rows:
        suffix = get_suffix(url)

        # Skip if already has the correct suffix
        if short_name.endswith(suffix):
            continue

        new_short_name = short_name + suffix

        to_rename.append({
            "uuid": uuid,
            "old_short_name": short_name,
            "new_short_name": new_short_name,
            "url": url,
            "release_date": release_date,
            "name": name,
        })

    return to_rename


def main():
    parser = argparse.ArgumentParser(description="Rename X-Art release short_names to include type suffix")
    parser.add_argument("--execute", action="store_true", help="Actually rename (default is dry run)")
    args = parser.parse_args()

    with psycopg.connect(DB_URL) as conn:
        releases = find_releases_to_rename(conn)

        if not releases:
            print("No releases need renaming.")
            return

        video_count = sum(1 for r in releases if r["new_short_name"].endswith("-video"))
        gallery_count = sum(1 for r in releases if r["new_short_name"].endswith("-gallery"))

        print(f"{'DRY RUN - ' if not args.execute else ''}{len(releases)} releases to rename:")
        print(f"  {video_count} videos, {gallery_count} galleries\n")

        for r in releases:
            print(f"  {r['old_short_name']}  →  {r['new_short_name']}  ({r['release_date']})")

        if not args.execute:
            print(f"\nDry run complete. {len(releases)} releases would be renamed.")
            print("Run with --execute to actually rename.")
            return

        with conn.cursor() as cur:
            for r in releases:
                cur.execute(
                    "UPDATE releases SET short_name = %s WHERE uuid = %s",
                    (r["new_short_name"], r["uuid"]),
                )
            conn.commit()

        print(f"\nRenamed {len(releases)} releases.")


if __name__ == "__main__":
    main()
