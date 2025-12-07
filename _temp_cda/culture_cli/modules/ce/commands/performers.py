"""Performers-related commands for the CLI."""


from typing import Annotated

import polars as pl
import typer

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    format_performer_detail,
    format_performers_table,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)


# Create performers command group
performers_app = typer.Typer(help="Manage Culture Extractor performers")


@performers_app.command("list")
def list_performers(
    site: Annotated[
        str | None,
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by performer name (case-insensitive)"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results (useful when querying all sites)"),
    ] = None,
    only_linked: Annotated[
        bool,
        typer.Option("--only-linked", help="Show only performers linked to Stashapp/StashDB"),
    ] = False,
    only_unlinked: Annotated[
        bool,
        typer.Option("--only-unlinked", help="Show only performers not linked to Stashapp/StashDB"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List performers from the Culture Extractor database.

    By default, lists performers across all sites. Use --site to filter by a specific site.
    Use --name to search by performer name. Combine filters as needed.

    Examples:
        ce performers list --name "Jane"                 # Search for Jane across all sites
        ce performers list --site meanawolf              # List all performers from Meana Wolf
        ce performers list -s meanawolf -n "Jane"        # Filter by site and name
        ce performers list -n "Jane" --limit 20          # Limit results to 20
        ce performers list --site meanawolf --json       # JSON output
        ce performers list --site meanawolf --only-unlinked  # Show unlinked performers only
    """
    try:
        if only_linked and only_unlinked:
            print_error("Cannot use both --only-linked and --only-unlinked")
            raise typer.Exit(code=1)

        client = config.get_client()

        # Fetch performers based on filters
        performers_df, site_name = _fetch_performers(client, site, name)

        # Check if any results were found
        if performers_df.shape[0] == 0:
            msg = _build_not_found_message(site_name, name)
            print_info(msg)
            raise typer.Exit(code=0)

        # Enrich with external link status
        performers_df = _enrich_with_link_status(client, performers_df)

        # Apply link status filters
        if only_linked:
            performers_df = performers_df.filter(
                (performers_df["has_stashapp_link"]) | (performers_df["has_stashdb_link"])
            )
        elif only_unlinked:
            performers_df = performers_df.filter(
                (~performers_df["has_stashapp_link"]) & (~performers_df["has_stashdb_link"])
            )

        # Check again after filtering
        if performers_df.shape[0] == 0:
            link_filter = "linked" if only_linked else "unlinked" if only_unlinked else ""
            msg = f"No {link_filter} performers found"
            if site_name:
                msg += f" for site '{site_name}'"
            if name:
                msg += f" matching '{name}'"
            print_info(msg)
            raise typer.Exit(code=0)

        # Apply limit if specified
        if limit and limit > 0:
            performers_df = performers_df.head(limit)

        # Display results
        count = performers_df.shape[0]
        if json_output:
            print_json(performers_df)
        else:
            table = format_performers_table(performers_df, site_name)
            print_table(table)
            print_success(_build_success_message(count, name, limit))

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch performers: {e}")
        raise typer.Exit(code=1) from e


def _fetch_performers(client, site: str | None, name: str | None):
    """Fetch performers based on site and name filters.

    Args:
        client: Culture Extractor client
        site: Optional site identifier
        name: Optional name filter

    Returns:
        Tuple of (performers_df, site_name or None)
    """
    if site:
        site_uuid, site_name = _resolve_site_uuid(client, site)

        filter_msg = f" matching '{name}'" if name else ""
        print_info(f"Fetching performers from '{site_name}'{filter_msg}...")

        performers_df = client.get_performers(site_uuid, name_filter=name)
        return performers_df, site_name
    if not name:
        print_error("When querying across all sites, --name filter is required to avoid overwhelming results")
        print_info("Use --name to search for a specific performer, or use --site to browse a specific site")
        raise ValueError("Name filter required for all-sites query")

    filter_msg = f" matching '{name}'"
    print_info(f"Searching performers across all sites{filter_msg}...")

    performers_df = client.get_performers_all(name_filter=name)
    return performers_df, None


def _resolve_site_uuid(client, site: str) -> tuple[str, str]:
    """Resolve a site identifier (UUID, short name, or name) to UUID and name.

    Args:
        client: Culture Extractor client
        site: Site identifier (UUID, short name, or full name)

    Returns:
        Tuple of (site_uuid, site_name)

    Raises:
        ValueError: If site is not found
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
        raise ValueError(f"Site '{site}' not found")

    return site_match["ce_sites_uuid"][0], site_match["ce_sites_name"][0]


def _enrich_with_link_status(client, performers_df: pl.DataFrame) -> pl.DataFrame:
    """Enrich performers dataframe with external link status.

    Args:
        client: Culture Extractor client
        performers_df: DataFrame with performer information

    Returns:
        DataFrame with added has_stashapp_link and has_stashdb_link columns
    """
    # Get all performer UUIDs
    performer_uuids = performers_df["ce_performers_uuid"].to_list()

    # Fetch external IDs for all performers
    stashapp_links = []
    stashdb_links = []

    for uuid in performer_uuids:
        external_ids = client.get_performer_external_ids(uuid)
        stashapp_links.append("stashapp" in external_ids)
        stashdb_links.append("stashdb" in external_ids)

    # Add columns to dataframe
    performers_df = performers_df.with_columns([
        pl.Series("has_stashapp_link", stashapp_links),
        pl.Series("has_stashdb_link", stashdb_links),
    ])

    return performers_df


def _build_not_found_message(site_name: str | None, name: str | None) -> str:
    """Build a descriptive message when no performers are found."""
    msg = "No performers found"
    if site_name:
        msg += f" for site '{site_name}'"
    if name:
        msg += f" matching '{name}'"
    return msg


def _build_success_message(count: int, name: str | None, limit: int | None) -> str:
    """Build a success message with count and filter information."""
    filter_msg = f" matching '{name}'" if name else ""
    limit_msg = f" (showing first {limit})" if limit else ""
    return f"Found {count} performer(s){filter_msg}{limit_msg}"


@performers_app.command("show")
def show_performer(
    uuid: Annotated[str, typer.Argument(help="Performer UUID to display")],
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of formatted view"),
    ] = False,
) -> None:
    """Show detailed information about a specific performer.

    Examples:
        ce performers show 018f1477-f285-726b-9136-21956e3e8b92
        ce performers show 018f1477-f285-726b-9136-21956e3e8b92 --json
    """
    try:
        # Get Culture Extractor client
        client = config.get_client()

        # Get the performer by UUID
        performer_df = client.get_performer_by_uuid(uuid)

        if performer_df.shape[0] == 0:
            print_error(f"Performer with UUID '{uuid}' not found")
            raise typer.Exit(code=1)

        # Get external IDs
        external_ids = client.get_performer_external_ids(uuid)

        if json_output:
            # Combine performer data with external IDs
            performer_dict = performer_df.to_dicts()[0]
            performer_dict["external_ids"] = external_ids
            print_json(performer_dict)
        else:
            # Format as detailed view
            detail = format_performer_detail(performer_df, external_ids)
            print(detail)
            print_success(f"Performer details for {uuid}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch performer: {e}")
        raise typer.Exit(code=1) from e


@performers_app.command("unmapped")
def list_unmapped_performers(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="Site to check (short name or UUID)"),
    ],
    target_system: Annotated[
        str,
        typer.Option("--target-system", "-t", help="Target system to check for mappings"),
    ] = "stashapp",
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by performer name (case-insensitive)"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List performers from a site that aren't mapped to an external system.

    Shows performers that don't have external IDs for the specified target system
    (default: stashapp). Useful for identifying performers that still need to be
    linked to external systems.

    Examples:
        ce performers unmapped --site meanawolf                        # List unmapped performers for Meana Wolf
        ce performers unmapped -s meanawolf -t stashdb                 # Check for StashDB mappings
        ce performers unmapped -s meanawolf -n "Jane"                  # Filter by name
        ce performers unmapped -s meanawolf --limit 20                 # Limit results
        ce performers unmapped -s meanawolf --json                     # JSON output
    """
    try:
        client = config.get_client()

        # Resolve site UUID
        site_uuid, site_name = _resolve_site_uuid(client, site)

        # Build filter message
        filter_msg = f" matching '{name}'" if name else ""
        print_info(f"Fetching performers from '{site_name}' without '{target_system}' mappings{filter_msg}...")

        # Fetch unmapped performers
        performers_df = client.get_performers_unmapped(
            site_uuid, target_system_name=target_system, name_filter=name
        )

        # Check if any results were found
        if performers_df.shape[0] == 0:
            msg = f"No unmapped performers found for site '{site_name}'"
            if name:
                msg += f" matching '{name}'"
            print_info(msg)
            raise typer.Exit(code=0)

        # Apply limit if specified
        if limit and limit > 0:
            performers_df = performers_df.head(limit)

        # Display results
        count = performers_df.shape[0]
        if json_output:
            print_json(performers_df)
        else:
            table = format_performers_table(performers_df, site_name)
            print_table(table)
            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {count} unmapped performer(s){filter_msg}{limit_msg}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch unmapped performers: {e}")
        raise typer.Exit(code=1) from e


@performers_app.command("link")
def link_performer(
    uuid: Annotated[str, typer.Argument(help="Performer UUID to link")],
    stashapp_id: Annotated[
        int | None,
        typer.Option("--stashapp-id", help="Stashapp performer ID"),
    ] = None,
    stashdb_id: Annotated[
        str | None,
        typer.Option("--stashdb-id", help="StashDB performer ID (UUID/GUID)"),
    ] = None,
) -> None:
    """Link a Culture Extractor performer to external systems.

    Sets external IDs for a performer, allowing you to associate them with
    Stashapp performers, StashDB entries, etc.

    Examples:
        ce performers link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345
        ce performers link 018f1477-f285-726b-9136-21956e3e8b92 --stashdb-id "a1b2c3d4-..."
        ce performers link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345 --stashdb-id "a1b2c3d4-..."
    """
    try:
        # Validate that at least one ID was provided
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        # Get Culture Extractor client
        client = config.get_client()

        # Verify performer exists
        performer_df = client.get_performer_by_uuid(uuid)
        if performer_df.shape[0] == 0:
            print_error(f"Performer with UUID '{uuid}' not found")
            raise typer.Exit(code=1)

        performer_name = performer_df["ce_performers_name"][0]

        # Set external IDs
        links = []
        if stashapp_id is not None:
            client.set_performer_external_id(uuid, "stashapp", str(stashapp_id))
            links.append(f"Stashapp ID: {stashapp_id}")
        if stashdb_id is not None:
            client.set_performer_external_id(uuid, "stashdb", stashdb_id)
            links.append(f"StashDB ID: {stashdb_id}")

        print_success(f"Linked performer '{performer_name}' to {', '.join(links)}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to link performer: {e}")
        raise typer.Exit(code=1) from e
