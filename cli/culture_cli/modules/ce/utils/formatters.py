"""Output formatting utilities for the CLI."""

import json
import sys
from typing import Any

import polars as pl
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# Force UTF-8 encoding for stdout/stderr if on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        # Python < 3.7 doesn't have reconfigure
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

console = Console(stderr=True)


def format_releases_table(releases_df: pl.DataFrame, site_name: str | None = None) -> Table:
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


def format_releases_table_from_list(releases: list[dict], site_name: str | None = None) -> Table:
    """Format releases list as a Rich table.

    Args:
        releases: List of release dictionaries
        site_name: Optional site name for table title

    Returns:
        Rich Table object ready for display
    """
    title = f"Releases from {site_name}" if site_name else "Releases"
    table = Table(title=title, show_header=True, header_style="bold cyan", expand=False)

    table.add_column("Date", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Short Name", style="yellow")
    table.add_column("UUID", style="dim")

    for row in releases:
        release_date = str(row.get("ce_release_date", "")) or "-"
        release_name = str(row.get("ce_release_name", "")) or "-"
        release_short_name = str(row.get("ce_release_short_name", "")) or "-"
        release_uuid = str(row.get("ce_release_uuid", "")) or "-"

        if release_name != "-" and len(release_name) > 50:
            release_name = release_name[:47] + "..."

        table.add_row(
            release_date,
            release_name,
            release_short_name,
            release_uuid,
        )

    return table


def format_download_summary_table(
    summaries: list[dict], site_name: str | None = None
) -> Table:
    """Format per-release download summary as a Rich table.

    Args:
        summaries: List of release download summary dictionaries
        site_name: Optional site name for table title

    Returns:
        Rich Table object ready for display
    """
    title = f"Download status for {site_name}" if site_name else "Download status"
    table = Table(title=title, show_header=True, header_style="bold cyan", expand=False)

    table.add_column("Date", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Short Name", style="yellow")
    table.add_column("Downloads", justify="right")

    for row in summaries:
        release_date = str(row.get("ce_release_date", "")) or "-"
        release_name = str(row.get("ce_release_name", "")) or "-"
        release_short_name = str(row.get("ce_release_short_name", "")) or "-"

        if release_name != "-" and len(release_name) > 50:
            release_name = release_name[:47] + "..."

        download_count = row.get("ce_release_download_count", 0)
        type_pairs = row.get("ce_release_download_type_pairs")
        if download_count > 0 and type_pairs:
            downloads_cell = f"[bold]{download_count}[/bold] ({type_pairs})"
        elif download_count > 0:
            downloads_cell = f"[bold]{download_count}[/bold]"
        else:
            downloads_cell = "[dim]\u2014[/dim]"

        table.add_row(
            release_date,
            release_name,
            release_short_name,
            downloads_cell,
        )

    return table


def format_download_type_summary(summaries: list[dict]) -> str:
    """Build a summary string of all distinct file_types and content_types across results.

    Args:
        summaries: List of release download summary dictionaries

    Returns:
        Formatted summary string
    """
    file_types: set[str] = set()
    content_types: set[str] = set()

    for row in summaries:
        ft = row.get("ce_release_download_file_types")
        if ft:
            file_types.update(t.strip() for t in ft.split(","))
        ct = row.get("ce_release_download_content_types")
        if ct:
            content_types.update(t.strip() for t in ct.split(","))

    lines = []
    if file_types:
        lines.append(f"File types: {', '.join(sorted(file_types))}")
    if content_types:
        lines.append(f"Content types: {', '.join(sorted(content_types))}")
    return "\n".join(lines)


def format_release_detail(release_df: pl.DataFrame, external_ids: dict | None = None) -> str:
    """Format a single release as detailed text view.

    Args:
        release_df: Polars DataFrame with single release information
        external_ids: Optional dictionary of external IDs

    Returns:
        Formatted string with release details
    """
    row = release_df.to_dicts()[0]

    # Build detail text
    details = []
    details.append("[bold cyan]Scene Details[/bold cyan]\n")
    details.append(f"[yellow]UUID:[/yellow] {row.get('ce_release_uuid', 'N/A')}")
    details.append(f"[yellow]Name:[/yellow] {row.get('ce_release_name', 'N/A')}")
    details.append(f"[yellow]Short Name:[/yellow] {row.get('ce_release_short_name', 'N/A')}")
    details.append(f"[yellow]Date:[/yellow] {row.get('ce_release_date', 'N/A')}")
    details.append(f"[yellow]URL:[/yellow] {row.get('ce_release_url', 'N/A')}")
    details.append("\n[yellow]Description:[/yellow]")
    details.append(row.get("ce_release_description", "N/A") or "N/A")

    # Add external IDs if present
    if external_ids:
        details.append("\n[bold cyan]External IDs[/bold cyan]")
        for system_name, ext_id in external_ids.items():
            # Format the system name nicely (capitalize first letter)
            formatted_name = system_name.replace("_", " ").title()
            details.append(f"[yellow]{formatted_name}:[/yellow] {ext_id}")

    detail_text = "\n".join(details)

    console.print(Panel(detail_text, border_style="cyan"))

    # Show available files if present
    available_files = row.get("ce_release_available_files")
    if available_files:
        try:
            files_json = json.loads(available_files) if isinstance(available_files, str) else available_files
            console.print("\n[bold cyan]Available Files:[/bold cyan]")
            console.print_json(json.dumps(files_json, indent=2))
        except (json.JSONDecodeError, TypeError):
            pass

    return ""


def format_release_detail_from_dict(release: dict) -> str:
    """Format a single release dictionary as detailed text view.

    Args:
        release: Dictionary with release information (from API response)

    Returns:
        Formatted string with release details
    """
    details = []
    details.append("[bold cyan]Scene Details[/bold cyan]\n")
    details.append(f"[yellow]UUID:[/yellow] {release.get('ce_release_uuid', 'N/A')}")
    details.append(f"[yellow]Name:[/yellow] {release.get('ce_release_name', 'N/A')}")
    details.append(f"[yellow]Short Name:[/yellow] {release.get('ce_release_short_name', 'N/A')}")
    details.append(f"[yellow]Date:[/yellow] {release.get('ce_release_date', 'N/A')}")
    details.append(f"[yellow]URL:[/yellow] {release.get('ce_release_url', 'N/A')}")
    details.append("\n[yellow]Description:[/yellow]")
    details.append(release.get("ce_release_description", "N/A") or "N/A")

    # Add external IDs if present
    external_ids = release.get("external_ids", {})
    if external_ids:
        has_ids = any(v for v in external_ids.values() if v)
        if has_ids:
            details.append("\n[bold cyan]External IDs[/bold cyan]")
            for system_name, ext_id in external_ids.items():
                if ext_id:
                    formatted_name = system_name.replace("_", " ").title()
                    details.append(f"[yellow]{formatted_name}:[/yellow] {ext_id}")

    detail_text = "\n".join(details)
    console.print(Panel(detail_text, border_style="cyan"))

    # Show available files if present
    available_files = release.get("ce_release_available_files")
    if available_files:
        try:
            files_json = json.loads(available_files) if isinstance(available_files, str) else available_files
            console.print("\n[bold cyan]Available Files:[/bold cyan]")
            console.print_json(json.dumps(files_json, indent=2))
        except (json.JSONDecodeError, TypeError):
            pass

    return ""


def format_sites_table(sites_df: pl.DataFrame | list[dict]) -> Table:
    """Format sites dataframe or list of dicts as a Rich table.

    Args:
        sites_df: Polars DataFrame or list of dicts with site information

    Returns:
        Rich Table object ready for display
    """
    table = Table(title="Culture Extractor Sites", show_header=True, header_style="bold cyan")

    # Add columns
    table.add_column("UUID", style="dim", width=38)
    table.add_column("Short Name", style="yellow")
    table.add_column("Name", style="green")
    table.add_column("URL", style="blue")

    # Convert to iterable of dicts
    rows = sites_df.iter_rows(named=True) if isinstance(sites_df, pl.DataFrame) else sites_df

    # Add rows
    for row in rows:
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
    console.print(f"[bold blue]i[/bold blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message to console.

    Args:
        message: Warning message to display
    """
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def format_performers_table(performers_df: pl.DataFrame, site_name: str | None = None) -> Table:  # noqa: PLR0912
    """Format performers dataframe as a Rich table.

    Args:
        performers_df: Polars DataFrame with performer information
        site_name: Optional site name for table title (if None, shows multi-site view)

    Returns:
        Rich Table object ready for display
    """
    # Check if this is a multi-site query by looking for ce_site_name column
    is_multi_site = "ce_site_name" in performers_df.columns

    # Check if link status columns are present
    has_link_status = "has_stashapp_link" in performers_df.columns and "has_stashdb_link" in performers_df.columns

    title = f"Performers from {site_name}" if site_name else "Performers (All Sites)"
    table = Table(title=title, show_header=True, header_style="bold cyan", expand=False)

    # Add columns
    table.add_column("Name", style="green")
    if is_multi_site:
        table.add_column("Site", style="cyan")
    table.add_column("Short Name", style="yellow")
    if has_link_status:
        table.add_column("Links", style="magenta", justify="center")
    table.add_column("UUID", style="dim")

    # Add rows
    for row in performers_df.iter_rows(named=True):
        performer_name = str(row.get("ce_performers_name", "")) or "-"
        performer_short_name = str(row.get("ce_performers_short_name", "")) or "-"
        performer_uuid = str(row.get("ce_performers_uuid", "")) or "-"

        # Truncate long names
        if performer_name != "-" and len(performer_name) > 40:
            performer_name = performer_name[:37] + "..."

        # Build link status indicator
        link_status = ""
        if has_link_status:
            has_stashapp = row.get("has_stashapp_link", False)
            has_stashdb = row.get("has_stashdb_link", False)

            if has_stashapp and has_stashdb:
                link_status = "SA+DB"  # Both linked
            elif has_stashapp:
                link_status = "SA"  # Stashapp only
            elif has_stashdb:
                link_status = "DB"  # StashDB only
            else:
                link_status = "-"  # Not linked

        if is_multi_site:
            site_display = str(row.get("ce_site_name", "")) or "-"
            if site_display != "-" and len(site_display) > 20:
                site_display = site_display[:17] + "..."

            if has_link_status:
                table.add_row(
                    performer_name,
                    site_display,
                    performer_short_name,
                    link_status,
                    performer_uuid,
                )
            else:
                table.add_row(
                    performer_name,
                    site_display,
                    performer_short_name,
                    performer_uuid,
                )
        elif has_link_status:
            table.add_row(
                performer_name,
                performer_short_name,
                link_status,
                performer_uuid,
            )
        else:
            table.add_row(
                performer_name,
                performer_short_name,
                performer_uuid,
            )

    return table


def format_performer_detail(performer_df: pl.DataFrame, external_ids: dict | None = None) -> str:
    """Format a single performer as detailed text view.

    Args:
        performer_df: Polars DataFrame with single performer information
        external_ids: Optional dictionary of external IDs

    Returns:
        Formatted string with performer details
    """
    row = performer_df.to_dicts()[0]

    # Build detail text
    details = []
    details.append("[bold cyan]Performer Details[/bold cyan]\n")
    details.append(f"[yellow]UUID:[/yellow] {row.get('ce_performers_uuid', 'N/A')}")
    details.append(f"[yellow]Name:[/yellow] {row.get('ce_performers_name', 'N/A')}")
    details.append(f"[yellow]Short Name:[/yellow] {row.get('ce_performers_short_name', 'N/A')}")
    details.append(f"[yellow]URL:[/yellow] {row.get('ce_performers_url', 'N/A')}")

    # Add external IDs if present
    if external_ids:
        details.append("\n[bold cyan]External IDs[/bold cyan]")
        for system_name, ext_id in external_ids.items():
            # Format the system name nicely (capitalize first letter)
            formatted_name = system_name.replace("_", " ").title()
            details.append(f"[yellow]{formatted_name}:[/yellow] {ext_id}")

    detail_text = "\n".join(details)

    console.print(Panel(detail_text, border_style="cyan"))

    return ""


def format_tags_table(tags_df: pl.DataFrame, site_name: str | None = None) -> Table:
    """Format tags dataframe as a Rich table.

    Args:
        tags_df: Polars DataFrame with tag information
        site_name: Optional site name for table title

    Returns:
        Rich Table object ready for display
    """
    title = f"Tags from {site_name}" if site_name else "Tags"
    table = Table(title=title, show_header=True, header_style="bold cyan", expand=False)

    # Add columns
    table.add_column("Name", style="green")
    table.add_column("Short Name", style="yellow")
    table.add_column("Stashapp", style="cyan", justify="center")
    table.add_column("StashDB", style="cyan", justify="center")
    table.add_column("UUID", style="dim")

    # Add rows
    for row in tags_df.iter_rows(named=True):
        tag_name = str(row.get("ce_tags_name", "")) or "-"
        tag_short_name = str(row.get("ce_tags_short_name", "")) or "-"
        tag_uuid = str(row.get("ce_tags_uuid", "")) or "-"
        stashapp_id = row.get("ce_tags_stashapp_id")
        stashdb_id = row.get("ce_tags_stashdb_id")

        # Truncate long names
        if tag_name != "-" and len(tag_name) > 40:
            tag_name = tag_name[:37] + "..."

        # Display link status with checkmark or x
        stashapp_status = "✓" if stashapp_id else "✗"
        stashdb_status = "✓" if stashdb_id else "✗"

        table.add_row(
            tag_name,
            tag_short_name,
            stashapp_status,
            stashdb_status,
            tag_uuid,
        )

    return table
