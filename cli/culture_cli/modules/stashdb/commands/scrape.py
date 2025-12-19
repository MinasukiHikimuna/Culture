"""Scrape commands for StashDB data lake."""

import subprocess
import sys

import typer
from rich.console import Console


app = typer.Typer()
console = Console()


@app.command("performer")
def scrape_performer(
    performer_id: str = typer.Argument(..., help="StashDB performer UUID"),
    data_path: str = typer.Option(
        "data/stashdb", "--data-path", "-d", help="Base path for Delta Lake storage"
    ),
    no_images: bool = typer.Option(
        False, "--no-images", help="Skip downloading images"
    ),
) -> None:
    """Scrape all scenes for a StashDB performer.

    Examples:
        culture stashdb scrape performer 12345678-1234-1234-1234-123456789abc
        culture stashdb scrape performer 12345678-1234-1234-1234-123456789abc --no-images
    """
    console.print(f"[blue]Scraping scenes for performer: {performer_id}[/blue]")

    cmd = [
        "scrapy",
        "crawl",
        "stashdb",
        "-a",
        "mode=performer",
        "-a",
        f"performer_id={performer_id}",
        "-a",
        f"data_path={data_path}",
        "-a",
        f"download_images={not no_images}",
    ]

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")

    result = subprocess.run(
        cmd,
        cwd="extractors/scrapy",
        check=False,
    )

    if result.returncode == 0:
        console.print("\n[green]Scrape completed successfully![/green]")
    else:
        console.print(f"\n[red]Scrape failed with exit code {result.returncode}[/red]")
        sys.exit(result.returncode)


@app.command("studio")
def scrape_studio(
    studio_id: str = typer.Argument(..., help="StashDB studio UUID"),
    data_path: str = typer.Option(
        "data/stashdb", "--data-path", "-d", help="Base path for Delta Lake storage"
    ),
    no_images: bool = typer.Option(
        False, "--no-images", help="Skip downloading images"
    ),
) -> None:
    """Scrape all scenes for a StashDB studio.

    Examples:
        culture stashdb scrape studio 12345678-1234-1234-1234-123456789abc
        culture stashdb scrape studio 12345678-1234-1234-1234-123456789abc --no-images
    """
    console.print(f"[blue]Scraping scenes for studio: {studio_id}[/blue]")

    cmd = [
        "scrapy",
        "crawl",
        "stashdb",
        "-a",
        "mode=studio",
        "-a",
        f"studio_id={studio_id}",
        "-a",
        f"data_path={data_path}",
        "-a",
        f"download_images={not no_images}",
    ]

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")

    result = subprocess.run(
        cmd,
        cwd="extractors/scrapy",
        check=False,
    )

    if result.returncode == 0:
        console.print("\n[green]Scrape completed successfully![/green]")
    else:
        console.print(f"\n[red]Scrape failed with exit code {result.returncode}[/red]")
        sys.exit(result.returncode)
