"""Performers-related commands for the CLI."""


import typer
from typing import Annotated

from ce_cli.utils.config import config
from ce_cli.utils.formatters import (
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
    """
    try:
        # Get Culture Extractor client
        client = config.get_client()

        # Determine if we're querying by site or all sites
        if site:
            # Site-specific query
            sites_df = client.get_sites()

            # Check if it's a UUID or short name
            site_match = sites_df.filter(
                (sites_df["ce_sites_short_name"] == site)
                | (sites_df["ce_sites_uuid"] == site)
                | (sites_df["ce_sites_name"] == site)
            )

            if site_match.shape[0] == 0:
                print_error(f"Site '{site}' not found")
                print_info("To see available sites, run: ce sites list")
                raise typer.Exit(code=1)

            site_uuid = site_match["ce_sites_uuid"][0]
            site_name = site_match["ce_sites_name"][0]

            # Fetch performers for the site
            filter_msg = f" matching '{name}'" if name else ""
            print_info(f"Fetching performers from '{site_name}'{filter_msg}...")

            performers_df = client.get_performers(site_uuid, name_filter=name)
        else:
            # All sites query
            if not name:
                print_error("When querying across all sites, --name filter is required to avoid overwhelming results")
                print_info("Use --name to search for a specific performer, or use --site to browse a specific site")
                raise typer.Exit(code=1)

            filter_msg = f" matching '{name}'"
            print_info(f"Searching performers across all sites{filter_msg}...")

            performers_df = client.get_performers_all(name_filter=name)

        if performers_df.shape[0] == 0:
            msg = "No performers found"
            if site:
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
            # When showing all sites, include site column in table
            table = format_performers_table(performers_df, site_name if site else None)
            print_table(table)

            filter_msg = ""
            if name:
                filter_msg = f" matching '{name}'"
            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {count} performer(s){filter_msg}{limit_msg}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to fetch performers: {e}")
        raise typer.Exit(code=1)


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
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to fetch performer: {e}")
        raise typer.Exit(code=1)


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
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to link performer: {e}")
        raise typer.Exit(code=1)
