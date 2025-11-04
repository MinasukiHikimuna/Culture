"""Culture Extractor module for the Culture CLI."""

import typer

from culture_cli.modules.ce.commands.performers import performers_app
from culture_cli.modules.ce.commands.releases import releases_app
from culture_cli.modules.ce.commands.sites import sites_app
from culture_cli.modules.ce.commands.tags import tags_app


ce_app = typer.Typer(
    name="ce",
    help="Culture Extractor database operations",
    add_completion=False,
)

# Register command groups
ce_app.add_typer(sites_app, name="sites", help="Manage and query sites")
ce_app.add_typer(releases_app, name="releases", help="Manage and query releases")
ce_app.add_typer(performers_app, name="performers", help="Manage and query performers")
ce_app.add_typer(tags_app, name="tags", help="Manage and query tags")
