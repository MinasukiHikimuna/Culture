"""Stashapp module for the Culture CLI."""

import typer

from culture_cli.modules.stash.commands import performers, scenes, tags


stash_app = typer.Typer(
    name="stash",
    help="Stashapp database operations",
    add_completion=False,
)

# Register command groups
stash_app.add_typer(performers.app, name="performers", help="Manage and query performers")
stash_app.add_typer(scenes.app, name="scenes", help="Manage and query scenes")
stash_app.add_typer(tags.app, name="tags", help="Manage and query tags")
