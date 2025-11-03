"""Scene commands for culture stash."""

import sys
import traceback

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from libraries.client_stashapp import get_stashapp_client


app = typer.Typer()
console = Console()


def display_scene_details(scene: dict) -> None:
    """Display detailed information about a scene."""
    # Scene basic info
    console.print(
        Panel(
            f"[bold cyan]Scene Information[/bold cyan]\n\n"
            f"[green]ID:[/green] {scene['id']}\n"
            f"[green]Title:[/green] {scene.get('title') or 'N/A'}\n"
            f"[green]Date:[/green] {scene.get('date') or 'N/A'}",
            title=f"Scene {scene['id']}",
            border_style="green",
        )
    )

    # Display all sections using helper functions
    _display_stash_ids(scene)
    _display_files(scene)
    _display_performers(scene)
    _display_tags(scene)
    _display_galleries(scene)

    console.print("\n")


def _display_stash_ids(scene: dict) -> None:
    """Display external IDs table."""
    if not scene.get("stash_ids"):
        return

    stash_id_table = Table(
        title="External IDs", show_header=True, header_style="bold magenta"
    )
    stash_id_table.add_column("Endpoint", style="cyan")
    stash_id_table.add_column("ID", style="yellow")

    for stash_id in scene["stash_ids"]:
        stash_id_table.add_row(
            stash_id.get("endpoint", "N/A"), stash_id.get("stash_id", "N/A")
        )

    console.print(stash_id_table)


def _display_files(scene: dict) -> None:
    """Display files table."""
    if not scene.get("files"):
        return

    file_table = Table(title="Files", show_header=True, header_style="bold magenta")
    file_table.add_column("Path", style="cyan")
    file_table.add_column("Size", style="yellow")
    file_table.add_column("Duration", style="green")
    file_table.add_column("Resolution", style="blue")

    for file in scene["files"]:
        size_mb = (
            f"{int(file['size']) / 1024 / 1024:.1f} MB"
            if file.get("size")
            else "N/A"
        )
        duration = f"{file['duration']:.1f}s" if file.get("duration") else "N/A"
        resolution = (
            f"{file['width']}x{file['height']}"
            if file.get("width") and file.get("height")
            else "N/A"
        )
        file_table.add_row(file.get("path", "N/A"), size_mb, duration, resolution)

    console.print(file_table)


def _display_performers(scene: dict) -> None:
    """Display performers table."""
    if not scene.get("performers"):
        return

    performer_table = Table(
        title="Performers", show_header=True, header_style="bold magenta"
    )
    performer_table.add_column("ID", style="cyan")
    performer_table.add_column("Name", style="green")
    performer_table.add_column("CE UUID", style="yellow")

    for performer in scene["performers"]:
        ce_uuid = None
        for sid in performer.get("stash_ids", []):
            if sid.get("endpoint") == "https://culture.extractor/graphql":
                ce_uuid = sid.get("stash_id")
                break

        performer_table.add_row(
            performer["id"], performer.get("name", "N/A"), ce_uuid or "Not linked"
        )

    console.print(performer_table)


def _display_tags(scene: dict) -> None:
    """Display tags panel."""
    if not scene.get("tags"):
        return

    tag_names = [tag.get("name", "N/A") for tag in scene["tags"]]
    console.print(Panel(", ".join(tag_names), title="Tags", border_style="magenta"))


def _display_galleries(scene: dict) -> None:
    """Display galleries table."""
    if not scene.get("galleries"):
        return

    gallery_table = Table(
        title="Galleries", show_header=True, header_style="bold magenta"
    )
    gallery_table.add_column("ID", style="cyan")
    gallery_table.add_column("Title", style="green")
    gallery_table.add_column("CE URL", style="yellow")

    for gallery in scene["galleries"]:
        ce_url = None
        for url in gallery.get("urls", []):
            if "culture.extractor/galleries/" in url:
                ce_url = url
                break

        gallery_table.add_row(
            gallery["id"], gallery.get("title", "N/A"), ce_url or "Not linked"
        )

    console.print(gallery_table)


def _apply_scene_filters(scenes, scene_id, ce_id, title, limit):
    """Apply post-query filters to scenes list."""
    if scene_id:
        scenes = [s for s in scenes if s["id"] == str(scene_id)]

    if ce_id:
        scenes = [
            s
            for s in scenes
            if any(
                sid.get("endpoint") == "https://culture.extractor/graphql"
                and sid.get("stash_id") == ce_id
                for sid in s.get("stash_ids", [])
            )
        ]

    if title:
        scenes = [
            s
            for s in scenes
            if s.get("title") and title.lower() in s["title"].lower()
        ]

    if limit:
        scenes = scenes[:limit]

    return scenes


def _display_scenes_list_format(scenes):
    """Display scenes in simple list format."""
    console.print("[bold cyan]Stashapp ID -> CE ID mapping:[/bold cyan]\n")
    for scene in scenes:
        ce_id = _get_ce_id_from_scene(scene)
        if ce_id:
            console.print(f"[yellow]{scene['id']}[/yellow] -> [green]{ce_id}[/green]")
        else:
            console.print(f"[yellow]{scene['id']}[/yellow] -> [dim]No CE ID[/dim]")

    console.print("\n[dim]Use: ce releases link <ce_id> --stashapp-id <stashapp_id>[/dim]")


def _get_ce_id_from_scene(scene):
    """Extract CE ID from scene's stash_ids."""
    for stash_id in scene.get("stash_ids", []):
        if stash_id.get("endpoint") == "https://culture.extractor/graphql":
            return stash_id.get("stash_id")
    return None


@app.command("find")
def find_scenes(
    ce_id: str | None = typer.Option(
        None, "--ce-id", help="Filter by Culture Extractor UUID"
    ),
    title: str | None = typer.Option(None, "--title", "-t", help="Filter by title"),
    scene_id: int | None = typer.Option(
        None, "--id", help="Find specific scene by ID"
    ),
    query: str | None = typer.Option(
        None, "--query", "-q", help="Search query (searches across all fields)"
    ),
    ce_only: bool = typer.Option(
        False, "--ce-only", help="Show only scenes with CE IDs"
    ),
    list_format: bool = typer.Option(
        False, "--list", help="Output as simple list (stashapp_id -> ce_id)"
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-l", help="Limit number of results"
    ),
) -> None:
    """Find and list scenes in Stashapp with optional filters.

    Examples:
        culture stash scenes find --ce-id 01993924-76de-743c-b28b-6d9205dfa184
        culture stash scenes find --title "Beach Play"
        culture stash scenes find --id 35733
        culture stash scenes find --query "Braless Forever" --ce-only
        culture stash scenes find --query "Braless Forever" --ce-only --list
        culture stash scenes find --limit 10
    """
    try:
        console.print("[blue]Connecting to Stashapp...[/blue]")
        stash_raw_client = get_stashapp_client()

        console.print("[blue]Fetching scenes...[/blue]")

        # Build filter for API query
        api_filter = {}
        if ce_only:
            api_filter["stash_id_endpoint"] = {
                "endpoint": "https://culture.extractor/graphql",
                "stash_id": "",
                "modifier": "NOT_NULL"
            }

        # Call find_scenes with filter and query
        kwargs = {"fragment": """
            id
            title
            date
            code
            stash_ids {
                endpoint
                stash_id
            }
            galleries {
                id
                title
                urls
            }
            performers {
                id
                name
                stash_ids {
                    endpoint
                    stash_id
                }
            }
            tags {
                id
                name
            }
            files {
                path
                size
                duration
                width
                height
            }
            """}

        if api_filter:
            kwargs["f"] = api_filter
        if query:
            kwargs["q"] = query

        scenes = stash_raw_client.find_scenes(**kwargs)

        # Apply post-query filters
        scenes = _apply_scene_filters(scenes, scene_id, ce_id, title, limit)

        # Display results
        if not scenes:
            console.print("[yellow]No scenes found matching the criteria.[/yellow]")
            if ce_id:
                console.print(
                    f"\n[dim]No scene with CE UUID {ce_id} found in Stashapp.[/dim]"
                )
                console.print(
                    "[dim]To link a scene to this CE release, add a stash_id with:[/dim]"
                )
                console.print(
                    f"[dim]  Endpoint: https://culture.extractor/graphql[/dim]\n"
                    f"[dim]  Stash ID: {ce_id}[/dim]"
                )
            sys.exit(0)

        console.print(f"\n[green]Found {len(scenes)} scene(s)[/green]\n")

        # Display results based on format
        if list_format:
            _display_scenes_list_format(scenes)
        else:
            for scene in scenes:
                display_scene_details(scene)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"[red]{traceback.format_exc()}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    app()
