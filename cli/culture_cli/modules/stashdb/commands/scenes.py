"""Scene query commands for StashDB data lake."""

import json
import sys
from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from libraries.stashdb_lake import StashDbLake


app = typer.Typer()
console = Console()


def _format_duration(seconds: int | None) -> str:
    """Format duration in seconds to human readable format."""
    if seconds is None:
        return "N/A"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {secs}s"


@app.command("list")
def list_scenes(
    data_path: str = typer.Option(
        "data/stashdb", "--data-path", "-d", help="Base path for Delta Lake storage"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of scenes"),
    performer: str | None = typer.Option(
        None, "--performer", "-p", help="Filter by performer ID"
    ),
    studio: str | None = typer.Option(
        None, "--studio", "-s", help="Filter by studio ID"
    ),
    as_of: str | None = typer.Option(
        None, "--as-of", help="Query data as of date (YYYY-MM-DD)"
    ),
) -> None:
    """List scenes from the StashDB data lake.

    Examples:
        culture stashdb scenes list
        culture stashdb scenes list --limit 50
        culture stashdb scenes list --performer 12345678-1234-1234-1234-123456789abc
        culture stashdb scenes list --as-of 2024-01-01
    """
    lake = StashDbLake(data_path)

    as_of_dt = None
    if as_of:
        try:
            as_of_dt = datetime.fromisoformat(as_of)
            console.print(f"[blue]Querying data as of: {as_of}[/blue]")
        except ValueError:
            console.print(f"[red]Invalid date format: {as_of}. Use YYYY-MM-DD[/red]")
            sys.exit(1)

    df = lake.get_scenes(as_of=as_of_dt)

    if df.is_empty():
        console.print("[yellow]No scenes found in data lake.[/yellow]")
        console.print("[dim]Run 'culture stashdb scrape performer <id>' to fetch data.[/dim]")
        sys.exit(0)

    # Apply filters
    if performer:
        df = df.filter(df["performer_ids"].list.contains(performer))
    if studio:
        df = df.filter(df["studio_id"] == studio)

    # Limit results
    df = df.head(limit)

    # Display table
    table = Table(title=f"StashDB Scenes ({len(df)} results)", show_header=True)
    table.add_column("ID", style="cyan", max_width=36)
    table.add_column("Title", style="green", max_width=40)
    table.add_column("Date", style="yellow")
    table.add_column("Duration", style="blue")
    table.add_column("Scraped At", style="dim")

    for row in df.iter_rows(named=True):
        table.add_row(
            row["id"][:36],
            (row["title"] or "N/A")[:40],
            str(row["release_date"]) if row["release_date"] else "N/A",
            _format_duration(row["duration"]),
            row["scraped_at"].strftime("%Y-%m-%d %H:%M") if row["scraped_at"] else "N/A",
        )

    console.print(table)


@app.command("show")
def show_scene(
    scene_id: str = typer.Argument(..., help="StashDB scene UUID"),
    data_path: str = typer.Option(
        "data/stashdb", "--data-path", "-d", help="Base path for Delta Lake storage"
    ),
    raw: bool = typer.Option(
        False, "--raw", "-r", help="Show raw JSON document"
    ),
) -> None:
    """Show details of a specific scene.

    Examples:
        culture stashdb scenes show 12345678-1234-1234-1234-123456789abc
        culture stashdb scenes show 12345678-1234-1234-1234-123456789abc --raw
    """
    lake = StashDbLake(data_path)

    df = lake.get_scenes(scene_ids=[scene_id])

    if df.is_empty():
        console.print(f"[red]Scene not found: {scene_id}[/red]")
        sys.exit(1)

    row = df.row(0, named=True)

    if raw:
        doc = json.loads(row["json_document"])
        console.print_json(json.dumps(doc, indent=2, default=str))
        return

    # Display formatted scene info
    console.print(
        Panel(
            f"[bold cyan]Scene Information[/bold cyan]\n\n"
            f"[green]ID:[/green] {row['id']}\n"
            f"[green]Title:[/green] {row['title'] or 'N/A'}\n"
            f"[green]Date:[/green] {row['release_date'] or 'N/A'}\n"
            f"[green]Duration:[/green] {_format_duration(row['duration'])}\n"
            f"[green]Studio:[/green] {row['studio_id'] or 'N/A'}\n"
            f"[green]Scraped At:[/green] {row['scraped_at']}",
            title=f"Scene {scene_id[:8]}...",
            border_style="green",
        )
    )

    # Show performers
    if row["performer_ids"]:
        perf_table = Table(title="Performers", show_header=True)
        perf_table.add_column("ID", style="cyan")
        for perf_id in row["performer_ids"]:
            perf_table.add_row(perf_id)
        console.print(perf_table)

    # Show tags
    if row["tag_ids"]:
        tag_table = Table(title="Tags", show_header=True)
        tag_table.add_column("ID", style="magenta")
        for tag_id in row["tag_ids"]:
            tag_table.add_row(tag_id)
        console.print(tag_table)


@app.command("history")
def show_history(
    scene_id: str = typer.Argument(..., help="StashDB scene UUID"),
    data_path: str = typer.Option(
        "data/stashdb", "--data-path", "-d", help="Base path for Delta Lake storage"
    ),
) -> None:
    """Show version history of a scene over time.

    Examples:
        culture stashdb scenes history 12345678-1234-1234-1234-123456789abc
    """
    lake = StashDbLake(data_path)

    df = lake.get_scene_history(scene_id)

    if df.is_empty():
        console.print(f"[red]No history found for scene: {scene_id}[/red]")
        sys.exit(1)

    table = Table(title=f"Scene History: {scene_id[:8]}...", show_header=True)
    table.add_column("Version", style="cyan")
    table.add_column("Scraped At", style="yellow")
    table.add_column("Title", style="green")
    table.add_column("Duration", style="blue")

    for row in df.iter_rows(named=True):
        table.add_row(
            str(row["_version"]),
            row["scraped_at"].strftime("%Y-%m-%d %H:%M") if row["scraped_at"] else "N/A",
            (row["title"] or "N/A")[:40],
            _format_duration(row["duration"]),
        )

    console.print(table)
    console.print(f"\n[dim]Total versions: {len(df)}[/dim]")
