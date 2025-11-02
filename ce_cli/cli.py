"""Main CLI application for Culture Extractor operations."""

import typer
from ce_cli.commands.performers import performers_app
from ce_cli.commands.releases import releases_app
from ce_cli.commands.sites import sites_app

app = typer.Typer(
    name="ce",
    help="Command-line interface for Culture Extractor database operations",
    add_completion=True,
)

# Register command groups
app.add_typer(sites_app, name="sites", help="Manage and query sites")
app.add_typer(releases_app, name="releases", help="Manage and query releases")
app.add_typer(performers_app, name="performers", help="Manage and query performers")


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        from ce_cli import __version__

        typer.echo(f"ce version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Culture Extractor CLI - Interact with your Culture Extractor database."""
    pass


if __name__ == "__main__":
    app()
