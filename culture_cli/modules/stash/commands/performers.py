"""Performer commands for stash-cli."""

import base64
import mimetypes
import sys
from pathlib import Path

import polars as pl
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from libraries.client_stashapp import StashAppClient


app = typer.Typer()
console = Console()


def create_performers_table(df: pl.DataFrame) -> Table:
    """Create a rich table for displaying performers."""
    table = Table(title="Stashapp Performers", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Gender", style="yellow")
    table.add_column("Favorite", style="red")
    table.add_column("StashDB ID", style="blue")
    table.add_column("TPDB ID", style="blue")

    for row in df.iter_rows(named=True):
        table.add_row(
            str(row["stashapp_id"]),
            row["stashapp_name"] or "",
            row["stashapp_gender"] or "",
            "⭐" if row["stashapp_favorite"] else "",
            row["stashapp_stashdb_id"] or "",
            row["stashapp_tpdb_id"] or "",
        )

    return table


@app.command("list")
def list_performers(
    name: str | None = typer.Option(
        None, "--name", "-n", help="Filter performers by name (case-insensitive)"
    ),
    stashdb_id: str | None = typer.Option(None, "--stashdb-id", "-s", help="Filter by StashDB ID"),
    tpdb_id: str | None = typer.Option(None, "--tpdb-id", "-t", help="Filter by ThePornDB ID"),
    favorite: bool | None = typer.Option(None, "--favorite", "-f", help="Filter by favorite status"),
    gender: str | None = typer.Option(
        None, "--gender", "-g", help="Filter by gender (MALE, FEMALE, TRANSGENDER_MALE, etc.)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit number of results"),
    prefix: str = typer.Option("", "--prefix", "-p", help="Env var prefix for Stashapp connection"),
) -> None:
    """List performers from Stashapp with optional filters.

    Examples:
        stash-cli performers list --name "Jane"
        stash-cli performers list --stashdb-id "abc123"
        stash-cli performers list --favorite --gender FEMALE
    """
    try:
        client = StashAppClient(prefix=prefix)
        console.print("[blue]Fetching performers from Stashapp...[/blue]")

        df = client.get_performers()

        # Apply filters
        if name:
            df = df.filter(pl.col("stashapp_name").str.to_lowercase().str.contains(name.lower()))

        if stashdb_id:
            df = df.filter(pl.col("stashapp_stashdb_id") == stashdb_id)

        if tpdb_id:
            df = df.filter(pl.col("stashapp_tpdb_id") == tpdb_id)

        if favorite is not None:
            df = df.filter(pl.col("stashapp_favorite") == favorite)

        if gender:
            gender_upper = gender.upper()
            df = df.filter(pl.col("stashapp_gender") == gender_upper)

        # Apply limit
        if limit:
            df = df.head(limit)

        if df.height == 0:
            console.print("[yellow]No performers found matching the criteria.[/yellow]")
            return

        if json_output:
            print(df.write_json())
        else:
            table = create_performers_table(df)
            console.print(table)
            console.print(f"\n[green]Total: {df.height} performer(s)[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@app.command("show")
def show_performer(
    performer_id: int = typer.Argument(..., help="Performer ID to display"),
    prefix: str = typer.Option("", "--prefix", "-p", help="Environment variable prefix for Stashapp connection"),
) -> None:
    """Show detailed information about a specific performer.

    Example:
        stash-cli performers show 123
    """
    try:
        client = StashAppClient(prefix=prefix)
        console.print(f"[blue]Fetching performer {performer_id} from Stashapp...[/blue]")

        df = client.get_performers()
        performer_df = df.filter(pl.col("stashapp_id") == performer_id)

        if performer_df.height == 0:
            console.print(f"[red]Performer with ID {performer_id} not found.[/red]")
            sys.exit(1)

        performer = performer_df.to_dicts()[0]

        # Display detailed information
        console.print("\n[bold cyan]Performer Details[/bold cyan]")
        console.print(f"[green]ID:[/green] {performer['stashapp_id']}")
        console.print(f"[green]Name:[/green] {performer['stashapp_name']}")
        console.print(f"[green]Gender:[/green] {performer['stashapp_gender']}")
        console.print(f"[green]Favorite:[/green] {'Yes ⭐' if performer['stashapp_favorite'] else 'No'}")

        if performer["stashapp_stashdb_id"]:
            console.print(f"[green]StashDB ID:[/green] {performer['stashapp_stashdb_id']}")

        if performer["stashapp_tpdb_id"]:
            console.print(f"[green]TPDB ID:[/green] {performer['stashapp_tpdb_id']}")

        if performer["stashapp_alias_list"]:
            console.print(f"[green]Aliases:[/green] {', '.join(performer['stashapp_alias_list'])}")

        if performer["stashapp_urls"]:
            console.print("[green]URLs:[/green]")
            for url in performer["stashapp_urls"]:
                console.print(f"  - {url}")

        if performer["stashapp_custom_fields"]:
            console.print("[green]Custom Fields:[/green]")
            for field in performer["stashapp_custom_fields"]:
                console.print(f"  {field['key']}: {field['value']}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@app.command("create")
def create_performer(
    name: str = typer.Argument(..., help="Performer name"),
    stashdb_id: str | None = typer.Option(
        None, "--stashdb-id", "-s", help="StashDB performer ID (UUID)"
    ),
    ce_id: str | None = typer.Option(
        None, "--ce-id", "-c", help="Culture Extractor performer ID (UUID)"
    ),
    image: str | None = typer.Option(None, "--image", "-i", help="Path to profile image file"),
    disambiguation: str | None = typer.Option(
        None, "--disambiguation", "-d", help="Disambiguation text (e.g., '1990s'/'Brazzers')"
    ),
    gender: str | None = typer.Option(
        None,
        "--gender",
        "-g",
        help="Gender: MALE, FEMALE, TRANSGENDER_MALE, TRANSGENDER_FEMALE, INTERSEX, NON_BINARY",
    ),
    prefix: str = typer.Option(
        "", "--prefix", "-p", help="Environment variable prefix for Stashapp connection"
    ),
) -> None:
    """Create a new performer in Stashapp with optional external IDs and profile image.

    The image will be base64 encoded and uploaded as part of the performer creation.
    Gender must be one of: MALE, FEMALE, TRANSGENDER_MALE, TRANSGENDER_FEMALE, INTERSEX, NON_BINARY

    Examples:
        stash-cli performers create "Jane Doe"
        stash-cli performers create "Jane Doe" --stashdb-id "abc123-def456-..."
        stash-cli performers create "Jane Doe" --image "/path/to/profile.jpg"
        stash-cli performers create "Jane Doe" --gender FEMALE --disambiguation "2000s"
        stash-cli performers create "Jane Doe" --stashdb-id "abc123..." --ce-id "def456..." --image "profile.jpg"
    """
    try:
        # Validate gender if provided
        valid_genders = ["MALE", "FEMALE", "TRANSGENDER_MALE", "TRANSGENDER_FEMALE", "INTERSEX", "NON_BINARY"]
        if gender and gender not in valid_genders:
            console.print(f"[red]Error: Invalid gender '{gender}'[/red]")
            console.print(f"[yellow]Valid values: {', '.join(valid_genders)}[/yellow]")
            sys.exit(1)

        client = StashAppClient(prefix=prefix)

        # Show what we're about to create
        console.print("\n[bold cyan]Creating Performer[/bold cyan]")
        console.print(f"[green]Name:[/green] {name}")
        if stashdb_id:
            console.print(f"[green]StashDB ID:[/green] {stashdb_id}")
        if ce_id:
            console.print(f"[green]Culture Extractor ID:[/green] {ce_id}")
        if image:
            console.print(f"[green]Profile Image:[/green] {image}")
        if disambiguation:
            console.print(f"[green]Disambiguation:[/green] {disambiguation}")
        if gender:
            console.print(f"[green]Gender:[/green] {gender}")

        # Process image if provided
        image_data = None
        if image:
            image_data = _process_image_file(image)

        # Create the performer
        console.print("\n[blue]Creating performer in Stashapp...[/blue]")
        result = client.create_performer(
            name=name,
            stashdb_id=stashdb_id,
            ce_id=ce_id,
            image=image_data,
            disambiguation=disambiguation,
            gender=gender,
        )

        # Display success message
        performer_id = result.get("id")
        success_msg = (
            f"[bold green]Successfully created performer![/bold green]\n\n"
            f"ID: {performer_id}\n"
            f"Name: {result.get('name')}\n"
        )
        if image_data:
            success_msg += "Profile image: Uploaded\n"
        success_msg += f"\nView details with: [cyan]stash-cli performers show {performer_id}[/cyan]"

        console.print(
            Panel(
                success_msg,
                title="Success",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"[red]Error creating performer: {e}[/red]")
        sys.exit(1)


def _process_image_file(image_path: str) -> str:
    """Process an image file and return base64 encoded data URL.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded data URL (e.g., "data:image/jpeg;base64,...")

    Raises:
        FileNotFoundError: If the image file doesn't exist
        ValueError: If the file is not a valid image
    """
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {image_path}")

    # Read and encode the image
    with path.open("rb") as img_file:
        image_data = img_file.read()
        base64_image = base64.b64encode(image_data).decode("utf-8")

    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"  # Default fallback

    return f"data:{mime_type};base64,{base64_image}"


if __name__ == "__main__":
    app()
