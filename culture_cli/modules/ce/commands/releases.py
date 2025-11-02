"""Releases-related commands for the CLI."""


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
)


# Create releases command group
releases_app = typer.Typer(help="Manage Culture Extractor releases")


@releases_app.command("list")
def list_releases(
    site: Annotated[
        str | None,
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
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
        ce releases list --site meanawolf              # List all Meana Wolf releases
        ce releases list --site meanawolf --limit 20   # Show first 20 releases
        ce releases list --site meanawolf --json       # JSON output
    """
    try:
        # Get Culture Extractor client
        client = config.get_client()

        # If no site specified, show error
        if not site:
            print_error("Site filter is required. Use --site <site_name> or --site <uuid>")
            print_info("To see available sites, run: ce sites list")
            raise typer.Exit(code=1)

        # Try to find site by short name or UUID
        sites_df = client.get_sites()

        # Check if it's a UUID or short name
        site_match = sites_df.filter(
            (sites_df["ce_sites_short_name"] == site) |
            (sites_df["ce_sites_uuid"] == site) |
            (sites_df["ce_sites_name"] == site)
        )

        if site_match.shape[0] == 0:
            print_error(f"Site '{site}' not found")
            print_info("To see available sites, run: ce sites list")
            raise typer.Exit(code=1)

        site_uuid = site_match["ce_sites_uuid"][0]
        site_name = site_match["ce_sites_name"][0]

        print_info(f"Fetching releases from '{site_name}'...")

        # Fetch releases for the site
        releases_df = client.get_releases(site_uuid)

        if releases_df.shape[0] == 0:
            print_info(f"No releases found for site '{site_name}'")
            raise typer.Exit(code=0)

        # Apply limit if specified
        if limit and limit > 0:
            releases_df = releases_df.head(limit)

        # Display results
        count = releases_df.shape[0]
        if json_output:
            print_json(releases_df)
        else:
            table = format_releases_table(releases_df, site_name)
            print_table(table)

            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {count} release(s){limit_msg}")

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
