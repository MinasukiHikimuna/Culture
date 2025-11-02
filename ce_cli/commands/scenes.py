"""Scene/Release commands for CE CLI."""

import os
import sys
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from libraries.client_culture_extractor import ClientCultureExtractor

load_dotenv()

app = typer.Typer()
console = Console()


def get_ce_client() -> ClientCultureExtractor:
    """Get Culture Extractor client with connection string from environment."""
    ce_connection_string = os.getenv("CE_CONNECTION_STRING")
    if not ce_connection_string:
        # Build from individual components
        ce_user = os.getenv("CE_DB_USERNAME")
        ce_pass = os.getenv("CE_DB_PASSWORD")
        ce_host = os.getenv("CE_DB_HOST")
        ce_port = os.getenv("CE_DB_PORT")
        ce_db = os.getenv("CE_DB_NAME")

        if not all([ce_user, ce_pass, ce_host, ce_port, ce_db]):
            console.print(
                "[red]Error: CE connection environment variables not found. "
                "Need either CE_CONNECTION_STRING or CE_DB_* variables.[/red]"
            )
            sys.exit(1)

        ce_connection_string = (
            f"postgresql://{ce_user}:{ce_pass}@{ce_host}:{ce_port}/{ce_db}"
        )

    return ClientCultureExtractor(ce_connection_string)


@app.command("show")
def show_release(
    ce_id: str = typer.Argument(..., help="Culture Extractor release UUID to display"),
) -> None:
    """Show detailed information about a Culture Extractor release.

    This command retrieves release data from Culture Extractor including:
    - Basic release information (name, date, site, etc.)
    - Description
    - Available files metadata
    - JSON document data

    Example:
        ce scenes show 01993924-76de-743c-b28b-6d9205dfa184
    """
    try:
        console.print("[blue]Connecting to Culture Extractor...[/blue]")
        ce_client = get_ce_client()

        # Get release data from Culture Extractor
        console.print(f"[blue]Fetching release {ce_id}...[/blue]")
        release_df = ce_client.get_release_by_uuid(ce_id)

        if release_df.height == 0:
            console.print(f"[red]Release with UUID {ce_id} not found.[/red]")
            sys.exit(1)

        release = release_df.to_dicts()[0]

        # Display basic release information
        console.print("\n")
        console.print(
            Panel(
                f"[bold cyan]Release Information[/bold cyan]\n\n"
                f"[green]UUID:[/green] {release['ce_release_uuid']}\n"
                f"[green]Name:[/green] {release['ce_release_name']}\n"
                f"[green]Short Name:[/green] {release['ce_release_short_name'] or 'N/A'}\n"
                f"[green]Site:[/green] {release['ce_site_name']}\n"
                f"[green]Site UUID:[/green] {release['ce_site_uuid']}\n"
                f"[green]Release Date:[/green] {release['ce_release_date'] or 'N/A'}\n"
                f"[green]URL:[/green] {release['ce_release_url'] or 'N/A'}\n"
                f"[green]Created:[/green] {release['ce_release_created'] or 'N/A'}\n"
                f"[green]Last Updated:[/green] {release['ce_release_last_updated'] or 'N/A'}",
                title="Culture Extractor Release",
                border_style="cyan",
            )
        )

        # Display description if available
        if release.get("ce_release_description"):
            console.print(
                Panel(
                    release["ce_release_description"],
                    title="Description",
                    border_style="cyan",
                )
            )

        # Display available files if present
        if release.get("ce_release_available_files"):
            console.print(
                Panel(
                    release["ce_release_available_files"],
                    title="Available Files (JSON)",
                    border_style="yellow",
                )
            )

        # Display JSON document if present and different from available_files
        if release.get("ce_release_json_document"):
            console.print(
                Panel(
                    release["ce_release_json_document"],
                    title="JSON Document",
                    border_style="magenta",
                )
            )

        # Get and display performers for this release
        console.print("\n[blue]Fetching performers for this release...[/blue]")
        performers_df = ce_client.get_release_performers(ce_id)

        if performers_df.height > 0:
            from rich.table import Table

            performer_table = Table(
                title="Performers", show_header=True, header_style="bold magenta"
            )
            performer_table.add_column("Name", style="green")
            performer_table.add_column("CE UUID", style="cyan")
            performer_table.add_column("Stashapp ID", style="yellow")
            performer_table.add_column("StashDB ID", style="blue")

            for performer in performers_df.iter_rows(named=True):
                performer_table.add_row(
                    performer["ce_performers_name"] or "N/A",
                    performer["ce_performers_uuid"] or "N/A",
                    performer["ce_performers_stashapp_id"] or "Not linked",
                    performer["ce_performers_stashdb_id"] or "Not linked",
                )

            console.print(performer_table)
        else:
            console.print("[dim]No performers found for this release[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback

        console.print(f"[red]{traceback.format_exc()}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    app()
