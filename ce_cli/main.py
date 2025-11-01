"""Main entry point for Culture Extractor CLI."""

import typer
from typing_extensions import Annotated

from ce_cli import __version__
from ce_cli.commands.performers import performers_app
from ce_cli.commands.releases import releases_app
from ce_cli.commands.sites import sites_app


# Create main app
app = typer.Typer(
    name="ce",
    help="Culture Extractor CLI - Manage Culture Extractor database operations",
    add_completion=True,
)

# Register command groups
app.add_typer(sites_app, name="sites")
app.add_typer(releases_app, name="releases")
app.add_typer(performers_app, name="performers")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"Culture Extractor CLI version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True, help="Show version"),
    ] = False,
) -> None:
    """Culture Extractor CLI - A modern command-line interface for Culture Extractor database operations."""
    pass


if __name__ == "__main__":
    app()
