"""Tags-related commands for the CLI."""

from typing import Annotated

import typer

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    print_error,
    print_info,
    print_success,
)


# Create tags command group
tags_app = typer.Typer(help="Manage Culture Extractor tags")


@tags_app.command("link")
def link_tag(
    uuid: Annotated[str, typer.Argument(help="Tag UUID to link")],
    stashapp_id: Annotated[
        int | None,
        typer.Option("--stashapp-id", help="Stashapp tag ID"),
    ] = None,
    stashdb_id: Annotated[
        str | None,
        typer.Option("--stashdb-id", help="StashDB tag ID (UUID/GUID)"),
    ] = None,
) -> None:
    """Link a Culture Extractor tag to external systems.

    Sets external IDs for a tag, allowing you to associate them with
    Stashapp tags, StashDB entries, etc.

    Examples:
        ce tags link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345
        ce tags link 018f1477-f285-726b-9136-21956e3e8b92 --stashdb-id "a1b2c3d4-..."
        ce tags link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345 --stashdb-id "a1b2c3d4-..."
    """
    try:
        # Validate that at least one ID was provided
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        # Get Culture Extractor client
        client = config.get_client()

        # Verify tag exists
        tag_df = client.get_tag_by_uuid(uuid)
        if tag_df.shape[0] == 0:
            print_error(f"Tag with UUID '{uuid}' not found")
            raise typer.Exit(code=1)

        tag_name = tag_df["ce_tags_name"][0]

        # Set external IDs
        links = []
        if stashapp_id is not None:
            client.set_tag_external_id(uuid, "stashapp", str(stashapp_id))
            links.append(f"Stashapp ID: {stashapp_id}")
        if stashdb_id is not None:
            client.set_tag_external_id(uuid, "stashdb", stashdb_id)
            links.append(f"StashDB ID: {stashdb_id}")

        print_success(f"Linked tag '{tag_name}' to {', '.join(links)}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to link tag: {e}")
        raise typer.Exit(code=1) from e
