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
import subprocess
import sys
import tempfile
import termios
import time
import traceback
from contextlib import suppress
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from culture_cli.modules.ce.utils.config import config
from libraries.client_culture_extractor import ClientCultureExtractor
from libraries.client_stashapp import StashAppClient
from stashface_api_client import StashfaceAPIClient


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


def select_match(matches: list[dict], console: Console) -> dict | None:
    """Select a match from the list, handling single or multiple matches.

    Args:
        matches: List of face recognition matches
        console: Rich console for output

    Returns:
        Selected match or None if cancelled
    """
    if len(matches) == 1:
        selected_match = matches[0]
        console.print(
            f"[cyan]Auto-selecting only match: {selected_match.get('name', 'Unknown')}[/cyan]"
        )
        return selected_match

    console.print("[yellow]Multiple matches found. Please select one:[/yellow]")
    for i, match in enumerate(matches, 1):
        console.print(f"  {i}. {match.get('name', 'Unknown')} ({match.get('confidence', 0)}%)")

    while True:
        try:
            choice = console.input(f"[cyan]Enter choice (1-{len(matches)}, 0 to skip): [/cyan]")
            choice_num = int(choice)
            if choice_num == 0:
                console.print("[yellow]Skipping. Exiting.[/yellow]")
                return None
            if 1 <= choice_num <= len(matches):
                return matches[choice_num - 1]
            console.print(f"[red]Please enter a number between 0 and {len(matches)}[/red]")
        except (ValueError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled. Exiting.[/yellow]")
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
        console.print("[dim]Consider manually locating the image or linking the performer through Stashapp directly[/dim]")  # noqa: E501
        sys.exit(1)
    console.print(f"[green]✓ Found image: {image_path}[/green]")

    # Step 3: Run face recognition
    console.print("\n[bold]Step 3: Running face recognition[/bold]")
    face_results = run_face_recognition(image_path, threshold, max_results)

    # Step 4: Display and select match
    console.print("\n[bold]Step 4: Face recognition results[/bold]")
    matches = display_face_matches(face_results)
    if not matches:
        console.print("[yellow]No matches found. Exiting.[/yellow]")
        sys.exit(0)

    console.print("\n[bold]Step 5: Select match[/bold]")
    selected_match = select_match(matches, console)
    if not selected_match:
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
        # Reset terminal state after viu display
        # viu can leave the terminal in alternate screen or with modified input settings
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

        # Print newline to ensure we're on a clean line
        print()

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
        console.print("[yellow]Cancelled. No changes made.[/yellow]")
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
  python match_performer_face.py 01958935-af28-73a6-8f67-e272112f8e3b --threshold 0.8
  python match_performer_face.py 01958935-af28-73a6-8f67-e272112f8e3b --auto-approve
  python match_performer_face.py 01958935-af28-73a6-8f67-e272112f8e3b --show-image
        """,
    )

    parser.add_argument("performer_uuid", help="Culture Extractor performer UUID")
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

    try:
        run_matching_workflow(
            args.performer_uuid,
            args.threshold,
            args.max_results,
            args.auto_approve,
            args.show_image,
            args.force,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user. Exiting.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
