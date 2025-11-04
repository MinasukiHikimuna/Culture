"""Tags-related commands for the CLI."""

from typing import Annotated

import typer

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    format_tags_table,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)


# Create tags command group
tags_app = typer.Typer(help="Manage Culture Extractor tags")


@tags_app.command("list")
def list_tags(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by tag name (case-insensitive)"),
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
    """List tags from a specific site in the Culture Extractor database.

    Use --name to filter by tag name. Tags are retrieved from releases in the site.

    Examples:
        ce tags list --site meanawolf                    # List all tags from Meana Wolf
        ce tags list -s meanawolf -n "pov"               # Filter by name
        ce tags list -s meanawolf --limit 20             # Limit results to 20
        ce tags list --site meanawolf --json             # JSON output
    """
    try:
        client = config.get_client()

        # Resolve site UUID
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

        site_uuid = site_match["ce_sites_uuid"][0]
        site_name = site_match["ce_sites_name"][0]

        filter_msg = f" matching '{name}'" if name else ""
        print_info(f"Fetching tags from '{site_name}'{filter_msg}...")

        # Fetch tags for the site
        tags_df = client.get_tags(site_uuid, name_filter=name)

        if tags_df.shape[0] == 0:
            msg = f"No tags found for site '{site_name}'"
            if name:
                msg += f" matching '{name}'"
            print_info(msg)
            raise typer.Exit(code=0)

        # Apply limit if specified
        if limit and limit > 0:
            tags_df = tags_df.head(limit)

        # Display results
        count = tags_df.shape[0]
        if json_output:
            print_json(tags_df)
        else:
            table = format_tags_table(tags_df, site_name)
            print_table(table)
            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {count} tag(s){filter_msg}{limit_msg}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch tags: {e}")
        raise typer.Exit(code=1) from e


@tags_app.command("link")
def link_tag(
    uuid: Annotated[str, typer.Argument(help="Tag UUID to link")],
    stashapp_id: Annotated[
        int | None,
        typer.Option("--stashapp-id", help="Stashapp tag ID"),
    ] = None,
    stashdb_id: Annotated[
        str | None,
        typer.Option("--stashdb-id", help="StashDB tag ID (UUID/GUID)"),
    ] = None,
) -> None:
    """Link a Culture Extractor tag to external systems.

    Sets external IDs for a tag, allowing you to associate them with
    Stashapp tags, StashDB entries, etc.

    Examples:
        ce tags link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345
        ce tags link 018f1477-f285-726b-9136-21956e3e8b92 --stashdb-id "a1b2c3d4-..."
        ce tags link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345 --stashdb-id "a1b2c3d4-..."
    """
    try:
        # Validate that at least one ID was provided
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        # Get Culture Extractor client
        client = config.get_client()

        # Verify tag exists
        tag_df = client.get_tag_by_uuid(uuid)
        if tag_df.shape[0] == 0:
            print_error(f"Tag with UUID '{uuid}' not found")
            raise typer.Exit(code=1)

        tag_name = tag_df["ce_tags_name"][0]

        # Set external IDs
        links = []
        if stashapp_id is not None:
            client.set_tag_external_id(uuid, "stashapp", str(stashapp_id))
            links.append(f"Stashapp ID: {stashapp_id}")
        if stashdb_id is not None:
            client.set_tag_external_id(uuid, "stashdb", stashdb_id)
            links.append(f"StashDB ID: {stashdb_id}")

        print_success(f"Linked tag '{tag_name}' to {', '.join(links)}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to link tag: {e}")
        raise typer.Exit(code=1) from e
