"""Sites-related commands for the CLI."""

from typing import Annotated

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
    """
    try:
        # Get Culture Extractor client
        client = config.get_client()

        # Fetch all sites
        sites_df = client.get_sites()

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
