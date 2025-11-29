"""Releases-related commands for the CLI."""

import os
import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    format_release_detail,
    format_releases_table,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
    print_warning,
)


# Create releases command group
releases_app = typer.Typer(help="Manage Culture Extractor releases")


def _resolve_site_for_releases(client, site: str) -> tuple[str, str]:
    """Resolve site identifier to UUID and name.

    Returns:
        Tuple of (site_uuid, site_name)
    """
    sites_df = client.get_sites()
    site_match = sites_df.filter(
        (sites_df["ce_sites_short_name"] == site)
        | (sites_df["ce_sites_uuid"] == site)
        | (sites_df["ce_sites_name"] == site)
    )

    if site_match.shape[0] == 0:
        print_error(f"Site '{site}' not found")
        print_info("To see available sites, run: ce sites list")
        raise typer.Exit(code=1)

    return site_match["ce_sites_uuid"][0], site_match["ce_sites_name"][0]


def _resolve_tag_for_releases(client, site: str, site_uuid: str, site_name: str, tag: str) -> tuple[str, str]:
    """Resolve tag identifier to UUID and name for a given site.

    Returns:
        Tuple of (tag_uuid, tag_name)
    """
    tags_df = client.get_tags(site_uuid)
    tag_match = tags_df.filter(
        (tags_df["ce_tags_name"] == tag)
        | (tags_df["ce_tags_uuid"] == tag)
        | (tags_df["ce_tags_short_name"] == tag)
    )

    if tag_match.shape[0] == 0:
        print_error(f"Tag '{tag}' not found for site '{site_name}'")
        print_info(f"To see available tags, run: ce tags list --site {site}")
        raise typer.Exit(code=1)

    return tag_match["ce_tags_uuid"][0], tag_match["ce_tags_name"][0]


def _resolve_performer_for_releases(
    client, site: str, site_uuid: str, site_name: str, performer: str
) -> tuple[str, str]:
    """Resolve performer identifier to UUID and name for a given site.

    Returns:
        Tuple of (performer_uuid, performer_name)
    """
    performers_df = client.get_performers(site_uuid)
    performer_match = performers_df.filter(
        (performers_df["ce_performers_name"] == performer)
        | (performers_df["ce_performers_uuid"] == performer)
        | (performers_df["ce_performers_short_name"] == performer)
    )

    if performer_match.shape[0] == 0:
        print_error(f"Performer '{performer}' not found for site '{site_name}'")
        print_info(f"To see available performers, run: ce performers list --site {site}")
        raise typer.Exit(code=1)

    return performer_match["ce_performers_uuid"][0], performer_match["ce_performers_name"][0]


@releases_app.command("list")
def list_releases(
    site: Annotated[
        str | None,
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", "-t", help="Filter by tag (tag name or UUID)"),
    ] = None,
    performer: Annotated[
        str | None,
        typer.Option("--performer", "-p", help="Filter by performer (performer name or UUID)"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results (default: all)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List releases from the Culture Extractor database.

    A release represents a scene/content item regardless of whether it has been downloaded.

    Examples:
        ce releases list --site meanawolf                      # List all Meana Wolf releases
        ce releases list --site meanawolf --limit 20           # Show first 20 releases
        ce releases list --site meanawolf --tag "pov"          # Filter by tag
        ce releases list --site meanawolf --performer "name"   # Filter by performer
        ce releases list --site meanawolf --json               # JSON output
    """
    try:
        client = config.get_client()

        if not site:
            print_error("Site filter is required. Use --site <site_name> or --site <uuid>")
            print_info("To see available sites, run: ce sites list")
            raise typer.Exit(code=1)

        site_uuid, site_name = _resolve_site_for_releases(client, site)

        tag_uuid = None
        tag_name = None
        if tag:
            tag_uuid, tag_name = _resolve_tag_for_releases(client, site, site_uuid, site_name, tag)

        performer_uuid = None
        performer_name = None
        if performer:
            performer_uuid, performer_name = _resolve_performer_for_releases(
                client, site, site_uuid, site_name, performer
            )

        filter_parts = []
        if tag_name:
            filter_parts.append(f"tag '{tag_name}'")
        if performer_name:
            filter_parts.append(f"performer '{performer_name}'")
        filter_msg = f" with {' and '.join(filter_parts)}" if filter_parts else ""
        print_info(f"Fetching releases from '{site_name}'{filter_msg}...")

        releases_df = client.get_releases(site_uuid, tag_uuid=tag_uuid, performer_uuid=performer_uuid)

        if releases_df.shape[0] == 0:
            msg = f"No releases found for site '{site_name}'"
            if filter_msg:
                msg += filter_msg
            print_info(msg)
            raise typer.Exit(code=0)

        if limit and limit > 0:
            releases_df = releases_df.head(limit)

        count = releases_df.shape[0]
        if json_output:
            print_json(releases_df)
        else:
            table = format_releases_table(releases_df, site_name)
            print_table(table)
            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {count} release(s){filter_msg}{limit_msg}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch releases: {e}")
        raise typer.Exit(code=1) from e


@releases_app.command("show")
def show_release(
    uuid: Annotated[str, typer.Argument(help="Release UUID to display")],
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of formatted view"),
    ] = False,
) -> None:
    """Show detailed information about a specific release.

    Examples:
        ce releases show 018f1477-f285-726b-9136-21956e3e8b92
        ce releases show 018f1477-f285-726b-9136-21956e3e8b92 --json
    """
    try:
        # Get Culture Extractor client
        client = config.get_client()

        # Get the release by UUID
        release_df = client.get_release_by_uuid(uuid)

        if release_df.shape[0] == 0:
            print_error(f"Release with UUID '{uuid}' not found")
            raise typer.Exit(code=1)

        # Get external IDs
        external_ids = client.get_release_external_ids(uuid)

        # Get performers for this release
        performers_df = client.get_release_performers(uuid)

        # Get tags for this release
        tags_df = client.get_release_tags(uuid)

        # Get downloads for this release
        downloads_df = client.get_release_downloads(uuid)

        if json_output:
            # Combine release data with external IDs, performers, tags, and downloads
            release_dict = release_df.to_dicts()[0]
            release_dict["external_ids"] = external_ids
            release_dict["performers"] = performers_df.to_dicts() if performers_df.shape[0] > 0 else []
            release_dict["tags"] = tags_df.to_dicts() if tags_df.shape[0] > 0 else []
            release_dict["downloads"] = downloads_df.to_dicts() if downloads_df.shape[0] > 0 else []
            print_json(release_dict)
        else:
            # Format as detailed view
            detail = format_release_detail(release_df, external_ids)
            print(detail)

            # Display performers if any
            if performers_df.shape[0] > 0:
                _display_performers_table(performers_df)

            # Display tags if any
            if tags_df.shape[0] > 0:
                _display_tags_table(tags_df)

            # Display downloads if any
            if downloads_df.shape[0] > 0:
                _display_downloads_table(downloads_df)

            print_success(f"Release details for {uuid}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch release: {e}")
        raise typer.Exit(code=1) from e


def _display_performers_table(performers_df) -> None:
    """Display performers in a formatted table."""
    console = Console()
    performer_table = Table(title="Performers", show_header=True, header_style="bold magenta")
    performer_table.add_column("Name", style="green")
    performer_table.add_column("CE UUID", style="cyan")
    performer_table.add_column("Stashapp ID", style="yellow")
    performer_table.add_column("StashDB ID", style="blue")

    for performer in performers_df.iter_rows(named=True):
        performer_table.add_row(
            performer["ce_performers_name"] or "N/A",
            performer["ce_performers_uuid"] or "N/A",
            performer["ce_performers_stashapp_id"] or "Not linked",
            performer["ce_performers_stashdb_id"] or "Not linked",
        )

    console.print(performer_table)
    print()


def _display_tags_table(tags_df) -> None:
    """Display tags in a formatted table."""
    console = Console()
    tags_table = Table(title="Tags", show_header=True, header_style="bold magenta")
    tags_table.add_column("Name", style="green")
    tags_table.add_column("CE UUID", style="cyan")

    for tag in tags_df.iter_rows(named=True):
        tags_table.add_row(
            tag["ce_tags_name"] or "N/A",
            tag["ce_tags_uuid"] or "N/A",
        )

    console.print(tags_table)
    print()


def _display_downloads_table(downloads_df) -> None:
    """Display downloaded files in a formatted table."""
    console = Console()
    downloads_table = Table(title="Downloaded Files", show_header=True, header_style="bold magenta")
    downloads_table.add_column("Filename", style="green")
    downloads_table.add_column("File Type", style="cyan")
    downloads_table.add_column("Content Type", style="yellow")
    downloads_table.add_column("Variant", style="blue")
    downloads_table.add_column("Downloaded At", style="white")

    for download in downloads_df.iter_rows(named=True):
        filename = (
            download["ce_downloads_saved_filename"]
            or download["ce_downloads_original_filename"]
            or "N/A"
        )
        downloaded_at = (
            str(download["ce_downloads_downloaded_at"])
            if download["ce_downloads_downloaded_at"]
            else "N/A"
        )
        downloads_table.add_row(
            filename,
            download["ce_downloads_file_type"] or "N/A",
            download["ce_downloads_content_type"] or "N/A",
            download["ce_downloads_variant"] or "N/A",
            downloaded_at,
        )

    console.print(downloads_table)
    print()


@releases_app.command("link")
def link_release(
    uuid: Annotated[str, typer.Argument(help="Release UUID to link")],
    stashapp_id: Annotated[
        int | None,
        typer.Option("--stashapp-id", help="Stashapp scene ID"),
    ] = None,
    stashdb_id: Annotated[
        str | None,
        typer.Option("--stashdb-id", help="StashDB scene ID (UUID/GUID)"),
    ] = None,
) -> None:
    """Link a Culture Extractor release to external systems.

    Sets external IDs for a release, allowing you to associate them with
    Stashapp scenes, StashDB entries, etc.

    Examples:
        ce releases link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345
        ce releases link 018f1477-f285-726b-9136-21956e3e8b92 --stashdb-id "a1b2c3d4-..."
        ce releases link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345 --stashdb-id "a1b2c3d4-..."
    """
    try:
        # Validate that at least one ID was provided
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        # Get Culture Extractor client
        client = config.get_client()

        # Verify release exists
        release_df = client.get_release_by_uuid(uuid)
        if release_df.shape[0] == 0:
            print_error(f"Release with UUID '{uuid}' not found")
            raise typer.Exit(code=1)

        release_name = release_df["ce_release_name"][0]

        # Set external IDs
        links = []
        if stashapp_id is not None:
            client.set_release_external_id(uuid, "stashapp", str(stashapp_id))
            links.append(f"Stashapp ID: {stashapp_id}")
        if stashdb_id is not None:
            client.set_release_external_id(uuid, "stashdb", stashdb_id)
            links.append(f"StashDB ID: {stashdb_id}")

        print_success(f"Linked release '{release_name}' to {', '.join(links)}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to link release: {e}")
        raise typer.Exit(code=1) from e


@releases_app.command("delete")
def delete_release(
    release_uuid: Annotated[str, typer.Argument(help="Release UUID to delete")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Delete a release from the Culture Extractor database.

    This will permanently delete the release record and all associated data
    (downloads, tags, performers links, external IDs) from the database.
    If CE_METADATA_BASE_PATH is configured, downloaded files will also be deleted.

    Examples:
        ce releases delete 018f1477-f285-726b-9136-21956e3e8b92
        ce releases delete 018f1477-f285-726b-9136-21956e3e8b92 --yes
    """
    try:
        client = config.get_client()

        release_df = client.get_release_by_uuid(release_uuid)
        if release_df.shape[0] == 0:
            print_error(f"Release with UUID '{release_uuid}' not found")
            raise typer.Exit(code=1)

        release_name = release_df["ce_release_name"][0]
        site_name = release_df["ce_site_name"][0]

        if not yes:
            confirmed = _confirm_release_deletion(release_name, site_name, release_uuid)
            if not confirmed:
                print_info("Deletion cancelled")
                raise typer.Exit(code=0)

        result = client.delete_release(release_uuid)

        files_deleted = _delete_release_files(result["site_name"], release_uuid, result["downloads"])

        _print_deletion_summary(result, files_deleted)

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to delete release: {e}")
        raise typer.Exit(code=1) from e


def _confirm_release_deletion(release_name: str, site_name: str, release_uuid: str) -> bool:
    """Prompt user to confirm release deletion."""
    print_warning(f"You are about to delete release '{release_name}' from '{site_name}'")
    print_info(f"UUID: {release_uuid}")
    print_info("This will permanently delete the release and all associated data.")
    return typer.confirm("Are you sure you want to proceed?")


def _delete_release_files(site_name: str, release_uuid: str, downloads: list[dict]) -> int:
    """Delete files from the file system if metadata path is configured."""
    metadata_base_path = os.environ.get("CE_METADATA_BASE_PATH")
    if not metadata_base_path or not downloads:
        return 0

    release_dir = Path(metadata_base_path) / site_name / "Metadata" / release_uuid
    if not release_dir.exists():
        return 0

    files_deleted = sum(1 for _ in release_dir.iterdir() if _.is_file())
    shutil.rmtree(release_dir)
    return files_deleted


def _print_deletion_summary(result: dict, files_deleted: int) -> None:
    """Print summary of what was deleted."""
    print_success(f"Deleted release '{result['release_name']}' from '{result['site_name']}'")
    if result["downloads"]:
        print_info(f"Removed {len(result['downloads'])} download record(s) from database")
    if files_deleted > 0:
        print_info(f"Deleted {files_deleted} file(s) from disk")
