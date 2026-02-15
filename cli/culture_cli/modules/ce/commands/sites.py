"""Sites-related commands for the CLI."""

from typing import Annotated

import httpx
import typer

from culture_cli.api_client import CultureAPIClient
from culture_cli.modules.ce.utils.formatters import (
    format_sites_table,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)


# Create sites command group
sites_app = typer.Typer(help="Manage Culture Extractor sites")


def _get_api_client() -> CultureAPIClient:
    """Get an API client instance."""
    return CultureAPIClient()


@sites_app.command("list")
def list_sites(
    only_linked: Annotated[
        bool,
        typer.Option("--only-linked", help="Show only sites linked to Stashapp/StashDB"),
    ] = False,
    only_unlinked: Annotated[
        bool,
        typer.Option("--only-unlinked", help="Show only sites not linked to Stashapp/StashDB"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List all sites in the Culture Extractor database.

    Examples:
        ce sites list              # Display as a table
        ce sites list --json       # Display as JSON
        ce sites list -j           # Short form for JSON output
        ce sites list --only-linked     # Show only linked sites
        ce sites list --only-unlinked   # Show only unlinked sites
    """
    try:
        if only_linked and only_unlinked:
            print_error("Cannot use both --only-linked and --only-unlinked")
            raise typer.Exit(code=1)

        # Determine linked filter
        linked: bool | None = None
        if only_linked:
            linked = True
        elif only_unlinked:
            linked = False

        # Get sites from API
        with _get_api_client() as api:
            sites = api.get_sites(linked=linked)

        # Check if any results
        if not sites:
            link_filter = "linked" if only_linked else "unlinked" if only_unlinked else ""
            msg = f"No {link_filter} sites found" if link_filter else "No sites found"
            print_info(msg)
            raise typer.Exit(code=0)

        # Display results
        count = len(sites)
        if json_output:
            print_json(sites)
        else:
            table = format_sites_table(sites)
            print_table(table)
            print_success(f"Found {count} sites")

    except httpx.ConnectError:
        print_error("Cannot connect to Culture API. Is the API server running?")
        print_info("Start the API with: cd api && uv run uvicorn api.main:app --port 8000")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
        print_error(f"API error: {detail}")
        raise typer.Exit(code=1) from e


@sites_app.command("link")
def link_site(
    uuid: Annotated[str, typer.Argument(help="Site UUID to link")],
    stashapp_id: Annotated[
        int | None,
        typer.Option("--stashapp-id", help="Stashapp studio ID"),
    ] = None,
    stashdb_id: Annotated[
        str | None,
        typer.Option("--stashdb-id", help="StashDB studio ID (UUID/GUID)"),
    ] = None,
) -> None:
    """Link a Culture Extractor site to external systems.

    Sets external IDs for a site, allowing you to associate them with
    Stashapp studios, StashDB entries, etc.

    Examples:
        ce sites link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345
        ce sites link 018f1477-f285-726b-9136-21956e3e8b92 --stashdb-id "a1b2c3d4-..."
        ce sites link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345 --stashdb-id "a1b2c3d4-..."
    """
    try:
        # Validate that at least one ID was provided
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        with _get_api_client() as api:
            # First verify the site exists by fetching it
            site = api.get_site(uuid)
            site_name = site["ce_sites_name"]

            # Link to external systems
            links = []
            if stashapp_id is not None:
                api.link_site(uuid, "stashapp", str(stashapp_id))
                links.append(f"Stashapp ID: {stashapp_id}")
            if stashdb_id is not None:
                api.link_site(uuid, "stashdb", stashdb_id)
                links.append(f"StashDB ID: {stashdb_id}")

            print_success(f"Linked site '{site_name}' to {', '.join(links)}")

    except httpx.ConnectError:
        print_error("Cannot connect to Culture API. Is the API server running?")
        print_info("Start the API with: cd api && uv run uvicorn api.main:app --port 8000")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print_error(f"Site with UUID '{uuid}' not found")
        else:
            detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
            print_error(f"API error: {detail}")
        raise typer.Exit(code=1) from e


@sites_app.command("create")
def create_site(
    short_name: Annotated[str, typer.Argument(help="Short identifier for the site")],
    name: Annotated[str, typer.Argument(help="Full site name")],
    url: Annotated[str, typer.Argument(help="Base URL of the site")],
    username: Annotated[
        str | None,
        typer.Option("--username", "-u", help="Username for site authentication"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of formatted text"),
    ] = False,
) -> None:
    """Create a new site in the Culture Extractor database.

    Creates a new site with the given identifiers. If --username is provided,
    you will be prompted securely for the password.

    Examples:
        ce sites create example "Example Site" https://example.com
        ce sites create mysite "My Site" https://mysite.com --username user
        ce sites create mysite "My Site" https://mysite.com --json
    """
    try:
        # Prompt for password securely if username is provided
        password: str | None = None
        if username is not None:
            password = typer.prompt("Password", hide_input=True)

        with _get_api_client() as api:
            result = api.create_site(
                short_name=short_name,
                name=name,
                url=url,
                username=username,
                password=password,
            )

        if json_output:
            print_json(result)
        else:
            print_success(f"Created site '{result['name']}' with UUID: {result['uuid']}")

    except httpx.ConnectError:
        print_error("Cannot connect to Culture API. Is the API server running?")
        print_info("Start the API with: cd api && uv run uvicorn api.main:app --port 8000")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
        print_error(f"API error: {detail}")
        raise typer.Exit(code=1) from e
