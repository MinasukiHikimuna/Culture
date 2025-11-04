"""Import a single ManyVids release into Culture Extractor database.

This script imports ManyVids JSON files into the CE database with:
- Release metadata
- Performer linkage (Ellie Idol)
- Tags creation and linkage
- Cover image download record
- Video metadata download record (from xxhash.json)
"""

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import newnewid
import typer
from rich.console import Console

from culture_cli.modules.ce.utils.config import config


console = Console()
app = typer.Typer()

# Constants
SITE_UUID = "019a4925-594f-74dd-98ec-296b6f695b41"  # ManyVids
PERFORMER_UUID = "019a4ce9-25ed-7649-bf81-bfef6fd416c7"  # Ellie Idol
SOURCE_DIR = Path("/Volumes/Culture Downloads/Ellie Idol Rip")
DEST_BASE_DIR = Path("/Volumes/Ripping/Ellie Idol/Metadata")


def parse_duration(duration_str: str) -> int:
    """Parse duration string like '11:43' to seconds.

    Args:
        duration_str: Duration in format 'MM:SS' or 'HH:MM:SS'

    Returns:
        Duration in seconds
    """
    parts = duration_str.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    return 0


def parse_xxhash_file(xxhash_path: Path) -> dict:
    """Parse xxhash.json file to extract video hashes.

    Args:
        xxhash_path: Path to xxhash.json file

    Returns:
        Dictionary with duration, phash, oshash, md5
    """
    content = xxhash_path.read_text()
    lines = content.strip().split("\n")

    result = {"duration": 0, "phash": "", "oshash": "", "md5": ""}

    for line in lines:
        if line.startswith("Duration:"):
            # Extract duration in seconds from "Duration: 00:11:43 (703)"
            match = re.search(r"\((\d+)\)", line)
            if match:
                result["duration"] = int(match.group(1))
        elif line.startswith("PHash:"):
            result["phash"] = line.split(":")[1].strip()
        elif line.startswith("OSHash:"):
            result["oshash"] = line.split(":")[1].strip()

    return result


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with file_path.open("rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def normalize_name(name: str) -> str:
    """Normalize a name to create short_name.

    Args:
        name: Original name

    Returns:
        Normalized short name (lowercase, alphanumeric)
    """
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def get_or_create_tag(cursor, site_uuid: str, tag_name: str) -> str:
    """Get existing tag or create new one.

    Args:
        cursor: Database cursor
        site_uuid: Site UUID
        tag_name: Tag name/label

    Returns:
        Tag UUID
    """
    short_name = normalize_name(tag_name)

    # Check if tag exists
    cursor.execute(
        """
        SELECT uuid FROM tags
        WHERE site_uuid = %s AND short_name = %s
        """,
        (site_uuid, short_name),
    )

    result = cursor.fetchone()
    if result:
        return str(result[0])

    # Create new tag
    tag_uuid = str(newnewid.uuid7())
    cursor.execute(
        """
        INSERT INTO tags (uuid, site_uuid, name, short_name, url)
        VALUES (%s, %s, %s, %s, NULL)
        """,
        (tag_uuid, site_uuid, tag_name, short_name),
    )

    console.print(f"[green]Created new tag:[/green] {tag_name} ({tag_uuid})")
    return tag_uuid


@app.command()
def import_release(  # noqa: PLR0912, PLR0915
    json_file: str = typer.Argument(..., help="Path to ManyVids JSON file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't commit changes to database"),
) -> None:
    """Import a single ManyVids release into Culture Extractor database.

    Example:
        python import_manyvids_release.py "/Volumes/Culture Downloads/Ellie Idol Rip/Ellie Idol - \\
            2015-09-02 - 80465 - CUM 3 TIMES IN 11 MINUTES WITH CEI - <uuid>.json"
    """
    json_path = Path(json_file)

    if not json_path.exists():
        console.print(f"[red]Error:[/red] File not found: {json_path}")
        raise typer.Exit(1)

    # Read ManyVids JSON
    console.print(f"[cyan]Reading:[/cyan] {json_path.name}")
    with json_path.open() as f:
        mv_data = json.load(f)

    data = mv_data.get("data", {})

    # Extract base filename (without .json extension)
    base_name = json_path.stem

    # Extract UUID from filename (last part after the last hyphen)
    # Format: "Ellie Idol - 2022-03-04 - 3390645 - TITLE - UUID"
    filename_parts = base_name.split(" - ")
    if len(filename_parts) < 2:
        console.print(f"[red]Error:[/red] Cannot parse UUID from filename: {base_name}")
        raise typer.Exit(1)

    release_uuid = filename_parts[-1]  # Last part is the UUID
    console.print(f"[cyan]Extracted release UUID from filename:[/cyan] {release_uuid}")

    # Find corresponding files
    cover_jpg = json_path.with_suffix(".jpg")
    xxhash_json = json_path.parent / f"{base_name}.xxhash.json"

    if not cover_jpg.exists():
        console.print(f"[red]Error:[/red] Cover image not found: {cover_jpg}")
        raise typer.Exit(1)

    console.print(f"[cyan]Found cover image:[/cyan] {cover_jpg.name}")

    # Parse xxhash if exists
    video_hashes = None
    if xxhash_json.exists():
        console.print(f"[cyan]Found xxhash file:[/cyan] {xxhash_json.name}")
        video_hashes = parse_xxhash_file(xxhash_json)
        console.print(f"  Duration: {video_hashes['duration']}s")
        console.print(f"  PHash: {video_hashes['phash']}")
        console.print(f"  OSHash: {video_hashes['oshash']}")

    # Extract release data
    title = data.get("title", "Unknown")
    manyvids_id = data.get("id", "")
    url = f"https://www.manyvids.com{data.get('url', '')}"
    description = data.get("description", "")
    launch_date = data.get("launchDate")
    video_duration = data.get("videoDuration", "")

    # Parse duration
    duration_seconds = parse_duration(video_duration) if video_duration else -1

    # Use ManyVids ID as short_name
    short_name = manyvids_id

    console.print("\n[bold]Release Details:[/bold]")
    console.print(f"  Title: {title}")
    console.print(f"  ManyVids ID: {manyvids_id}")
    console.print(f"  URL: {url}")
    console.print(f"  Duration: {duration_seconds}s")
    console.print(f"  Launch Date: {launch_date}")
    console.print(f"  Description: {description[:100]}...")

    # Check if release already exists in database (before doing file operations)
    client = config.get_client()
    cursor = client.connection.cursor()
    cursor.execute(
        "SELECT uuid FROM releases WHERE uuid = %s",
        (release_uuid,),
    )
    existing = cursor.fetchone()
    if existing:
        console.print(f"\n[yellow]⚠ Release already exists:[/yellow] {release_uuid}")
        console.print(f"[yellow]Skipping import.[/yellow]")
        cursor.close()
        raise typer.Exit(0)
    cursor.close()

    # Build available_files JSON
    available_files = [
        {
            "$type": "AvailableVideoFile",
            "FileType": "video",
            "ContentType": "scene",
            "Variant": data.get("resolution", "HD"),
            "Url": url,
            "ResolutionWidth": data.get("width", -1),
            "ResolutionHeight": data.get("height", -1),
            "FileSize": -1,
            "Fps": -1,
            "Codec": "",
        },
        {
            "$type": "AvailableImageFile",
            "FileType": "image",
            "ContentType": "cover",
            "Variant": "",
            "Url": data.get("screenshot", ""),
            "ResolutionWidth": -1,
            "ResolutionHeight": -1,
            "FileSize": -1,
        },
    ]

    # Create metadata directory
    metadata_dir = DEST_BASE_DIR / release_uuid
    if not dry_run:
        metadata_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]Created directory:[/green] {metadata_dir}")
    else:
        console.print(f"[yellow]Would create directory:[/yellow] {metadata_dir}")

    # Copy cover image
    dest_cover = metadata_dir / "cover.jpg"
    if not dry_run:
        shutil.copy2(cover_jpg, dest_cover)
        console.print(f"[green]Copied cover image to:[/green] {dest_cover}")
    else:
        console.print(f"[yellow]Would copy:[/yellow] {cover_jpg} -> {dest_cover}")

    # Calculate SHA256
    cover_sha256 = calculate_sha256(cover_jpg)
    console.print(f"[cyan]Cover SHA256:[/cyan] {cover_sha256}")

    # Get database client (reuse existing client)
    cursor = client.connection.cursor()

    try:
        # Insert release
        console.print("\n[bold]Inserting release into database...[/bold]")
        cursor.execute(
            """
            INSERT INTO releases (
                uuid, site_uuid, sub_site_uuid, name, short_name, url,
                release_date, description, duration, json_document, available_files,
                created, last_updated
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                release_uuid,
                SITE_UUID,
                None,
                title,
                short_name,
                url,
                launch_date,
                description,
                duration_seconds,
                json.dumps(data),
                json.dumps(available_files),
            ),
        )
        console.print("[green]✓ Inserted release[/green]")

        # Link performer
        cursor.execute(
            """
            INSERT INTO release_entity_site_performer_entity (releases_uuid, performers_uuid)
            VALUES (%s, %s)
            """,
            (release_uuid, PERFORMER_UUID),
        )
        console.print("[green]✓ Linked performer (Ellie Idol)[/green]")

        # Process tags
        tag_list = data.get("tagList", [])
        console.print(f"\n[bold]Processing {len(tag_list)} tags...[/bold]")

        for tag_item in tag_list:
            tag_label = tag_item.get("label", "")
            if not tag_label:
                continue

            tag_uuid = get_or_create_tag(cursor, SITE_UUID, tag_label)

            # Link tag to release
            cursor.execute(
                """
                INSERT INTO release_entity_site_tag_entity (releases_uuid, tags_uuid)
                VALUES (%s, %s)
                """,
                (release_uuid, tag_uuid),
            )
            console.print(f"  [green]✓ Linked tag:[/green] {tag_label}")

        # Create download record for cover image
        console.print("\n[bold]Creating download records...[/bold]")

        download_uuid = str(newnewid.uuid7())
        cursor.execute(
            """
            INSERT INTO downloads (
                uuid, release_uuid, file_type, content_type, variant,
                original_filename, saved_filename, downloaded_at,
                available_file, file_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                download_uuid,
                release_uuid,
                "image",
                "cover",
                "",
                cover_jpg.name,
                "cover.jpg",
                datetime.fromtimestamp(cover_jpg.stat().st_mtime, tz=UTC),
                json.dumps(available_files[1]),  # Cover image from available_files
                json.dumps({"$type": "ImageFileMetadata", "sha256Sum": cover_sha256}),
            ),
        )
        console.print("[green]✓ Created cover image download record[/green]")

        # Create download record for video (metadata only)
        if video_hashes:
            # Construct expected video filename from base_name
            video_filename = f"{base_name}.mp4"

            video_download_uuid = str(newnewid.uuid7())
            cursor.execute(
                """
                INSERT INTO downloads (
                    uuid, release_uuid, file_type, content_type, variant,
                    original_filename, saved_filename, downloaded_at,
                    available_file, file_metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
                """,
                (
                    video_download_uuid,
                    release_uuid,
                    "video",
                    "scene",
                    data.get("resolution", "HD"),
                    video_filename,
                    video_filename,  # saved_filename same as original_filename
                    json.dumps(available_files[0]),  # Video from available_files
                    json.dumps({
                        "$type": "VideoHashes",
                        "duration": video_hashes["duration"],
                        "phash": video_hashes["phash"],
                        "oshash": video_hashes["oshash"],
                        "md5": video_hashes.get("md5", ""),
                    }),
                ),
            )
            console.print(f"[green]✓ Created video metadata download record[/green] ({video_filename})")

        if dry_run:
            console.print("\n[yellow]DRY RUN - Rolling back transaction[/yellow]")
            client.connection.rollback()
        else:
            client.connection.commit()
            console.print(f"\n[bold green]✓ Successfully imported release {release_uuid}![/bold green]")
            console.print(f"[cyan]View in CE:[/cyan] ce releases show {release_uuid}")

    except Exception as e:
        client.connection.rollback()
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise
    finally:
        cursor.close()


if __name__ == "__main__":
    app()
