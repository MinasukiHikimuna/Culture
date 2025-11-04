"""Tags-related commands for the CLI."""

import json
from typing import Annotated

import typer
from rich.table import Table

from culture_cli.modules.ce.utils.config import config
from culture_cli.modules.ce.utils.formatters import (
    format_tags_table,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)
from culture_cli.modules.ce.utils.tag_matcher import find_tag_matches
from libraries.client_stashapp import StashAppClient


# Create tags command group
tags_app = typer.Typer(help="Manage Culture Extractor tags")


@tags_app.command("list")
def list_tags(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="Filter by site (short name or UUID)"),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by tag name (case-insensitive)"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results"),
    ] = None,
    unlinked_only: Annotated[
        bool,
        typer.Option("--unlinked-only", "-u", help="Show only tags without Stashapp links"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List tags from a specific site in the Culture Extractor database.

    Use --name to filter by tag name. Tags are retrieved from releases in the site.
    Use --unlinked-only to show only tags that don't have Stashapp links.

    Examples:
        ce tags list --site meanawolf                    # List all tags from Meana Wolf
        ce tags list -s meanawolf -n "pov"               # Filter by name
        ce tags list -s meanawolf --limit 20             # Limit results to 20
        ce tags list -s meanawolf --unlinked-only        # Show only unlinked tags
        ce tags list --site meanawolf --json             # JSON output
    """
    try:
        client = config.get_client()

        # Resolve site UUID
        sites_df = client.get_sites()
        site_match = sites_df.filter(
            (sites_df["ce_sites_short_name"] == site)
            | (sites_df["ce_sites_uuid"] == site)
            | (sites_df["ce_sites_name"] == site)
        )

        if site_match.shape[0] == 0:
            print_error(f"Site '{site}' not found")
            print_info("To see available sites, run: ce sites list")
            raise typer.Exit(code=1)

        site_uuid = site_match["ce_sites_uuid"][0]
        site_name = site_match["ce_sites_name"][0]

        filter_msg = f" matching '{name}'" if name else ""
        print_info(f"Fetching tags from '{site_name}'{filter_msg}...")

        # Fetch tags for the site
        tags_df = client.get_tags(site_uuid, name_filter=name)

        if tags_df.shape[0] == 0:
            msg = f"No tags found for site '{site_name}'"
            if name:
                msg += f" matching '{name}'"
            print_info(msg)
            raise typer.Exit(code=0)

        # Filter for unlinked tags if requested
        if unlinked_only:
            tags_df = tags_df.filter(tags_df["ce_tags_stashapp_id"].is_null())
            if tags_df.shape[0] == 0:
                print_info(f"All tags from '{site_name}' are linked to Stashapp")
                raise typer.Exit(code=0)

        # Apply limit if specified
        if limit and limit > 0:
            tags_df = tags_df.head(limit)

        # Display results
        count = tags_df.shape[0]
        if json_output:
            print_json(tags_df)
        else:
            table = format_tags_table(tags_df, site_name)
            print_table(table)
            limit_msg = f" (showing first {limit})" if limit else ""
            print_success(f"Found {count} tag(s){filter_msg}{limit_msg}")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to fetch tags: {e}")
        raise typer.Exit(code=1) from e


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


@tags_app.command("unlinked")
def list_unlinked_tags(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="CE site to check (short name or UUID)"),
    ],
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """List CE tags that are not linked to Stashapp.

    This command shows which tags from a site don't have Stashapp links,
    helping you identify tags that need manual linking or lower thresholds.

    Examples:
        ce tags unlinked --site ellieidol                    # List all unlinked tags
        ce tags unlinked -s ellieidol --limit 50             # Limit results
        ce tags unlinked --site ellieidol --json             # Output as JSON
    """
    try:
        ce_client = config.get_client()
        site_uuid, site_name = _resolve_site(ce_client, site)
        ce_tags = _fetch_ce_tags(ce_client, site_uuid, site_name)

        print_info("Checking for unlinked tags...")
        unlinked_tags = []

        for row in ce_tags.iter_rows(named=True):
            ce_uuid = row["ce_tags_uuid"]
            ce_name = row["ce_tags_name"]
            external_ids = ce_client.get_tag_external_ids(ce_uuid)

            if "stashapp" not in external_ids:
                unlinked_tags.append({"uuid": ce_uuid, "name": ce_name})

        if not unlinked_tags:
            print_success(f"All tags from '{site_name}' are linked to Stashapp!")
            raise typer.Exit(code=0)

        # Apply limit if specified
        if limit and limit > 0:
            unlinked_tags = unlinked_tags[:limit]

        # Display results
        if json_output:
            print(json.dumps(unlinked_tags, indent=2))
        else:
            table = Table(title=f"Unlinked Tags from {site_name}")
            table.add_column("Tag Name", style="cyan")
            table.add_column("UUID", style="dim")

            for tag in unlinked_tags:
                table.add_row(tag["name"], tag["uuid"])

            print_table(table)
            limit_msg = f" (showing first {limit})" if limit else ""
            total_tags = ce_tags.shape[0]
            unlinked_count = len(unlinked_tags) if not limit else sum(
                1
                for row in ce_tags.iter_rows(named=True)
                if "stashapp" not in ce_client.get_tag_external_ids(row["ce_tags_uuid"])
            )
            linked_count = total_tags - unlinked_count
            print_info(
                f"Found {unlinked_count} unlinked tag(s) out of {total_tags} total "
                f"({linked_count} linked, {(linked_count/total_tags)*100:.1f}% coverage){limit_msg}"
            )
            print_info("To find potential matches, run: ce tags match --site <site> -t <threshold>")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to list unlinked tags: {e}")
        raise typer.Exit(code=1) from e


@tags_app.command("match")
def match_tags(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="CE site to match tags from (short name or UUID)"),
    ],
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Minimum similarity ratio (0.0-1.0)"),
    ] = 0.85,
    max_distance: Annotated[
        int | None,
        typer.Option("--max-distance", "-d", help="Maximum Levenshtein distance"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of results"),
    ] = None,
    include_linked: Annotated[
        bool,
        typer.Option("--include-linked", help="Include tags that already have Stashapp links"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON instead of table"),
    ] = False,
) -> None:
    """Find potential tag matches between CE and Stashapp using Levenshtein distance.

    This command compares tag names between Culture Extractor and Stashapp
    using string similarity algorithms to find potential matches. By default,
    only shows matches for unlinked tags.

    Examples:
        ce tags match --site ellieidol                           # Find matches for unlinked tags (default)
        ce tags match -s ellieidol -t 0.9                       # Higher threshold for more exact matches
        ce tags match -s ellieidol --include-linked             # Include already linked tags
        ce tags match -s ellieidol --limit 50 --json            # Limit results, output as JSON
    """
    try:
        ce_client = config.get_client()
        site_uuid, site_name = _resolve_site(ce_client, site)
        ce_tags = _fetch_ce_tags(ce_client, site_uuid, site_name)

        # Filter to unlinked tags by default
        if not include_linked:
            ce_tags = _filter_unlinked_tags(ce_client, ce_tags)
            if ce_tags.shape[0] == 0:
                print_success(f"All tags from '{site_name}' are already linked to Stashapp!")
                raise typer.Exit(code=0)

        stashapp_tags = _fetch_stashapp_tags()
        matches = _find_and_limit_matches(ce_tags, stashapp_tags, threshold, max_distance, limit)
        _display_match_results(matches, site_name, limit, json_output)

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to match tags: {e}")
        raise typer.Exit(code=1) from e


def _resolve_site(ce_client, site: str) -> tuple[str, str]:
    """Resolve site identifier to UUID and name."""
    sites_df = ce_client.get_sites()
    site_match = sites_df.filter(
        (sites_df["ce_sites_short_name"] == site)
        | (sites_df["ce_sites_uuid"] == site)
        | (sites_df["ce_sites_name"] == site)
    )

    if site_match.shape[0] == 0:
        print_error(f"Site '{site}' not found")
        print_info("To see available sites, run: ce sites list")
        raise typer.Exit(code=1)

    return site_match["ce_sites_uuid"][0], site_match["ce_sites_name"][0]


def _fetch_ce_tags(ce_client, site_uuid: str, site_name: str):
    """Fetch CE tags for a site."""
    print_info(f"Fetching tags from CE site '{site_name}'...")
    ce_tags = ce_client.get_tags(site_uuid)

    if ce_tags.shape[0] == 0:
        print_info(f"No tags found for site '{site_name}'")
        raise typer.Exit(code=0)

    return ce_tags


def _fetch_stashapp_tags():
    """Fetch tags from Stashapp."""
    print_info("Fetching tags from Stashapp...")
    stashapp_client = StashAppClient()
    stashapp_tags = stashapp_client.get_tags()

    if stashapp_tags.shape[0] == 0:
        print_info("No tags found in Stashapp")
        raise typer.Exit(code=0)

    return stashapp_tags


def _filter_unlinked_tags(ce_client, ce_tags):
    """Filter CE tags to only include those without Stashapp links."""
    print_info("Filtering to unlinked tags...")
    unlinked_uuids = []

    for row in ce_tags.iter_rows(named=True):
        ce_uuid = row["ce_tags_uuid"]
        external_ids = ce_client.get_tag_external_ids(ce_uuid)
        if "stashapp" not in external_ids:
            unlinked_uuids.append(ce_uuid)

    # Filter the dataframe to only include unlinked tags
    return ce_tags.filter(ce_tags["ce_tags_uuid"].is_in(unlinked_uuids))


def _find_and_limit_matches(ce_tags, stashapp_tags, threshold: float, max_distance: int | None, limit: int | None):
    """Find tag matches and apply limit."""
    print_info(f"Finding matches (threshold: {threshold})...")
    matches = find_tag_matches(ce_tags, stashapp_tags, threshold=threshold, max_distance=max_distance)

    if not matches:
        print_info(f"No matches found with threshold {threshold}")
        print_info("Try lowering the threshold with --threshold option")
        raise typer.Exit(code=0)

    if limit and limit > 0:
        matches = matches[:limit]

    return matches


def _display_match_results(matches, site_name: str, limit: int | None, json_output: bool) -> None:
    """Display match results as JSON or table."""
    if json_output:
        matches_dict = [
            {
                "ce_uuid": m.ce_uuid,
                "ce_name": m.ce_name,
                "stashapp_id": m.stashapp_id,
                "stashapp_name": m.stashapp_name,
                "stashdb_id": m.stashdb_id,
                "distance": m.distance,
                "similarity": round(m.similarity, 4),
            }
            for m in matches
        ]
        print(json.dumps(matches_dict, indent=2))
    else:
        table = Table(title=f"Tag Matches for {site_name}")
        table.add_column("CE Tag", style="cyan")
        table.add_column("Stashapp Tag", style="green")
        table.add_column("Similarity", justify="right", style="yellow")
        table.add_column("Distance", justify="right", style="magenta")
        table.add_column("CE UUID", style="dim")
        table.add_column("Stashapp ID", justify="right", style="dim")

        for match in matches:
            table.add_row(
                match.ce_name,
                match.stashapp_name,
                f"{match.similarity:.2%}",
                str(match.distance),
                match.ce_uuid,
                str(match.stashapp_id),
            )

        print_table(table)
        limit_msg = f" (showing first {limit})" if limit else ""
        print_success(f"Found {len(matches)} potential match(es){limit_msg}")
        print_info("\nLink commands (copy and paste the ones you want):")
        for match in matches:
            print(f"uv run culture ce tags link {match.ce_uuid} --stashapp-id {match.stashapp_id}")
        print()


@tags_app.command("auto-link")
def auto_link_tags(
    site: Annotated[
        str,
        typer.Option("--site", "-s", help="CE site to auto-link tags from (short name or UUID)"),
    ],
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Minimum similarity ratio (0.0-1.0)"),
    ] = 0.95,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be linked without actually linking"),
    ] = False,
    include_linked: Annotated[
        bool,
        typer.Option("--include-linked", help="Include tags that already have Stashapp links"),
    ] = False,
) -> None:
    """Automatically link CE tags to Stashapp based on similarity matching.

    This command will automatically create links between CE and Stashapp tags
    when they have high similarity scores. By default, only processes unlinked
    tags. Use a high threshold (0.95+) to ensure accurate matches.

    Examples:
        ce tags auto-link --site ellieidol --dry-run              # Preview matches without linking
        ce tags auto-link -s ellieidol -t 0.95                   # Link unlinked tags with 95% threshold
        ce tags auto-link -s ellieidol --include-linked          # Include already linked tags
    """
    try:
        ce_client = config.get_client()
        site_uuid, site_name = _resolve_site(ce_client, site)
        ce_tags = _fetch_ce_tags(ce_client, site_uuid, site_name)
        stashapp_tags = _fetch_stashapp_tags()
        skip_linked = not include_linked
        existing_links = _get_existing_links(ce_client, ce_tags, skip_linked)
        matches_to_link = _find_best_matches(ce_tags, stashapp_tags, threshold, existing_links, skip_linked)
        _display_auto_link_preview(matches_to_link, site_name, dry_run)
        _perform_auto_link(ce_client, matches_to_link, existing_links, dry_run, skip_linked)

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        print_error(f"Failed to auto-link tags: {e}")
        raise typer.Exit(code=1) from e


def _get_existing_links(ce_client, ce_tags, skip_linked: bool) -> dict[str, str]:
    """Get existing Stashapp links for CE tags."""
    existing_links = {}
    if skip_linked:
        print_info("Checking for existing links...")
        for row in ce_tags.iter_rows(named=True):
            ce_uuid = row["ce_tags_uuid"]
            external_ids = ce_client.get_tag_external_ids(ce_uuid)
            if "stashapp" in external_ids:
                existing_links[ce_uuid] = external_ids["stashapp"]
    return existing_links


def _find_best_matches(ce_tags, stashapp_tags, threshold: float, existing_links: dict, skip_linked: bool):
    """Find and filter best matches for auto-linking."""
    print_info(f"Finding matches (threshold: {threshold})...")
    all_matches = find_tag_matches(ce_tags, stashapp_tags, threshold=threshold)

    # Filter to best match per CE tag and skip existing links
    best_matches = {}
    for match in all_matches:
        if skip_linked and match.ce_uuid in existing_links:
            continue

        if match.ce_uuid not in best_matches or match.similarity > best_matches[match.ce_uuid].similarity:
            best_matches[match.ce_uuid] = match

    matches_to_link = list(best_matches.values())

    if not matches_to_link:
        if skip_linked and existing_links:
            print_info(
                f"No new matches found. {len(existing_links)} tags already linked "
                "(use --no-skip-linked to re-process)"
            )
        else:
            print_info(f"No matches found with threshold {threshold}")
            print_info("Try lowering the threshold with --threshold option")
        raise typer.Exit(code=0)

    return matches_to_link


def _display_auto_link_preview(matches_to_link, site_name: str, dry_run: bool) -> None:
    """Display preview table of tags to be linked."""
    table = Table(title=f"Auto-Link Preview for {site_name}" + (" [DRY RUN]" if dry_run else ""))
    table.add_column("CE Tag", style="cyan")
    table.add_column("→", style="white")
    table.add_column("Stashapp Tag", style="green")
    table.add_column("Similarity", justify="right", style="yellow")

    for match in matches_to_link:
        table.add_row(
            match.ce_name,
            "→",
            match.stashapp_name,
            f"{match.similarity:.2%}",
        )

    print_table(table)


def _perform_auto_link(ce_client, matches_to_link, existing_links: dict, dry_run: bool, skip_existing: bool) -> None:
    """Perform the actual linking or show dry-run message."""
    if dry_run:
        print_info(f"[DRY RUN] Would link {len(matches_to_link)} tag(s)")
        print_info("Remove --dry-run to perform actual linking")
    else:
        print_info(f"Linking {len(matches_to_link)} tag(s)...")
        linked_count = 0
        for match in matches_to_link:
            try:
                ce_client.set_tag_external_id(match.ce_uuid, "stashapp", str(match.stashapp_id))
                if match.stashdb_id:
                    ce_client.set_tag_external_id(match.ce_uuid, "stashdb", match.stashdb_id)
                linked_count += 1
            except Exception as e:
                print_error(f"Failed to link '{match.ce_name}': {e}")

        print_success(f"Successfully linked {linked_count} tag(s)")
        if skip_existing and existing_links:
            print_info(f"Skipped {len(existing_links)} already linked tag(s)")
