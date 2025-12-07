"""Sites-related commands for the CLI."""

from typing import Annotated

import polars as pl
import typer

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    format_sites_table,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)


# Create sites command group
sites_app = typer.Typer(help="Manage Culture Extractor sites")


@sites_app.command("list")
def list_sites(
    only_linked: Annotated[
        bool,
        typer.Option("--only-linked", help="Show only sites linked to Stashapp/StashDB"),
    ] = False,
    only_unlinked: Annotated[
        bool,
        typer.Option("--only-unlinked", help="Show only sites not linked to Stashapp/StashDB"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List all sites in the Culture Extractor database.

    Examples:
        ce sites list              # Display as a table
        ce sites list --json       # Display as JSON
        ce sites list -j           # Short form for JSON output
        ce sites list --only-linked     # Show only linked sites
        ce sites list --only-unlinked   # Show only unlinked sites
    """
    try:
        if only_linked and only_unlinked:
            print_error("Cannot use both --only-linked and --only-unlinked")
            raise typer.Exit(code=1)

        # Get Culture Extractor client
        client = config.get_client()

        # Fetch all sites
        sites_df = client.get_sites()

        # Apply link status filters if requested
        if only_linked or only_unlinked:
            site_uuids = sites_df["ce_sites_uuid"].to_list()
            stashapp_links = []
            stashdb_links = []

            for uuid in site_uuids:
                external_ids = client.get_site_external_ids(uuid)
                stashapp_links.append("stashapp" in external_ids)
                stashdb_links.append("stashdb" in external_ids)

            # Add link status columns
            sites_df = sites_df.with_columns([
                pl.Series("has_stashapp_link", stashapp_links),
                pl.Series("has_stashdb_link", stashdb_links),
            ])

            # Filter based on link status
            if only_linked:
                sites_df = sites_df.filter(
                    (sites_df["has_stashapp_link"]) | (sites_df["has_stashdb_link"])
                )
            elif only_unlinked:
                sites_df = sites_df.filter(
                    (~sites_df["has_stashapp_link"]) & (~sites_df["has_stashdb_link"])
                )

        # Check if any results remain after filtering
        if sites_df.shape[0] == 0:
            link_filter = "linked" if only_linked else "unlinked" if only_unlinked else ""
            msg = f"No {link_filter} sites found" if link_filter else "No sites found"
            print_info(msg)
            raise typer.Exit(code=0)

        # Display results
        count = sites_df.shape[0]
        if json_output:
            print_json(sites_df)
        else:
            table = format_sites_table(sites_df)
            print_table(table)
            print_success(f"Found {count} sites")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch sites: {e}")
        raise typer.Exit(code=1) from e


@sites_app.command("link")
def link_site(
    uuid: Annotated[str, typer.Argument(help="Site UUID to link")],
    stashapp_id: Annotated[
        int | None,
        typer.Option("--stashapp-id", help="Stashapp studio ID"),
    ] = None,
    stashdb_id: Annotated[
        str | None,
        typer.Option("--stashdb-id", help="StashDB studio ID (UUID/GUID)"),
    ] = None,
) -> None:
    """Link a Culture Extractor site to external systems.

    Sets external IDs for a site, allowing you to associate them with
    Stashapp studios, StashDB entries, etc.

    Examples:
        ce sites link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345
        ce sites link 018f1477-f285-726b-9136-21956e3e8b92 --stashdb-id "a1b2c3d4-..."
        ce sites link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345 --stashdb-id "a1b2c3d4-..."
    """
    try:
        # Validate that at least one ID was provided
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        # Get Culture Extractor client
        client = config.get_client()

        # Verify site exists
        site_df = client.get_site_by_uuid(uuid)
        if site_df.shape[0] == 0:
            print_error(f"Site with UUID '{uuid}' not found")
            raise typer.Exit(code=1)

        site_name = site_df["ce_sites_name"][0]

        # Set external IDs
        links = []
        if stashapp_id is not None:
            client.set_site_external_id(uuid, "stashapp", str(stashapp_id))
            links.append(f"Stashapp ID: {stashapp_id}")
        if stashdb_id is not None:
            client.set_site_external_id(uuid, "stashdb", stashdb_id)
            links.append(f"StashDB ID: {stashdb_id}")

        print_success(f"Linked site '{site_name}' to {', '.join(links)}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to link site: {e}")
        raise typer.Exit(code=1) from e
