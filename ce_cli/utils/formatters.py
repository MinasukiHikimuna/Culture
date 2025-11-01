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


def format_releases_table(releases_df: pl.DataFrame, site_name: str = None) -> Table:
    """Format releases dataframe as a Rich table.

    Args:
        releases_df: Polars DataFrame with release information
        site_name: Optional site name for table title

    Returns:
        Rich Table object ready for display
    """
    title = f"Releases from {site_name}" if site_name else "Releases"
    table = Table(title=title, show_header=True, header_style="bold cyan", expand=False)

    # Add columns
    table.add_column("Date", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Short Name", style="yellow")
    table.add_column("UUID", style="dim")

    # Add rows
    for row in releases_df.iter_rows(named=True):
        release_date = str(row.get("ce_release_date", "")) or "-"
        release_name = str(row.get("ce_release_name", "")) or "-"
        release_short_name = str(row.get("ce_release_short_name", "")) or "-"
        release_uuid = str(row.get("ce_release_uuid", "")) or "-"

        # Truncate long names
        if release_name != "-" and len(release_name) > 50:
            release_name = release_name[:47] + "..."

        table.add_row(
            release_date,
            release_name,
            release_short_name,
            release_uuid,
        )

    return table


def format_release_detail(release_df: pl.DataFrame) -> str:
    """Format a single release as detailed text view.

    Args:
        release_df: Polars DataFrame with single release information

    Returns:
        Formatted string with release details
    """
    from rich.panel import Panel
    from rich.syntax import Syntax
    import json

    row = scene_df.to_dicts()[0]

    # Build detail text
    details = []
    details.append(f"[bold cyan]Scene Details[/bold cyan]\n")
    details.append(f"[yellow]UUID:[/yellow] {row.get('ce_release_uuid', 'N/A')}")
    details.append(f"[yellow]Name:[/yellow] {row.get('ce_release_name', 'N/A')}")
    details.append(f"[yellow]Short Name:[/yellow] {row.get('ce_release_short_name', 'N/A')}")
    details.append(f"[yellow]Date:[/yellow] {row.get('ce_release_date', 'N/A')}")
    details.append(f"[yellow]URL:[/yellow] {row.get('ce_release_url', 'N/A')}")
    details.append(f"\n[yellow]Description:[/yellow]")
    details.append(row.get('ce_release_description', 'N/A') or 'N/A')

    detail_text = "\n".join(details)

    console.print(Panel(detail_text, border_style="cyan"))

    # Show available files if present
    available_files = row.get('ce_release_available_files')
    if available_files:
        try:
            files_json = json.loads(available_files) if isinstance(available_files, str) else available_files
            console.print("\n[bold cyan]Available Files:[/bold cyan]")
            console.print_json(json.dumps(files_json, indent=2))
        except:
            pass

    return ""


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
