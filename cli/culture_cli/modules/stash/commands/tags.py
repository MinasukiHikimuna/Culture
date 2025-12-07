"""Tag commands for Stashapp."""

import sys

import polars as pl
import typer
from rich.console import Console
from rich.table import Table

from libraries.client_stashapp import StashAppClient


app = typer.Typer()
console = Console()


def create_tags_table(df: pl.DataFrame) -> Table:
    """Create a rich table for displaying tags."""
    table = Table(title="Stashapp Tags", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("StashDB ID", style="blue")

    for row in df.iter_rows(named=True):
        table.add_row(
            str(row["id"]),
            row["name"] or "",
            row["stashdb_id"] or "",
        )

    return table


@app.command("list")
def list_tags(
    name: str | None = typer.Option(
        None, "--name", "-n", help="Filter tags by name (case-insensitive)"
    ),
    stashdb_id: str | None = typer.Option(None, "--stashdb-id", "-s", help="Filter by StashDB ID"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit number of results"),
    prefix: str = typer.Option("", "--prefix", "-p", help="Env var prefix for Stashapp connection"),
) -> None:
    """List tags from Stashapp with optional filters.

    Examples:
        culture stash tags list
        culture stash tags list --name "pov"
        culture stash tags list --stashdb-id "abc123"
        culture stash tags list --limit 20
    """
    try:
        client = StashAppClient(prefix=prefix)
        console.print("[blue]Fetching tags from Stashapp...[/blue]")

        df = client.get_tags()

        # Apply filters
        if name:
            df = df.filter(pl.col("name").str.to_lowercase().str.contains(name.lower()))

        if stashdb_id:
            df = df.filter(pl.col("stashdb_id") == stashdb_id)

        # Apply limit
        if limit:
            df = df.head(limit)

        if df.height == 0:
            console.print("[yellow]No tags found matching the criteria.[/yellow]")
            return

        if json_output:
            print(df.write_json())
        else:
            table = create_tags_table(df)
            console.print(table)
            console.print(f"\n[green]Total: {df.height} tag(s)[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    app()
