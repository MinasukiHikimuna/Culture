"""Main CLI application for Stashapp operations."""

import typer
from stash_cli.commands import performers, scenes

app = typer.Typer(
    name="stash-cli",
    help="Command-line interface for Stashapp database operations",
    add_completion=True,
)

# Register command groups
app.add_typer(performers.app, name="performers", help="Manage and query performers")
app.add_typer(scenes.app, name="scenes", help="Manage and query scenes")


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        from stash_cli import __version__

        typer.echo(f"stash-cli version {__version__}")
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
    """Stashapp CLI - Interact with your Stashapp database."""
    pass


if __name__ == "__main__":
    app()
