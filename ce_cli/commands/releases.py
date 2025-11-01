"""Releases-related commands for the CLI."""

from typing import Optional

import typer
from typing_extensions import Annotated

from ce_cli.utils.config import config
from ce_cli.utils.formatters import (
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
        Optional[str],
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
    ] = None,
    limit: Annotated[
        Optional[int],
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
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to fetch releases: {e}")
        raise typer.Exit(code=1)


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

        if json_output:
            print_json(release_df)
        else:
            # Format as detailed view
            from ce_cli.utils.formatters import format_release_detail
            detail = format_release_detail(release_df)
            print(detail)
            print_success(f"Release details for {uuid}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to fetch release: {e}")
        raise typer.Exit(code=1)
