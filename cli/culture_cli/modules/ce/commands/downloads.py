"""Downloads commands for the Culture CLI."""

from typing import Annotated

import httpx
import typer

from culture_cli.api_client import CultureAPIClient
from culture_cli.modules.ce.utils.formatters import (
    format_download_summary_table,
    format_download_type_summary,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)


downloads_app = typer.Typer(help="View and manage download status")


def _get_api_client() -> CultureAPIClient:
    return CultureAPIClient()


@downloads_app.command("list")
def list_downloads(
    site: Annotated[
        str | None,
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
    ] = None,
    downloads: Annotated[
        str,
        typer.Option("--downloads", help="Filter: 'all' (default) or 'none' (no downloads)"),
    ] = "all",
    has_file: Annotated[
        str | None,
        typer.Option("--has-file", help="Show releases with this file_type downloaded (e.g. 'video')"),
    ] = None,
    missing_file: Annotated[
        str | None,
        typer.Option("--missing-file", help="Show releases missing this file_type (e.g. 'video')"),
    ] = None,
    has_content: Annotated[
        str | None,
        typer.Option("--has-content", help="Show releases with this content_type downloaded (e.g. 'scene')"),
    ] = None,
    missing_content: Annotated[
        str | None,
        typer.Option(
            "--missing-content", help="Show releases missing this content_type (e.g. 'scene')"
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results (default: all)"),
    ] = None,
    desc: Annotated[
        bool,
        typer.Option("--desc", "-d", help="Sort by release date descending (newest first)"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List per-release download status for a site.

    Shows each release with a summary of what has been downloaded (file types and
    content types). Use filters to find releases missing specific download types.

    Examples:
        ce downloads list --site xart                         # All releases with download status
        ce downloads list --site xart --desc                  # Newest first
        ce downloads list --site xart --downloads none        # Releases with no downloads
        ce downloads list --site xart --missing-file video    # Missing video downloads
        ce downloads list --site xart --has-content scene     # Has scene content downloaded
    """
    if not site:
        print_error("Site filter is required. Use --site <site_name> or --site <uuid>")
        print_info("To see available sites, run: ce sites list")
        raise typer.Exit(code=1)

    filter_msg = _build_filter_message(downloads, has_file, missing_file, has_content, missing_content)
    print_info(f"Fetching download status for '{site}'{filter_msg}...")

    try:
        summaries = _fetch_summaries(
            site, downloads, has_file, missing_file, has_content, missing_content, limit, desc
        )
    except httpx.ConnectError:
        print_error("Cannot connect to Culture API. Is the API server running?")
        print_info("Start the API with: cd api && uv run uvicorn api.main:app --port 8000")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)

    if not summaries:
        print_info(f"No releases found for site '{site}'{filter_msg}")
        raise typer.Exit(code=0)

    _display_results(summaries, site, filter_msg, limit, json_output)


def _build_filter_message(
    downloads: str,
    has_file: str | None,
    missing_file: str | None,
    has_content: str | None,
    missing_content: str | None,
) -> str:
    """Build a human-readable description of active filters."""
    filter_parts = []
    if downloads == "none":
        filter_parts.append("no downloads")
    if has_file:
        filter_parts.append(f"has file_type '{has_file}'")
    if missing_file:
        filter_parts.append(f"missing file_type '{missing_file}'")
    if has_content:
        filter_parts.append(f"has content_type '{has_content}'")
    if missing_content:
        filter_parts.append(f"missing content_type '{missing_content}'")
    return f" with {' and '.join(filter_parts)}" if filter_parts else ""


def _fetch_summaries(
    site: str,
    downloads: str,
    has_file: str | None,
    missing_file: str | None,
    has_content: str | None,
    missing_content: str | None,
    limit: int | None,
    desc: bool,
) -> list[dict]:
    """Fetch download summaries from the API."""
    with _get_api_client() as api:
        return api.get_download_summary(
            site,
            downloads=downloads,
            has_file=has_file,
            missing_file=missing_file,
            has_content=has_content,
            missing_content=missing_content,
            limit=limit,
            desc=desc,
        )


def _handle_http_error(e: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors from the API."""
    detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
    if e.response.status_code == 404:
        print_error(detail)
    else:
        print_error(f"API error: {detail}")
    raise typer.Exit(code=1) from e


def _display_results(
    summaries: list[dict],
    site: str,
    filter_msg: str,
    limit: int | None,
    json_output: bool,
) -> None:
    """Display download summary results as table or JSON."""
    count = len(summaries)
    if json_output:
        print_json(summaries)
        return

    site_name = summaries[0]["ce_site_name"] if summaries else site
    table = format_download_summary_table(summaries, site_name)
    print_table(table)
    limit_msg = f" (showing first {limit})" if limit else ""
    print_success(f"Found {count} release(s){filter_msg}{limit_msg}")

    type_summary = format_download_type_summary(summaries)
    if type_summary:
        print_info(type_summary)
