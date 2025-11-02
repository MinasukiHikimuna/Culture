"""Sites-related commands for the CLI."""

from typing import Annotated

import typer

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    format_sites_table,
    print_error,
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
