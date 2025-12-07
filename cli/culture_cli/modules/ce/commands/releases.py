"""Releases-related commands for the CLI."""

import os
import shutil
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

from culture_cli.api_client import CultureAPIClient
from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    format_release_detail_from_dict,
    format_releases_table_from_list,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
    print_warning,
)


# Create releases command group
releases_app = typer.Typer(help="Manage Culture Extractor releases")


def _get_api_client() -> CultureAPIClient:
    """Get an API client instance."""
    return CultureAPIClient()


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
    desc: Annotated[
        bool,
        typer.Option("--desc", "-d", help="Sort by release date descending (newest first)"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List releases from the Culture Extractor database.

    A release represents a scene/content item regardless of whether it has been downloaded.
    Results are sorted by release date ascending (oldest first) by default.

    Examples:
        ce releases list --site meanawolf                      # List all Meana Wolf releases
        ce releases list --site meanawolf --limit 20           # Show first 20 releases
        ce releases list --site meanawolf --desc               # Sort newest first
        ce releases list --site meanawolf --tag "pov"          # Filter by tag
        ce releases list --site meanawolf --performer "name"   # Filter by performer
        ce releases list --site meanawolf --json               # JSON output
    """
    try:
        if not site:
            print_error("Site filter is required. Use --site <site_name> or --site <uuid>")
            print_info("To see available sites, run: ce sites list")
            raise typer.Exit(code=1)

        filter_parts = []
        if tag:
            filter_parts.append(f"tag '{tag}'")
        if performer:
            filter_parts.append(f"performer '{performer}'")
        filter_msg = f" with {' and '.join(filter_parts)}" if filter_parts else ""
        print_info(f"Fetching releases from '{site}'{filter_msg}...")

        with _get_api_client() as api:
            releases = api.get_releases(site, tag=tag, performer=performer, limit=limit, desc=desc)

        if not releases:
            msg = f"No releases found for site '{site}'"
            if filter_msg:
                msg += filter_msg
            print_info(msg)
            raise typer.Exit(code=0)

        count = len(releases)
        if json_output:
            print_json(releases)
        else:
            site_name = releases[0]["ce_site_name"] if releases else site
            table = format_releases_table_from_list(releases, site_name)
            print_table(table)
            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {count} release(s){filter_msg}{limit_msg}")

    except httpx.ConnectError:
        print_error("Cannot connect to Culture API. Is the API server running?")
        print_info("Start the API with: cd api && uv run uvicorn api.main:app --port 8000")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
            print_error(detail)
        else:
            detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
            print_error(f"API error: {detail}")
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
        with _get_api_client() as api:
            release = api.get_release(uuid)

        if json_output:
            print_json(release)
        else:
            detail = format_release_detail_from_dict(release)
            print(detail)

            if release.get("performers"):
                _display_performers_table(release["performers"])

            if release.get("tags"):
                _display_tags_table(release["tags"])

            if release.get("downloads"):
                _display_downloads_table(release["downloads"])

            print_success(f"Release details for {uuid}")

    except httpx.ConnectError:
        print_error("Cannot connect to Culture API. Is the API server running?")
        print_info("Start the API with: cd api && uv run uvicorn api.main:app --port 8000")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print_error(f"Release with UUID '{uuid}' not found")
        else:
            detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
            print_error(f"API error: {detail}")
        raise typer.Exit(code=1) from e


def _display_performers_table(performers: list[dict]) -> None:
    """Display performers in a formatted table."""
    console = Console()
    performer_table = Table(title="Performers", show_header=True, header_style="bold magenta")
    performer_table.add_column("Name", style="green")
    performer_table.add_column("CE UUID", style="cyan")
    performer_table.add_column("Stashapp ID", style="yellow")
    performer_table.add_column("StashDB ID", style="blue")

    for performer in performers:
        performer_table.add_row(
            performer.get("ce_performers_name") or "N/A",
            performer.get("ce_performers_uuid") or "N/A",
            performer.get("ce_performers_stashapp_id") or "Not linked",
            performer.get("ce_performers_stashdb_id") or "Not linked",
        )

    console.print(performer_table)
    print()


def _display_tags_table(tags: list[dict]) -> None:
    """Display tags in a formatted table."""
    console = Console()
    tags_table = Table(title="Tags", show_header=True, header_style="bold magenta")
    tags_table.add_column("Name", style="green")
    tags_table.add_column("CE UUID", style="cyan")

    for tag in tags:
        tags_table.add_row(
            tag.get("ce_tags_name") or "N/A",
            tag.get("ce_tags_uuid") or "N/A",
        )

    console.print(tags_table)
    print()


def _display_downloads_table(downloads: list[dict]) -> None:
    """Display downloaded files in a formatted table."""
    console = Console()
    downloads_table = Table(title="Downloaded Files", show_header=True, header_style="bold magenta")
    downloads_table.add_column("Filename", style="green")
    downloads_table.add_column("File Type", style="cyan")
    downloads_table.add_column("Content Type", style="yellow")
    downloads_table.add_column("Variant", style="blue")
    downloads_table.add_column("Downloaded At", style="white")

    for download in downloads:
        filename = (
            download.get("ce_downloads_saved_filename")
            or download.get("ce_downloads_original_filename")
            or "N/A"
        )
        downloaded_at = download.get("ce_downloads_downloaded_at") or "N/A"
        downloads_table.add_row(
            filename,
            download.get("ce_downloads_file_type") or "N/A",
            download.get("ce_downloads_content_type") or "N/A",
            download.get("ce_downloads_variant") or "N/A",
            str(downloaded_at),
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
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        with _get_api_client() as api:
            release = api.get_release(uuid)
            release_name = release["ce_release_name"]

            links = []
            if stashapp_id is not None:
                api.link_release(uuid, "stashapp", str(stashapp_id))
                links.append(f"Stashapp ID: {stashapp_id}")
            if stashdb_id is not None:
                api.link_release(uuid, "stashdb", stashdb_id)
                links.append(f"StashDB ID: {stashdb_id}")

            print_success(f"Linked release '{release_name}' to {', '.join(links)}")

    except httpx.ConnectError:
        print_error("Cannot connect to Culture API. Is the API server running?")
        print_info("Start the API with: cd api && uv run uvicorn api.main:app --port 8000")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print_error(f"Release with UUID '{uuid}' not found")
        else:
            detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
            print_error(f"API error: {detail}")
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
    # Delete still uses direct database client since it involves file operations
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
