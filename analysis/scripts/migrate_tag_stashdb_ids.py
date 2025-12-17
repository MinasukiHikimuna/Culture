#!/usr/bin/env python3
"""
Migrate StashDB IDs from tag aliases to native stash_ids field.

Usage:
    uv run python analysis/scripts/migrate_tag_stashdb_ids.py --dry-run      # Preview all changes
    uv run python analysis/scripts/migrate_tag_stashdb_ids.py -n 10          # Migrate first 10 tags
    uv run python analysis/scripts/migrate_tag_stashdb_ids.py --dry-run -n 5 # Preview first 5 tags
"""

import argparse
import re

from libraries.client_stashapp import get_stashapp_client


# GraphQL fragment to fetch all needed tag data
TAG_FRAGMENT = """
    id
    name
    sort_name
    description
    aliases
    ignore_auto_tag
    stash_ids {
        endpoint
        stash_id
    }
    parents { id }
    children { id }
"""

# Regex to match StashDB ID aliases
STASHDB_ALIAS_PATTERN = re.compile(r"^StashDB ID: ([a-f0-9-]+)$")


def migrate_tag(tag: dict) -> dict | None:
    """
    Prepare migration for a single tag.
    Returns the update payload if migration needed, None otherwise.
    """
    stashdb_id = None
    new_aliases = []

    for alias in tag.get("aliases", []):
        match = STASHDB_ALIAS_PATTERN.match(alias)
        if match:
            stashdb_id = match.group(1)
        else:
            new_aliases.append(alias)

    if not stashdb_id:
        return None

    # Build new stash_ids (preserve existing + add extracted)
    existing_stash_ids = tag.get("stash_ids", [])
    new_stash_ids = [
        {"endpoint": x["endpoint"], "stash_id": x["stash_id"]}
        for x in existing_stash_ids
    ]

    # Only add if not already present
    if not any(x["endpoint"] == "https://stashdb.org/graphql" for x in new_stash_ids):
        new_stash_ids.append(
            {"endpoint": "https://stashdb.org/graphql", "stash_id": stashdb_id}
        )

    return {
        "id": tag["id"],
        "name": tag["name"],
        "sort_name": tag.get("sort_name", ""),
        "aliases": new_aliases,
        "description": tag.get("description", ""),
        "parent_ids": [p["id"] for p in tag.get("parents", [])],
        "child_ids": [c["id"] for c in tag.get("children", [])],
        "ignore_auto_tag": tag.get("ignore_auto_tag", False),
        "stash_ids": new_stash_ids,
    }


def execute_update(stash, payload: dict):
    """Execute the TagUpdate mutation."""
    mutation = """
    mutation TagUpdate($input: TagUpdateInput!) {
        tagUpdate(input: $input) {
            id
            name
            aliases
            stash_ids { endpoint stash_id }
        }
    }
    """
    return stash.call_GQL(mutation, {"input": payload})


def main():
    parser = argparse.ArgumentParser(
        description="Migrate StashDB IDs from tag aliases to native stash_ids"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making updates",
    )
    parser.add_argument(
        "-n",
        type=int,
        default=None,
        help="Limit number of tags to migrate (default: all)",
    )
    args = parser.parse_args()

    stash = get_stashapp_client()

    # Fetch all tags
    tags = stash.find_tags({}, fragment=TAG_FRAGMENT)

    # Process each tag
    migrated = 0
    for tag in tags:
        payload = migrate_tag(tag)
        if payload:
            print(f"Tag {tag['id']}: {tag['name']}")
            print(f"  StashDB ID: {payload['stash_ids'][-1]['stash_id']}")
            print(
                f"  Aliases before: {len(tag['aliases'])} -> after: {len(payload['aliases'])}"
            )

            if args.dry_run:
                print("  [DRY RUN - no changes made]")
            else:
                execute_update(stash, payload)
                print("  [UPDATED]")

            migrated += 1

            if args.n is not None and migrated >= args.n:
                print(f"\nReached limit of {args.n} tags")
                break

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Total tags migrated: {migrated}")


if __name__ == "__main__":
    main()
