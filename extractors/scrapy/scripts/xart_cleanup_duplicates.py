#!/usr/bin/env python3
"""Delete same-type duplicate X-Art releases that have 0 downloads.

These are Category C duplicates: two releases with the same short_name and same
URL type (both /videos/ or both /galleries/), where one has downloads and the
other has none. The one with 0 downloads is a bug created by the spider
encountering the same release on multiple pagination pages.

Usage:
    python scripts/xart_cleanup_duplicates.py          # dry run (default)
    python scripts/xart_cleanup_duplicates.py --execute # actually delete
"""

import argparse

import psycopg

DB_URL = "postgresql://ce_admin:gTmtNikmpEGf26Fb@fraktal.piilukko.fi:5434/cultureextractor"


def get_url_type(url: str) -> str:
    if "/galleries/" in url:
        return "gallery"
    return "video"


def find_duplicates_to_delete(conn) -> list[dict]:
    """Find Category C duplicates: same short_name, same URL type, one has 0 downloads."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.uuid, r.short_name, r.url, r.release_date, r.name,
                   COUNT(d.uuid) AS download_count
            FROM releases r
            LEFT JOIN downloads d ON d.release_uuid = r.uuid
            WHERE r.site_uuid = (SELECT uuid FROM sites WHERE short_name = 'xart')
            GROUP BY r.uuid, r.short_name, r.url, r.release_date, r.name
            ORDER BY r.short_name, r.url
            """,
        )
        rows = cur.fetchall()

    # Group by short_name
    by_slug: dict[str, list[dict]] = {}
    for uuid, short_name, url, release_date, name, dl_count in rows:
        entry = {
            "uuid": uuid,
            "short_name": short_name,
            "url": url,
            "release_date": release_date,
            "name": name,
            "download_count": dl_count,
            "url_type": get_url_type(url),
        }
        by_slug.setdefault(short_name, []).append(entry)

    to_delete = []
    for _slug, records in sorted(by_slug.items()):
        if len(records) < 2:
            continue

        # Group by URL type within this slug
        by_type: dict[str, list[dict]] = {}
        for r in records:
            by_type.setdefault(r["url_type"], []).append(r)

        # For each URL type group with duplicates, mark the one with 0 downloads
        for _url_type, type_records in by_type.items():
            if len(type_records) < 2:
                continue

            has_downloads = [r for r in type_records if r["download_count"] > 0]
            no_downloads = [r for r in type_records if r["download_count"] == 0]

            if not has_downloads or not no_downloads:
                continue

            to_delete.extend(no_downloads)

    return to_delete


def main():
    parser = argparse.ArgumentParser(description="Delete same-type duplicate X-Art releases with 0 downloads")
    parser.add_argument("--execute", action="store_true", help="Actually delete (default is dry run)")
    args = parser.parse_args()

    with psycopg.connect(DB_URL) as conn:
        duplicates = find_duplicates_to_delete(conn)

        if not duplicates:
            print("No same-type duplicates with 0 downloads found.")
            return

        print(f"{'DRY RUN - ' if not args.execute else ''}Found {len(duplicates)} same-type duplicates to delete:\n")

        for r in duplicates:
            print(f"  {r['short_name']}  ({r['release_date']})  {r['url_type']}")
            print(f"    UUID: {r['uuid']}")
            print(f"    URL:  {r['url']}")
            print(f"    Downloads: {r['download_count']}")
            print()

        if not args.execute:
            print(f"Dry run complete. {len(duplicates)} releases would be deleted.")
            print("Run with --execute to actually delete.")
            return

        with conn.cursor() as cur:
            uuids = [r["uuid"] for r in duplicates]
            cur.execute("DELETE FROM releases WHERE uuid = ANY(%s)", (uuids,))
            conn.commit()

        print(f"Deleted {len(duplicates)} duplicate releases.")


if __name__ == "__main__":
    main()
