"""Data quality commands for the CLI."""

from typing import Annotated

import typer
from rich.table import Table

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)


# Create data quality command group
dq_app = typer.Typer(help="Data quality checks for Culture Extractor")


@dq_app.command("cross-site-performers")
def check_cross_site_performers(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """Check for performers linked to releases from different sites.

    Performers should only be linked to releases from the same site they belong to.
    This check identifies any performers that are incorrectly linked to releases
    from other sites.

    Examples:
        ce dq cross-site-performers          # Display as a table
        ce dq cross-site-performers --json   # Display as JSON
    """
    try:
        client = config.get_client()

        print_info("Checking for performers linked to releases from other sites...")

        df = client.get_performers_with_cross_site_releases()

        if df.shape[0] == 0:
            print_success("No cross-site performer links found. Data is clean!")
            raise typer.Exit(code=0)

        if json_output:
            print_json(df)
        else:
            table = _format_cross_site_table(df)
            print_table(table)

        unique_performers = df["performer_uuid"].n_unique()
        total_links = df.shape[0]
        print_error(
            f"Found {total_links} cross-site link(s) involving {unique_performers} performer(s)"
        )
        raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to check cross-site performers: {e}")
        raise typer.Exit(code=1) from e


def _format_cross_site_table(df) -> Table:
    """Format cross-site performers dataframe as a Rich table."""
    table = Table(
        title="Cross-Site Performer Links",
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )

    table.add_column("Performer", style="green")
    table.add_column("Performer Site", style="yellow")
    table.add_column("Release", style="blue")
    table.add_column("Release Site", style="red")

    for row in df.iter_rows(named=True):
        performer_name = row.get("performer_name", "") or "-"
        performer_site = row.get("performer_site_name", "") or "-"
        release_name = row.get("release_name", "") or "-"
        release_site = row.get("release_site_name", "") or "-"

        if len(performer_name) > 30:
            performer_name = performer_name[:27] + "..."
        if len(release_name) > 40:
            release_name = release_name[:37] + "..."

        table.add_row(performer_name, performer_site, release_name, release_site)

    return table
