"""StashDB module for the Culture CLI."""

import typer

from culture_cli.modules.stashdb.commands import scenes, scrape


stashdb_app = typer.Typer(
    name="stashdb",
    help="StashDB data lake operations",
    add_completion=False,
)

# Register command groups
stashdb_app.add_typer(scrape.app, name="scrape", help="Scrape data from StashDB")
stashdb_app.add_typer(scenes.app, name="scenes", help="Query scenes in data lake")
