"""Output formatting utilities for the CLI."""

import json
import sys
from typing import Any
import polars as pl
from rich.console import Console
from rich.table import Table


# Force UTF-8 encoding for stdout/stderr if on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7 doesn't have reconfigure
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

console = Console()


def format_sites_table(sites_df: pl.DataFrame) -> Table:
    """Format sites dataframe as a Rich table.

    Args:
        sites_df: Polars DataFrame with site information

    Returns:
        Rich Table object ready for display
    """
    table = Table(title="Culture Extractor Sites", show_header=True, header_style="bold cyan")

    # Add columns
    table.add_column("UUID", style="dim", width=38)
    table.add_column("Short Name", style="yellow")
    table.add_column("Name", style="green")
    table.add_column("URL", style="blue")

    # Add rows
    for row in sites_df.iter_rows(named=True):
        table.add_row(
            row["ce_sites_uuid"],
            row["ce_sites_short_name"],
            row["ce_sites_name"],
            row["ce_sites_url"],
        )

    return table


def format_json(data: Any, pretty: bool = True) -> str:
    """Format data as JSON string.

    Args:
        data: Data to format (dict, list, or Polars DataFrame)
        pretty: Whether to use pretty printing with indentation

    Returns:
        JSON string
    """
    if isinstance(data, pl.DataFrame):
        # Convert Polars DataFrame to list of dicts
        data = data.to_dicts()

    if pretty:
        return json.dumps(data, indent=2, default=str)
    else:
        return json.dumps(data, default=str)


def print_table(table: Table) -> None:
    """Print a Rich table to console.

    Args:
        table: Rich Table object to print
    """
    console.print(table)


def print_json(data: Any, pretty: bool = True) -> None:
    """Print data as JSON to console.

    Args:
        data: Data to print
        pretty: Whether to use pretty printing
    """
    print(format_json(data, pretty=pretty))


def print_error(message: str) -> None:
    """Print an error message to console.

    Args:
        message: Error message to display
    """
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message to console.

    Args:
        message: Success message to display
    """
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str) -> None:
    """Print an info message to console.

    Args:
        message: Info message to display
    """
    console.print(f"[bold blue]ℹ[/bold blue] {message}")
