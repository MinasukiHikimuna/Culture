"""Main CLI application for Culture operations."""

import typer

from culture_cli.commands import sync
from culture_cli.modules.ce.cli import ce_app
from culture_cli.modules.stash.cli import stash_app


app = typer.Typer(
    name="culture",
    help="Unified CLI for culture data management and synchronization",
    add_completion=True,
)

# Register sync command
app.command("sync")(sync.sync_scene)

# Register module subcommands
app.add_typer(ce_app, name="ce", help="Culture Extractor operations")
app.add_typer(stash_app, name="stash", help="Stashapp operations")


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        from culture_cli import __version__

        typer.echo(f"culture version {__version__}")
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
    """Culture CLI - Unified tool for culture data operations."""


if __name__ == "__main__":
    app()
