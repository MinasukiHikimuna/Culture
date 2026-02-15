#!/usr/bin/env python3
"""
Interactive performer face matching script.

This script automates the workflow of:
1. Getting CE performer details and their image
2. Running face recognition using Stashface API
3. Looking up matched performers in Stashapp
4. Prompting for confirmation
5. Linking the CE performer to Stashapp and StashDB IDs

Usage:
    python match_performer_face.py <ce_performer_uuid>
    python match_performer_face.py <ce_performer_uuid> --threshold 0.8
    python match_performer_face.py <ce_performer_uuid> --auto-approve
"""

import argparse
import os
import subprocess
import sys
import tempfile
import termios
import time
import traceback
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from stashface_api_client import StashfaceAPIClient

from culture_cli.modules.ce.utils.config import config
from libraries.client_stashapp import StashAppClient
from libraries.StashDbClient import StashDbClient


if TYPE_CHECKING:
    from libraries.client_culture_extractor import ClientCultureExtractor


console = Console()


def get_ce_performer(client: ClientCultureExtractor, performer_uuid: str) -> dict | None:
    """Get performer details from Culture Extractor database.

    Args:
        client: Culture Extractor client
        performer_uuid: UUID of the performer

    Returns:
        Dictionary with performer details or None if not found
    """
    try:
        performer_df = client.get_performer_by_uuid(performer_uuid)
        if performer_df.shape[0] == 0:
            return None
        return performer_df.to_dicts()[0]
    except Exception as e:
        console.print(f"[red]Error fetching CE performer: {e}[/red]")
        return None


def get_performer_image_path(performer: dict) -> tuple[Path | None, str | None]:
    """Get the image path for a performer.

    Args:
        performer: Performer dictionary from CE database

    Returns:
        Tuple of (Path to the performer's image file or None if not found,
                 Site name from database or None)
    """
    performer_uuid = performer.get("ce_performers_uuid")
    if not performer_uuid:
        return None, None

    # Get site name from database
    site_name = performer.get("ce_sites_name")

    if not site_name:
        return None, None

    # Try common image path patterns
    # Based on your example: /Volumes/Ripping/LezKiss/Performers/{uuid}/{uuid}.jpg
    possible_paths = [
        # Exact case from database (e.g., angels.love)
        Path(f"/Volumes/Ripping/{site_name}/Performers/{performer_uuid}/{performer_uuid}.jpg"),
        # Title case (LezKiss)
        Path(f"/Volumes/Ripping/{site_name.title()}/Performers/{performer_uuid}/{performer_uuid}.jpg"),
        # All caps (LEZKISS)
        Path(f"/Volumes/Ripping/{site_name.upper()}/Performers/{performer_uuid}/{performer_uuid}.jpg"),
        # Lowercase (lezkiss)  # noqa: ERA001
        Path(f"/Volumes/Ripping/{site_name.lower()}/Performers/{performer_uuid}/{performer_uuid}.jpg"),
    ]

    for path in possible_paths:
        if path.exists():
            return path, site_name

    # If image path is directly in the database
    image_path = performer.get("ce_performers_image_path")
    if image_path:
        path = Path(image_path)
        if path.exists():
            return path, site_name

    return None, site_name


def run_face_recognition(image_path: Path, threshold: float = 0.5, max_results: int = 3) -> dict:
    """Run face recognition on the performer image.

    Args:
        image_path: Path to the image file
        threshold: Confidence threshold (0.0-1.0)
        max_results: Maximum number of results to return

    Returns:
        Dictionary with face recognition results
    """
    console.print(f"[blue]Running face recognition on: {image_path}[/blue]")

    client = StashfaceAPIClient()
    results = client.analyze_faces(str(image_path), threshold, max_results, "json")

    return results


def display_face_matches(results: dict) -> list[dict]:
    """Display face recognition results and return matches.

    Args:
        results: Results from face recognition API

    Returns:
        List of performer matches
    """
    if not results.get("success"):
        console.print(f"[red]Face recognition failed: {results.get('error', 'Unknown error')}[/red]")
        return []

    faces_data = results.get("results", [])
    if not faces_data:
        console.print("[yellow]No faces detected in the image[/yellow]")
        return []

    all_matches = []

    for i, face in enumerate(faces_data, 1):
        console.print(f"\n[bold cyan]Face {i}:[/bold cyan]")
        console.print(f"  Detection confidence: [green]{face['confidence']:.1%}[/green]")

        performers = face.get("performers", [])
        if performers:
            all_matches.extend(performers)

            table = Table(title=f"Face {i} Matches", show_header=True)
            table.add_column("#", style="cyan", width=3)
            table.add_column("Name", style="green")
            table.add_column("Country", style="yellow")
            table.add_column("Confidence", style="magenta")
            table.add_column("StashDB ID", style="blue")

            for j, performer in enumerate(performers, 1):
                performer_url = performer.get("performer_url", "")
                stashdb_id = performer_url.split("/")[-1] if performer_url else "N/A"
                table.add_row(
                    str(j),
                    performer.get("name", "Unknown"),
                    performer.get("country", "?"),
                    f"{performer.get('confidence', 0)}%",
                    stashdb_id,
                )

            console.print(table)
        else:
            console.print("[yellow]  No performer matches found[/yellow]")

    return all_matches


def lookup_stashapp_performer(stashapp_client: StashAppClient, stashdb_id: str) -> dict | None:
    """Look up a performer in Stashapp by StashDB ID.

    Args:
        stashapp_client: Stashapp client
        stashdb_id: StashDB UUID

    Returns:
        Performer dictionary or None if not found
    """
    try:
        df = stashapp_client.get_performers()
        performer_df = df.filter(df["stashapp_stashdb_id"] == stashdb_id)

        if performer_df.height == 0:
            return None

        return performer_df.to_dicts()[0]
    except Exception as e:
        console.print(f"[red]Error looking up Stashapp performer: {e}[/red]")
        return None


def search_stashapp_performers(
    stashapp_client: StashAppClient, query: str
) -> list[dict]:
    """Search for performers in Stashapp by name or ID.

    Args:
        stashapp_client: Stashapp client
        query: Search query (name or numeric ID)

    Returns:
        List of matching performer dictionaries
    """
    try:
        df = stashapp_client.get_performers()

        # Check if query is a numeric ID
        if query.isdigit():
            performer_df = df.filter(df["stashapp_id"] == int(query))
        else:
            # Search by name (case-insensitive contains)
            performer_df = df.filter(
                df["stashapp_name"].str.to_lowercase().str.contains(query.lower())
            )

        return performer_df.to_dicts()
    except Exception as e:
        console.print(f"[red]Error searching Stashapp performers: {e}[/red]")
        return []


def search_stashdb_performers(query: str) -> list[dict]:
    """Search for performers in StashDB by name or ID.

    Args:
        query: Search query (name or UUID)

    Returns:
        List of matching performer dictionaries with id, name, and image_url
    """
    endpoint = os.getenv("STASHDB_ENDPOINT", "https://stashdb.org/graphql")
    api_key = os.getenv("STASHDB_API_KEY", "")
    stashdb_client = StashDbClient(endpoint, api_key)

    # Check if query looks like a UUID
    is_uuid = len(query) == 36 and query.count("-") == 4

    if is_uuid:
        # Query by ID
        gql_query = """
            query FindPerformer($id: ID!) {
                findPerformer(id: $id) {
                    id
                    name
                    disambiguation
                    country
                    images {
                        id
                        url
                    }
                }
            }
        """
        result = stashdb_client._gql_query(gql_query, {"id": query})
        if result and result.get("data", {}).get("findPerformer"):
            performer = result["data"]["findPerformer"]
            images = performer.get("images", [])
            return [{
                "id": performer["id"],
                "name": performer["name"],
                "disambiguation": performer.get("disambiguation"),
                "country": performer.get("country"),
                "image_url": images[0]["url"] if images else None,
            }]
        return []

    # Search by name
    gql_query = """
        query SearchPerformers($term: String!) {
            searchPerformer(term: $term, limit: 10) {
                id
                name
                disambiguation
                country
                images {
                    id
                    url
                }
            }
        }
    """
    result = stashdb_client._gql_query(gql_query, {"term": query})
    if result and result.get("data", {}).get("searchPerformer"):
        performers = result["data"]["searchPerformer"]
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "disambiguation": p.get("disambiguation"),
                "country": p.get("country"),
                "image_url": p["images"][0]["url"] if p.get("images") else None,
            }
            for p in performers
        ]
    return []


def get_stashapp_performer_image_url(stashapp_client: StashAppClient, performer_id: int) -> str | None:
    """Get the image URL for a Stashapp performer.

    Args:
        stashapp_client: Stashapp client
        performer_id: Stashapp performer ID

    Returns:
        Image URL or None if not found
    """
    try:
        performer = stashapp_client.stash.find_performer(
            performer_id,
            fragment="id name image_path",
        )
        if performer and performer.get("image_path"):
            # Build full URL from stash endpoint
            scheme = os.getenv("STASHAPP_SCHEME", "https")
            host = os.getenv("STASHAPP_HOST", "localhost")
            port = os.getenv("STASHAPP_PORT", "9999")
            api_key = os.getenv("STASHAPP_API_KEY", "")

            base_url = f"{scheme}://{host}:{port}{performer['image_path']}"

            # Add API key to URL if available
            if api_key:
                separator = "&" if "?" in base_url else "?"
                return f"{base_url}{separator}apikey={api_key}"
            return base_url
        return None
    except Exception as e:
        console.print(f"[red]Error getting Stashapp performer image: {e}[/red]")
        return None


def display_manual_search_results(  # noqa: PLR0912, PLR0915
    performers: list[dict],
    source: str,
    console: Console,
    stashapp_client: StashAppClient | None = None,
    show_image: bool = False,
    ce_image_path: Path | None = None,
) -> dict | None:
    """Display manual search results and let user select one.

    Args:
        performers: List of performer dictionaries from search
        source: Source name ("stashapp" or "stashdb")
        console: Rich console for output
        stashapp_client: Stashapp client (needed for stashapp image URLs)
        show_image: Whether to display images for comparison
        ce_image_path: Path to CE performer image for comparison

    Returns:
        Selected performer dict or None if cancelled
    """
    if not performers:
        console.print(f"[yellow]No performers found in {source}[/yellow]")
        return None

    table = Table(title=f"{source.upper()} Search Results", show_header=True)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Name", style="green")

    if source == "stashdb":
        table.add_column("Disambiguation", style="dim")
        table.add_column("Country", style="yellow")
        table.add_column("ID", style="blue")

        for i, p in enumerate(performers, 1):
            table.add_row(
                str(i),
                p.get("name", "Unknown"),
                p.get("disambiguation") or "",
                p.get("country") or "?",
                p.get("id", "N/A"),
            )
    else:  # stashapp
        table.add_column("Gender", style="yellow")
        table.add_column("ID", style="blue")
        table.add_column("StashDB ID", style="magenta")

        for i, p in enumerate(performers, 1):
            table.add_row(
                str(i),
                p.get("stashapp_name", "Unknown"),
                p.get("stashapp_gender") or "?",
                str(p.get("stashapp_id", "N/A")),
                p.get("stashapp_stashdb_id") or "N/A",
            )

    console.print(table)

    # Show CE image once if available
    if show_image and ce_image_path and ce_image_path.exists():
        console.print("\n[bold cyan]CE Performer Image:[/bold cyan]")
        display_image_viu(ce_image_path, width=40)

    while True:
        try:
            choice = console.input(
                f"[cyan]Select performer (1-{len(performers)}, 'v' to view image, 0 to cancel): [/cyan]"
            ).strip().lower()

            if choice == "0":
                return None

            if choice == "v" and show_image:
                # Ask which performer to view
                view_choice = console.input(
                    f"[cyan]View image for performer (1-{len(performers)}): [/cyan]"
                ).strip()
                if view_choice.isdigit():
                    view_num = int(view_choice)
                    if 1 <= view_num <= len(performers):
                        performer = performers[view_num - 1]
                        image_url = None

                        if source == "stashdb":
                            image_url = performer.get("image_url")
                        elif source == "stashapp" and stashapp_client:
                            image_url = get_stashapp_performer_image_url(
                                stashapp_client, performer.get("stashapp_id")
                            )

                        if image_url:
                            temp_path = download_stashdb_image(image_url)
                            if temp_path:
                                name = performer.get("name") or performer.get("stashapp_name", "Unknown")
                                console.print(f"\n[bold cyan]{name}:[/bold cyan]")
                                display_image_viu(temp_path, width=40)
                                temp_path.unlink(missing_ok=True)
                        else:
                            console.print("[yellow]No image available for this performer[/yellow]")
                continue

            if choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(performers):
                    return performers[choice_num - 1]

            console.print(f"[red]Please enter 1-{len(performers)}, 'v' to view image, or 0 to cancel[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/yellow]")
            return None


def prompt_manual_search(console: Console) -> tuple[str, str] | None:
    """Prompt user for manual search parameters.

    Args:
        console: Rich console for output

    Returns:
        Tuple of (source, query) or None if cancelled
    """
    console.print("\n[bold cyan]Manual Search[/bold cyan]")
    console.print("  1. StashDB")
    console.print("  2. Stashapp")
    console.print("  [dim]q. Cancel[/dim]")

    # Ask for source
    while True:
        try:
            source_input = console.input("[cyan]Select source: [/cyan]").strip().lower()
            if source_input in ("q", "quit", "exit"):
                return None
            if source_input == "1":
                source = "stashdb"
                break
            if source_input == "2":
                source = "stashapp"
                break
            console.print("[yellow]Please enter 1, 2, or 'q' to cancel[/yellow]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return None

    # Ask for search query
    try:
        query = console.input("[cyan]Search query (name or ID): [/cyan]").strip()
        if not query or query.lower() in ("q", "quit", "exit"):
            return None
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None

    return source, query


def run_manual_search_workflow(  # noqa: PLR0912, PLR0915
    ce_performer: dict,
    ce_client: ClientCultureExtractor,
    stashapp_client: StashAppClient,
    source: str,
    query: str,
    image_path: Path | None,
    show_image: bool,
) -> bool:
    """Run the manual search workflow to link a performer.

    Args:
        ce_performer: CE performer dictionary
        ce_client: Culture Extractor client
        stashapp_client: Stashapp client
        source: Source to search ("stashapp" or "stashdb")
        query: Search query (name or ID)
        image_path: Path to CE performer image for comparison
        show_image: Whether to display images

    Returns:
        True if performer was linked, False otherwise
    """
    console.print(f"\n[bold]Searching {source.upper()} for: {query}[/bold]")

    performers = search_stashapp_performers(stashapp_client, query) if source == "stashapp" else search_stashdb_performers(query)

    selected = display_manual_search_results(
        performers,
        source,
        console,
        stashapp_client=stashapp_client,
        show_image=show_image,
        ce_image_path=image_path,
    )
    if not selected:
        return False

    stashapp_id = None
    stashdb_id = None
    match_image_url = None

    if source == "stashapp":
        stashapp_id = selected.get("stashapp_id")
        stashdb_id = selected.get("stashapp_stashdb_id")
        match_image_url = get_stashapp_performer_image_url(stashapp_client, stashapp_id)
        match_name = selected.get("stashapp_name", "Unknown")
    else:
        stashdb_id = selected.get("id")
        match_image_url = selected.get("image_url")
        match_name = selected.get("name", "Unknown")
        # Look up in Stashapp by StashDB ID
        if stashdb_id:
            stashapp_performer = lookup_stashapp_performer(stashapp_client, stashdb_id)
            if stashapp_performer:
                stashapp_id = stashapp_performer.get("stashapp_id")
                console.print(f"[green]✓ Also found in Stashapp: ID {stashapp_id}[/green]")

    # Display comparison if images are available
    if show_image:
        console.print("\n[bold cyan]Visual Comparison:[/bold cyan]")

        if image_path and image_path.exists():
            display_image_viu(image_path, width=40, label="CE Performer Image")

        if match_image_url:
            console.print()
            match_image_path = download_stashdb_image(match_image_url)
            if match_image_path:
                display_image_viu(match_image_path, width=40, label=f"Match: {match_name}")
                match_image_path.unlink(missing_ok=True)

    # Display summary
    panel_content = []
    panel_content.append("[bold cyan]Culture Extractor Performer:[/bold cyan]")
    panel_content.append(f"  Name: {ce_performer.get('ce_performers_name', 'Unknown')}")
    panel_content.append(f"  UUID: {ce_performer.get('ce_performers_uuid', 'N/A')}")
    panel_content.append("\n[bold green]Selected Match:[/bold green]")
    panel_content.append(f"  Name: {match_name}")
    if stashdb_id:
        panel_content.append(f"  StashDB ID: {stashdb_id}")
    if stashapp_id:
        panel_content.append(f"  Stashapp ID: {stashapp_id}")

    console.print(Panel("\n".join(panel_content), title="Proposed Manual Link", border_style="green"))

    # Confirm
    while True:
        try:
            response = input("\033[1;36mLink this performer? (y/n): \033[0m").strip().lower()
            if response in ("y", "yes"):
                break
            if response in ("n", "no"):
                console.print("[yellow]Cancelled. No changes made.[/yellow]")
                return False
            print("\033[33mPlease enter 'y' or 'n'\033[0m")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return False

    # Link the performer
    ce_performer_uuid = ce_performer.get("ce_performers_uuid")
    link_performer(ce_client, ce_performer_uuid, stashapp_id, stashdb_id)

    console.print("\n[bold green]✅ Successfully linked performer![/bold green]")
    return True


def reset_terminal():
    """Reset terminal state after viu display.

    viu can leave the terminal in alternate screen or with modified input settings.
    This function resets terminal state and flushes input buffers.
    """
    # Reset terminal state
    subprocess.run(["stty", "sane"], check=False, capture_output=True)

    # Save and restore terminal settings to clear any buffered input
    try:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        # Flush input buffer
        termios.tcflush(fd, termios.TCIFLUSH)

        # Restore settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        # If terminal manipulation fails, just continue
        pass

    # Give terminal time to settle
    time.sleep(0.1)

    # Flush all output buffers
    sys.stdout.flush()
    sys.stderr.flush()


def display_image_viu(image_path: Path, width: int = 40, label: str = ""):
    """Display an image using viu.

    Args:
        image_path: Path to the image file
        width: Width in columns (default: 40)
        label: Optional label to display above the image
    """
    try:
        if label:
            console.print(f"[bold]{label}[/bold]")

        # Run viu with the image
        result = subprocess.run(
            ["viu", "-w", str(width), str(image_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print(result.stdout, end="")
        else:
            console.print(f"[yellow]Could not display image with viu: {result.stderr}[/yellow]")
            console.print(f"[dim]Image: {image_path}[/dim]")

    except FileNotFoundError:
        console.print("[yellow]viu not found. Install with: brew install viu[/yellow]")
        console.print(f"[dim]Image: {image_path}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Could not display image: {e}[/yellow]")
        console.print(f"[dim]Image: {image_path}[/dim]")
    finally:
        # Always reset terminal after viu display
        reset_terminal()


def download_stashdb_image(image_url: str) -> Path | None:
    """Download an image from StashDB.

    Args:
        image_url: URL to the StashDB image

    Returns:
        Path to the downloaded temporary file or None if download failed
    """
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        # Create a temporary file
        suffix = ".jpg"
        if "png" in image_url.lower():
            suffix = ".png"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name

        return Path(temp_path)

    except Exception as e:
        console.print(f"[yellow]Could not download StashDB image: {e}[/yellow]")
        return None


def display_match_summary(
    ce_performer: dict,
    match: dict,
    stashapp_performer: dict | None,
    image_path: Path | None = None,
    force_image: bool = False,
):
    """Display a summary of the proposed match.

    Args:
        ce_performer: CE performer details
        match: Face recognition match result
        stashapp_performer: Stashapp performer details (if found)
        image_path: Optional path to performer image for display
        force_image: Force display image regardless of terminal detection
    """
    # Display images side by side if available
    stashdb_image_path = None
    if force_image:
        console.print("\n[bold cyan]Visual Comparison:[/bold cyan]")

        # Display CE performer image
        if image_path and image_path.exists():
            display_image_viu(image_path, width=40, label="CE Performer Image")

        # Download and display StashDB image
        stashdb_image_url = match.get("image")
        if stashdb_image_url:
            console.print()  # Add spacing
            stashdb_image_path = download_stashdb_image(stashdb_image_url)
            if stashdb_image_path:
                display_image_viu(
                    stashdb_image_path,
                    width=40,
                    label=f"StashDB Match: {match.get('name', 'Unknown')}",
                )

    # Display text summary
    panel_content = []

    panel_content.append("[bold cyan]Culture Extractor Performer:[/bold cyan]")
    panel_content.append(f"  Name: {ce_performer.get('ce_performers_name', 'Unknown')}")
    panel_content.append(f"  UUID: {ce_performer.get('ce_performers_uuid', 'N/A')}")
    panel_content.append(f"  Site: {ce_performer.get('ce_sites_name', 'Unknown')}")

    panel_content.append("\n[bold green]Face Recognition Match:[/bold green]")
    panel_content.append(f"  Name: {match.get('name', 'Unknown')}")
    panel_content.append(f"  Confidence: {match.get('confidence', 0)}%")
    panel_content.append(f"  Country: {match.get('country', '?')}")

    stashdb_id = match.get("performer_url", "").split("/")[-1] if match.get("performer_url") else None
    if stashdb_id:
        panel_content.append(f"  StashDB ID: {stashdb_id}")
        panel_content.append(f"  Profile: {match.get('performer_url', 'N/A')}")

    stashdb_image_url = match.get("image")
    if stashdb_image_url:
        panel_content.append(f"  Photo: {stashdb_image_url}")

    if stashapp_performer:
        panel_content.append("\n[bold magenta]Stashapp Performer:[/bold magenta]")
        panel_content.append(f"  ID: {stashapp_performer.get('stashapp_id', 'N/A')}")
        panel_content.append(f"  Name: {stashapp_performer.get('stashapp_name', 'Unknown')}")
        panel_content.append(f"  Gender: {stashapp_performer.get('stashapp_gender', 'N/A')}")
        panel_content.append(f"  Favorite: {'⭐ Yes' if stashapp_performer.get('stashapp_favorite') else 'No'}")
    else:
        panel_content.append("\n[yellow]⚠ Performer not found in Stashapp[/yellow]")

    if not force_image:
        panel_content.append("\n[dim]Use --show-image to display images[/dim]")

    console.print(Panel("\n".join(panel_content), title="Proposed Match", border_style="green"))

    # Clean up temporary file
    if stashdb_image_path and stashdb_image_path.exists():
        with suppress(Exception):
            stashdb_image_path.unlink()


def link_performer(
    ce_client: ClientCultureExtractor,
    ce_performer_uuid: str,
    stashapp_id: int | None,
    stashdb_id: str | None,
):
    """Link the CE performer to external IDs.

    Args:
        ce_client: Culture Extractor client
        ce_performer_uuid: CE performer UUID
        stashapp_id: Stashapp performer ID (optional)
        stashdb_id: StashDB performer UUID (optional)
    """
    try:
        links = []
        if stashapp_id is not None:
            ce_client.set_performer_external_id(ce_performer_uuid, "stashapp", str(stashapp_id))
            links.append(f"Stashapp ID: {stashapp_id}")

        if stashdb_id is not None:
            ce_client.set_performer_external_id(ce_performer_uuid, "stashdb", stashdb_id)
            links.append(f"StashDB ID: {stashdb_id}")

        if links:
            console.print(f"[bold green]✓ Successfully linked performer to {', '.join(links)}[/bold green]")
        else:
            console.print("[yellow]⚠ No links created (no valid IDs provided)[/yellow]")

    except Exception as e:
        console.print(f"[red]Error linking performer: {e}[/red]")
        raise


def select_match(matches: list[dict], console: Console) -> dict | str | None:
    """Select a match from the list, handling single or multiple matches.

    Args:
        matches: List of face recognition matches
        console: Rich console for output

    Returns:
        Selected match dict, "manual" for manual search, or None if skipped
    """
    console.print("[yellow]Select a match:[/yellow]")
    for i, match in enumerate(matches, 1):
        console.print(f"  {i}. {match.get('name', 'Unknown')} ({match.get('confidence', 0)}%)")
    console.print("  [dim]m. Manual search[/dim]")
    console.print("  [dim]s. Skip[/dim]")

    while True:
        try:
            choice = console.input("[cyan]Enter choice: [/cyan]").strip().lower()
            if choice == "s":
                return None
            if choice == "m":
                return "manual"
            if choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(matches):
                    return matches[choice_num - 1]
            console.print(f"[red]Please enter 1-{len(matches)}, 'm' for manual, or 's' to skip[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/yellow]")
            return None


def extract_stashdb_id_from_url(performer_url: str | None) -> str | None:
    """Extract StashDB ID from performer URL.

    Args:
        performer_url: URL to StashDB performer profile

    Returns:
        StashDB UUID or None
    """
    if not performer_url:
        return None
    return performer_url.split("/")[-1]


def offer_manual_search(
    ce_performer: dict,
    ce_client: ClientCultureExtractor,
    stashapp_client: StashAppClient,
    image_path: Path | None,
    show_image: bool,
) -> bool:
    """Offer the user to do a manual search.

    Args:
        ce_performer: CE performer dictionary
        ce_client: Culture Extractor client
        stashapp_client: Stashapp client
        image_path: Path to CE performer image
        show_image: Whether to display images

    Returns:
        True if performer was linked via manual search, False otherwise
    """
    while True:
        try:
            response = console.input(
                "[cyan]Would you like to search manually? (y/n): [/cyan]"
            ).strip().lower()
            if response in ("n", "no"):
                return False
            if response in ("y", "yes"):
                break
            console.print("[yellow]Please enter 'y' or 'n'[/yellow]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return False

    search_params = prompt_manual_search(console)
    if not search_params:
        return False

    source, query = search_params
    return run_manual_search_workflow(
        ce_performer,
        ce_client,
        stashapp_client,
        source,
        query,
        image_path,
        show_image,
    )


def run_matching_workflow(  # noqa: PLR0915, PLR0912
    performer_uuid: str,
    threshold: float,
    max_results: int,
    auto_approve: bool,
    show_image: bool = False,
    force: bool = False,
):
    """Execute the complete matching workflow.

    Args:
        performer_uuid: CE performer UUID
        threshold: Face recognition threshold
        max_results: Maximum number of face matches
        auto_approve: Auto-approve 100% confidence matches
        show_image: Force image display using kitty protocol
        force: Process performer even if already linked
    """
    # Initialize clients
    console.print("[blue]Initializing clients...[/blue]")
    ce_client = config.get_client()
    stashapp_client = StashAppClient()

    # Step 1: Get CE performer
    console.print(f"\n[bold]Step 1: Fetching CE performer {performer_uuid}[/bold]")
    ce_performer = get_ce_performer(ce_client, performer_uuid)
    if not ce_performer:
        console.print(f"[red]✗ Performer with UUID '{performer_uuid}' not found[/red]")
        sys.exit(1)

    performer_name = ce_performer.get("ce_performers_name", "Unknown")
    console.print(f"[green]✓ Found: {performer_name}[/green]")

    # Check if performer already has external IDs (unless --force is used)
    if not force:
        existing_external_ids = ce_client.get_performer_external_ids(performer_uuid)
        has_stashapp = "stashapp" in existing_external_ids
        has_stashdb = "stashdb" in existing_external_ids

        if has_stashapp and has_stashdb:
            stashapp_id = existing_external_ids.get("stashapp", "unknown")
            stashdb_id = existing_external_ids.get("stashdb", "unknown")
            console.print(
                f"[yellow]⊘ Skipping '{performer_name}' - already linked[/yellow]\n"
                f"  Stashapp ID: {stashapp_id}\n"
                f"  StashDB ID: {stashdb_id}\n"
                f"  [dim]Use --force to process anyway[/dim]"
            )
            sys.exit(0)

    # Step 2: Get performer image
    console.print("\n[bold]Step 2: Locating performer image[/bold]")
    image_path, site_name = get_performer_image_path(ce_performer)
    if not image_path:
        console.print("[red]✗ Could not find performer image[/red]")
        site_display = site_name.title() if site_name else "<site>"
        console.print(f"[yellow]Expected location: /Volumes/Ripping/{site_display}/Performers/{performer_uuid}/{performer_uuid}.jpg[/yellow]")  # noqa: E501
        console.print("[dim]Note: The performer UUID in CE database may not match the filesystem UUID[/dim]")

        # Offer manual search as fallback
        if offer_manual_search(ce_performer, ce_client, stashapp_client, None, show_image):
            return
        sys.exit(1)
    console.print(f"[green]✓ Found image: {image_path}[/green]")

    # Step 3: Run face recognition
    console.print("\n[bold]Step 3: Running face recognition[/bold]")
    face_results = run_face_recognition(image_path, threshold, max_results)

    # Step 4: Display and select match
    console.print("\n[bold]Step 4: Face recognition results[/bold]")
    matches = display_face_matches(face_results)
    if not matches:
        console.print("[yellow]No matches found from face recognition.[/yellow]")
        # Offer manual search as fallback
        if offer_manual_search(ce_performer, ce_client, stashapp_client, image_path, show_image):
            return
        sys.exit(0)

    console.print("\n[bold]Step 5: Select match[/bold]")
    selected_match = select_match(matches, console)
    if selected_match == "manual":
        # User chose manual search
        search_params = prompt_manual_search(console)
        if search_params:
            source, query = search_params
            if run_manual_search_workflow(
                ce_performer, ce_client, stashapp_client, source, query, image_path, show_image
            ):
                return
        sys.exit(0)
    if not selected_match:
        # User skipped
        sys.exit(0)

    # Step 6: Look up in Stashapp
    console.print("\n[bold]Step 6: Looking up performer in Stashapp[/bold]")
    stashdb_id = extract_stashdb_id_from_url(selected_match.get("performer_url"))
    stashapp_performer = None

    if stashdb_id:
        stashapp_performer = lookup_stashapp_performer(stashapp_client, stashdb_id)
        if stashapp_performer:
            name = stashapp_performer.get("stashapp_name", "Unknown")
            pid = stashapp_performer.get("stashapp_id")
            console.print(f"[green]✓ Found in Stashapp: {name} (ID: {pid})[/green]")
        else:
            console.print("[yellow]⚠ Not found in Stashapp[/yellow]")
    else:
        console.print("[yellow]⚠ No StashDB ID found in match[/yellow]")

    # Step 7: Review and confirm
    console.print("\n[bold]Step 7: Review and confirm[/bold]")
    display_match_summary(ce_performer, selected_match, stashapp_performer, image_path, show_image)

    should_approve = auto_approve and selected_match.get("confidence") == 100
    if should_approve:
        console.print("\n[green]Auto-approving (100% confidence match)[/green]")
    else:
        # Simple yes/no prompt that accepts y/Y/n/N
        while True:
            try:
                response = input("\033[1;36mLink this performer? (y/n): \033[0m").strip().lower()
                if response in ("y", "yes"):
                    should_approve = True
                    break
                if response in ("n", "no"):
                    should_approve = False
                    break
                print("\033[33mPlease enter 'y' or 'n'\033[0m")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Cancelled. Exiting.[/yellow]")
                sys.exit(0)

    if not should_approve:
        console.print("[yellow]Match rejected.[/yellow]")
        # Offer manual search as fallback
        if offer_manual_search(ce_performer, ce_client, stashapp_client, image_path, show_image):
            return
        console.print("[yellow]No changes made.[/yellow]")
        sys.exit(0)

    # Step 8: Link the performer
    console.print("\n[bold]Step 8: Linking performer[/bold]")
    stashapp_id = stashapp_performer.get("stashapp_id") if stashapp_performer else None
    link_performer(ce_client, performer_uuid, stashapp_id, stashdb_id)

    console.print("\n[bold green]✅ Successfully completed performer matching![/bold green]")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive performer face matching and linking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python match_performer_face.py 01958935-af28-73a6-8f67-e272112f8e3b
  python match_performer_face.py uuid1 uuid2 uuid3
  python match_performer_face.py 01958935-af28-73a6-8f67-e272112f8e3b --threshold 0.8
  python match_performer_face.py 01958935-af28-73a6-8f67-e272112f8e3b --auto-approve
  python match_performer_face.py 01958935-af28-73a6-8f67-e272112f8e3b --show-image
        """,
    )

    parser.add_argument(
        "performer_uuids",
        nargs="+",
        help="One or more Culture Extractor performer UUIDs",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Face recognition confidence threshold (0.0-1.0, default: 0.5)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=3,
        help="Maximum number of face matches to show (default: 3)",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve matches with 100%% confidence",
    )
    parser.add_argument(
        "--show-image",
        action="store_true",
        help="Display images (CE performer + StashDB match) using viu",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Process performer even if already linked to external IDs",
    )

    args = parser.parse_args()

    if not 0.0 <= args.threshold <= 1.0:
        console.print("[red]Error: Threshold must be between 0.0 and 1.0[/red]")
        sys.exit(1)

    total = len(args.performer_uuids)
    for i, performer_uuid in enumerate(args.performer_uuids, 1):
        if total > 1:
            console.print(f"\n[bold blue]{'=' * 60}[/bold blue]")
            console.print(f"[bold blue]Processing performer {i}/{total}: {performer_uuid}[/bold blue]")
            console.print(f"[bold blue]{'=' * 60}[/bold blue]")

        try:
            run_matching_workflow(
                performer_uuid,
                args.threshold,
                args.max_results,
                args.auto_approve,
                args.show_image,
                args.force,
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled by user. Exiting.[/yellow]")
            sys.exit(130)
        except SystemExit:
            # Allow sys.exit() calls from workflow to pass through for single UUID
            # For multiple UUIDs, continue to next performer
            if total == 1:
                raise
            console.print("[yellow]Moving to next performer...[/yellow]")
            continue
        except Exception as e:
            console.print(f"\n[red]Error processing {performer_uuid}: {e}[/red]")
            traceback.print_exc()
            if total == 1:
                sys.exit(1)
            console.print("[yellow]Moving to next performer...[/yellow]")
            continue

    if total > 1:
        console.print(f"\n[bold green]Finished processing {total} performers.[/bold green]")


if __name__ == "__main__":
    main()
