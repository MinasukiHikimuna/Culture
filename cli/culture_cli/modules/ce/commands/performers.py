"""Performers-related commands for the CLI."""

from typing import Annotated

import httpx
import typer
from rich.panel import Panel
from rich.table import Table

from culture_cli.api_client import CultureAPIClient
from culture_cli.modules.ce.utils.formatters import (
    console,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)


# Create performers command group
performers_app = typer.Typer(help="Manage Culture Extractor performers")


@performers_app.command("list")
def list_performers(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by performer name (case-insensitive)"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results (useful when querying all sites)"),
    ] = None,
    only_linked: Annotated[
        bool,
        typer.Option("--only-linked", help="Show only performers linked to Stashapp/StashDB"),
    ] = False,
    only_unlinked: Annotated[
        bool,
        typer.Option("--only-unlinked", help="Show only performers not linked to Stashapp/StashDB"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List performers from a site.

    Examples:
        ce performers list --site meanawolf              # List all performers from Meana Wolf
        ce performers list -s meanawolf -n "Jane"        # Filter by site and name
        ce performers list -s meanawolf --limit 20       # Limit results to 20
        ce performers list --site meanawolf --json       # JSON output
        ce performers list --site meanawolf --only-unlinked  # Show unlinked performers only
    """
    try:
        if only_linked and only_unlinked:
            print_error("Cannot use both --only-linked and --only-unlinked")
            raise typer.Exit(code=1)

        filter_msg = f" matching '{name}'" if name else ""
        print_info(f"Fetching performers from '{site}'{filter_msg}...")

        with CultureAPIClient() as client:
            performers = client.get_performers(site=site, name=name, limit=limit)

        if not performers:
            print_info(_build_not_found_message(site, name))
            raise typer.Exit(code=0)

        # Apply link status filters
        performers = _filter_by_link_status(performers, only_linked, only_unlinked)

        if not performers:
            print_info(_build_filtered_not_found_message(site, name, only_linked, only_unlinked))
            raise typer.Exit(code=0)

        # Display results
        _display_performers(performers, site, name, limit, json_output)

    except httpx.HTTPStatusError as e:
        _handle_http_error(e, "fetch performers")
    except httpx.ConnectError as e:
        print_error("Could not connect to API. Is the server running?")
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch performers: {e}")
        raise typer.Exit(code=1) from e


@performers_app.command("show")
def show_performer(
    uuid: Annotated[str, typer.Argument(help="Performer UUID to display")],
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of formatted view"),
    ] = False,
) -> None:
    """Show detailed information about a specific performer.

    Examples:
        ce performers show 018f1477-f285-726b-9136-21956e3e8b92
        ce performers show 018f1477-f285-726b-9136-21956e3e8b92 --json
    """
    try:
        with CultureAPIClient() as client:
            performer = client.get_performer(uuid)

        if json_output:
            print_json(performer)
        else:
            _print_performer_detail(performer)
            print_success(f"Performer details for {uuid}")

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            detail = e.response.json().get("detail", str(e))
            print_error(detail)
        else:
            print_error(f"API error: {e}")
        raise typer.Exit(code=1) from e
    except httpx.ConnectError as e:
        print_error("Could not connect to API. Is the server running?")
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch performer: {e}")
        raise typer.Exit(code=1) from e


@performers_app.command("unmapped")
def list_unmapped_performers(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="Site to check (short name or UUID)"),
    ],
    target_system: Annotated[
        str,
        typer.Option("--target-system", "-t", help="Target system to check for mappings"),
    ] = "stashapp",
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by performer name (case-insensitive)"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List performers from a site that aren't mapped to an external system.

    Shows performers that don't have external IDs for the specified target system
    (default: stashapp). Useful for identifying performers that still need to be
    linked to external systems.

    Examples:
        ce performers unmapped --site meanawolf                        # List unmapped performers for Meana Wolf
        ce performers unmapped -s meanawolf -t stashdb                 # Check for StashDB mappings
        ce performers unmapped -s meanawolf -n "Jane"                  # Filter by name
        ce performers unmapped -s meanawolf --limit 20                 # Limit results
        ce performers unmapped -s meanawolf --json                     # JSON output
    """
    try:
        filter_msg = f" matching '{name}'" if name else ""
        print_info(f"Fetching performers from '{site}' without '{target_system}' mappings{filter_msg}...")

        with CultureAPIClient() as client:
            performers = client.get_performers(
                site=site,
                name=name,
                unmapped_only=True,
                target_system=target_system,
                limit=limit,
            )

        if not performers:
            msg = f"No unmapped performers found for site '{site}'"
            if name:
                msg += f" matching '{name}'"
            print_info(msg)
            raise typer.Exit(code=0)

        # Display results
        site_name = performers[0].get("ce_site_name") if performers else site
        if json_output:
            print_json(performers)
        else:
            table = _format_performers_table(performers, site_name)
            print_table(table)
            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {len(performers)} unmapped performer(s){filter_msg}{limit_msg}")

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            detail = e.response.json().get("detail", str(e))
            print_error(detail)
        else:
            print_error(f"API error: {e}")
        raise typer.Exit(code=1) from e
    except httpx.ConnectError as e:
        print_error("Could not connect to API. Is the server running?")
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch unmapped performers: {e}")
        raise typer.Exit(code=1) from e


@performers_app.command("link")
def link_performer(
    uuid: Annotated[str, typer.Argument(help="Performer UUID to link")],
    stashapp_id: Annotated[
        int | None,
        typer.Option("--stashapp-id", help="Stashapp performer ID"),
    ] = None,
    stashdb_id: Annotated[
        str | None,
        typer.Option("--stashdb-id", help="StashDB performer ID (UUID/GUID)"),
    ] = None,
) -> None:
    """Link a Culture Extractor performer to external systems.

    Sets external IDs for a performer, allowing you to associate them with
    Stashapp performers, StashDB entries, etc.

    Examples:
        ce performers link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345
        ce performers link 018f1477-f285-726b-9136-21956e3e8b92 --stashdb-id "a1b2c3d4-..."
        ce performers link 018f1477-f285-726b-9136-21956e3e8b92 --stashapp-id 12345 --stashdb-id "a1b2c3d4-..."
    """
    try:
        # Validate that at least one ID was provided
        if stashapp_id is None and stashdb_id is None:
            print_error("At least one external ID must be provided")
            print_info("Use --stashapp-id and/or --stashdb-id")
            raise typer.Exit(code=1)

        with CultureAPIClient() as client:
            links = []
            if stashapp_id is not None:
                client.link_performer(uuid, "stashapp", str(stashapp_id))
                links.append(f"Stashapp ID: {stashapp_id}")
            if stashdb_id is not None:
                client.link_performer(uuid, "stashdb", stashdb_id)
                links.append(f"StashDB ID: {stashdb_id}")

        print_success(f"Linked performer to {', '.join(links)}")

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            detail = e.response.json().get("detail", str(e))
            print_error(detail)
        else:
            print_error(f"API error: {e}")
        raise typer.Exit(code=1) from e
    except httpx.ConnectError as e:
        print_error("Could not connect to API. Is the server running?")
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to link performer: {e}")
        raise typer.Exit(code=1) from e


def _build_not_found_message(site: str, name: str | None) -> str:
    """Build a descriptive message when no performers are found."""
    msg = f"No performers found for site '{site}'"
    if name:
        msg += f" matching '{name}'"
    return msg


def _build_success_message(count: int, name: str | None, limit: int | None) -> str:
    """Build a success message with count and filter information."""
    filter_msg = f" matching '{name}'" if name else ""
    limit_msg = f" (showing first {limit})" if limit else ""
    return f"Found {count} performer(s){filter_msg}{limit_msg}"


def _format_performers_table(performers: list[dict], site_name: str | None) -> Table:
    """Format performers list as a Rich table."""
    title = f"Performers from {site_name}" if site_name else "Performers"
    table = Table(title=title)

    table.add_column("Name", style="cyan")
    table.add_column("Site", style="green")
    table.add_column("Short Name", style="yellow")
    table.add_column("Links", justify="center")
    table.add_column("UUID", style="dim")

    for p in performers:
        # Format link status
        has_sa = p.get("has_stashapp_link", False)
        has_db = p.get("has_stashdb_link", False)
        if has_sa and has_db:
            links = "SA+DB"
        elif has_sa:
            links = "SA"
        elif has_db:
            links = "DB"
        else:
            links = "-"

        name = p.get("ce_performers_name") or "-"
        site = p.get("ce_site_name") or p.get("ce_sites_name") or "-"
        short_name = p.get("ce_performers_short_name") or "None"
        uuid = p.get("ce_performers_uuid", "")

        table.add_row(name, site, short_name, links, uuid)

    return table


def _print_performer_detail(performer: dict) -> None:
    """Print a performer detail view as a Rich panel."""
    lines = [
        f"UUID: {performer.get('ce_performers_uuid', 'N/A')}",
        f"Name: {performer.get('ce_performers_name', 'N/A')}",
        f"Short Name: {performer.get('ce_performers_short_name') or 'N/A'}",
        f"URL: {performer.get('ce_performers_url') or 'N/A'}",
        "",
        "External IDs",
    ]

    external_ids = performer.get("external_ids", {})
    stashapp_id = external_ids.get("stashapp")
    stashdb_id = external_ids.get("stashdb")

    lines.append(f"Stashapp: {stashapp_id or 'Not linked'}")
    lines.append(f"Stashdb: {stashdb_id or 'Not linked'}")

    console.print(Panel("\n".join(lines), title="Performer Details"))


def _filter_by_link_status(
    performers: list[dict], only_linked: bool, only_unlinked: bool
) -> list[dict]:
    """Filter performers by link status."""
    if only_linked:
        return [
            p for p in performers if p.get("has_stashapp_link") or p.get("has_stashdb_link")
        ]
    if only_unlinked:
        return [
            p
            for p in performers
            if not p.get("has_stashapp_link") and not p.get("has_stashdb_link")
        ]
    return performers


def _build_filtered_not_found_message(
    site: str, name: str | None, only_linked: bool, only_unlinked: bool
) -> str:
    """Build a message for when no performers match filter criteria."""
    link_filter = "linked" if only_linked else "unlinked" if only_unlinked else ""
    msg = f"No {link_filter} performers found for site '{site}'"
    if name:
        msg += f" matching '{name}'"
    return msg


def _display_performers(
    performers: list[dict],
    site: str,
    name: str | None,
    limit: int | None,
    json_output: bool,
) -> None:
    """Display performers in the requested format."""
    site_name = performers[0].get("ce_site_name") if performers else site
    if json_output:
        print_json(performers)
    else:
        table = _format_performers_table(performers, site_name)
        print_table(table)
        print_success(_build_success_message(len(performers), name, limit))


def _handle_http_error(e: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors from the API."""
    if e.response.status_code == 404:
        detail = e.response.json().get("detail", str(e))
        print_error(detail)
    else:
        print_error(f"API error: {e}")
    raise typer.Exit(code=1) from e
