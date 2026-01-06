#!/usr/bin/env python3
"""
Stashapp Tag Analyzer - Analyze and manage bracketed tags from scene titles/descriptions.

Extracts [bracketed] tags from Stashapp scenes, displays frequency counts,
and optionally creates/links tags to matching scenes.

Usage:
    uv run python stashapp_tag_analyzer.py                    # Analyze tags
    uv run python stashapp_tag_analyzer.py --min-count 5      # Filter by count
    uv run python stashapp_tag_analyzer.py --apply --tags "F4M,GFE"  # Create & link
    uv run python stashapp_tag_analyzer.py --apply --tags "F4M" --dry-run  # Preview
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).resolve().parent
load_dotenv(project_root / ".env")

# Stashapp Configuration
STASH_URL = os.getenv("STASHAPP_URL")
STASH_API_KEY = os.getenv("STASHAPP_API_KEY")

# Regex for bracketed tags (from stashapp_importer.py)
BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")


@dataclass
class TagOccurrence:
    """Represents a tag and its occurrences across scenes."""

    normalized_name: str  # lowercase for matching
    display_name: str  # Original case (first occurrence)
    count: int = 0
    scene_ids: list[str] = field(default_factory=list)
    exists_in_stash: bool = False
    stash_tag_id: str | None = None


class StashappTagAnalyzer:
    """Analyzer for extracting and managing bracketed tags from Stashapp scenes."""

    def __init__(self, url: str, api_key: str):
        self.url = url
        self.headers = {"ApiKey": api_key, "Content-Type": "application/json"}
        self._stash_tags: dict[str, dict] | None = None  # Cache for existing tags

    def query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query."""
        response = requests.post(
            self.url,
            json={"query": query, "variables": variables or {}},
            headers=self.headers,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")
        return result.get("data", {})

    def fetch_all_scenes(self, verbose: bool = False) -> list[dict]:
        """Fetch all scenes with id, title, details, and existing tags."""
        if verbose:
            print("Fetching all scenes from Stashapp...")

        query = """
            query FindAllScenes($filter: FindFilterType!) {
                findScenes(filter: $filter) {
                    count
                    scenes {
                        id
                        title
                        details
                        tags { id name }
                    }
                }
            }
        """
        result = self.query(query, {"filter": {"per_page": -1}})
        scenes = result.get("findScenes", {}).get("scenes", [])
        count = result.get("findScenes", {}).get("count", 0)

        if verbose:
            print(f"Fetched {len(scenes)} scenes (total: {count})")

        return scenes

    def fetch_all_tags(self, verbose: bool = False) -> dict[str, dict]:
        """Fetch all existing tags from Stashapp, keyed by lowercase name/alias."""
        if self._stash_tags is not None:
            return self._stash_tags

        if verbose:
            print("Fetching existing tags from Stashapp...")

        query = """
            query FindTags($filter: FindFilterType!) {
                findTags(filter: $filter) {
                    tags { id name aliases }
                }
            }
        """
        result = self.query(query, {"filter": {"per_page": -1}})
        tags = result.get("findTags", {}).get("tags", [])

        # Build lookup: lowercase name/alias -> tag info
        self._stash_tags = {}
        for tag in tags:
            tag_info = {"id": tag["id"], "name": tag["name"]}
            self._stash_tags[tag["name"].lower()] = tag_info
            for alias in tag.get("aliases") or []:
                self._stash_tags[alias.lower()] = tag_info

        if verbose:
            print(f"Found {len(tags)} existing tags")

        return self._stash_tags

    def extract_bracketed_tags(self, text: str) -> list[str]:
        """Extract bracketed tags from text."""
        if not text:
            return []
        return [match.strip() for match in BRACKET_PATTERN.findall(text)]

    def analyze_tags(
        self, scenes: list[dict], verbose: bool = False
    ) -> dict[str, TagOccurrence]:
        """Analyze all scenes and count tag occurrences."""
        stash_tags = self.fetch_all_tags(verbose)
        tag_data: dict[str, TagOccurrence] = {}

        for scene in scenes:
            scene_id = scene.get("id", "")
            title = scene.get("title") or ""
            details = scene.get("details") or ""

            # Extract tags from both title and details
            tags_from_title = self.extract_bracketed_tags(title)
            tags_from_details = self.extract_bracketed_tags(details)

            # Combine and deduplicate per-scene (case-insensitive)
            seen_in_scene: set[str] = set()
            all_tags = tags_from_title + tags_from_details

            for tag in all_tags:
                normalized = tag.lower()

                # Skip if already counted for this scene
                if normalized in seen_in_scene:
                    continue
                seen_in_scene.add(normalized)

                if normalized not in tag_data:
                    # Check if exists in Stashapp
                    stash_tag = stash_tags.get(normalized)
                    tag_data[normalized] = TagOccurrence(
                        normalized_name=normalized,
                        display_name=tag,
                        exists_in_stash=stash_tag is not None,
                        stash_tag_id=stash_tag["id"] if stash_tag else None,
                    )

                tag_data[normalized].count += 1
                tag_data[normalized].scene_ids.append(scene_id)

        return tag_data

    def create_tag(self, name: str, dry_run: bool = False) -> str | None:
        """Create a new tag in Stashapp. Returns tag ID."""
        if dry_run:
            print(f"  Would create tag: {name}")
            return None

        mutation = """
            mutation TagCreate($input: TagCreateInput!) {
                tagCreate(input: $input) { id name }
            }
        """
        result = self.query(mutation, {"input": {"name": name}})
        tag = result.get("tagCreate", {})
        tag_id = tag.get("id")
        print(f"  Created tag: {name} (id: {tag_id})")
        return tag_id

    def link_tag_to_scene(
        self,
        scene_id: str,
        tag_id: str,
        existing_tag_ids: list[str],
        dry_run: bool = False,
    ) -> bool:
        """Add a tag to a scene, preserving existing tags."""
        if tag_id in existing_tag_ids:
            return False  # Already has this tag

        new_tag_ids = existing_tag_ids + [tag_id]

        if dry_run:
            return True

        mutation = """
            mutation SceneUpdate($input: SceneUpdateInput!) {
                sceneUpdate(input: $input) { id }
            }
        """
        self.query(mutation, {"input": {"id": scene_id, "tag_ids": new_tag_ids}})
        return True

    def apply_tags(
        self,
        tag_names: list[str],
        scenes: list[dict],
        tag_analysis: dict[str, TagOccurrence],
        dry_run: bool = False,
        verbose: bool = False,
    ):
        """Create tags and link them to matching scenes."""
        stash_tags = self.fetch_all_tags(verbose)

        # Build scene lookup for existing tags
        scene_existing_tags: dict[str, list[str]] = {}
        for scene in scenes:
            scene_id = scene.get("id", "")
            existing = [t["id"] for t in scene.get("tags") or []]
            scene_existing_tags[scene_id] = existing

        for tag_name in tag_names:
            normalized = tag_name.lower().strip()
            print(f"\nProcessing: {tag_name}")

            # Check if tag exists or needs creation
            if normalized in stash_tags:
                tag_id = stash_tags[normalized]["id"]
                print(f"  Tag exists (id: {tag_id})")
            else:
                tag_id = self.create_tag(tag_name, dry_run)
                if tag_id:
                    # Update cache
                    stash_tags[normalized] = {"id": tag_id, "name": tag_name}

            # Find scenes with this bracketed tag
            tag_occurrence = tag_analysis.get(normalized)
            if not tag_occurrence:
                print(f"  No scenes found with [{tag_name}] in title/details")
                continue

            # Link to scenes
            linked_count = 0
            skipped_count = 0

            for scene_id in tag_occurrence.scene_ids:
                existing_tags = scene_existing_tags.get(scene_id, [])

                if dry_run:
                    if tag_id and tag_id not in existing_tags:
                        linked_count += 1
                    elif not tag_id:
                        # Dry run - assume we'd link
                        linked_count += 1
                    else:
                        skipped_count += 1
                else:
                    if tag_id:
                        if self.link_tag_to_scene(
                            scene_id, tag_id, existing_tags, dry_run
                        ):
                            linked_count += 1
                            # Update cache
                            scene_existing_tags[scene_id] = existing_tags + [tag_id]
                        else:
                            skipped_count += 1

            action = "Would link" if dry_run else "Linked"
            print(f"  {action} to {linked_count} scenes")
            if skipped_count > 0:
                print(f"  Skipped {skipped_count} scenes (already tagged)")


def print_analysis(
    tag_data: dict[str, TagOccurrence],
    total_scenes: int,
    limit: int | None = None,
    min_count: int = 1,
):
    """Print formatted terminal summary."""
    # Filter and sort
    filtered = [t for t in tag_data.values() if t.count >= min_count]
    sorted_tags = sorted(filtered, key=lambda t: (-t.count, t.normalized_name))

    print("\nStashapp Bracketed Tag Analysis")
    print("=" * 70)
    print(f"Total scenes analyzed: {total_scenes:,}")
    print(f"Unique tags found: {len(tag_data):,}")
    if min_count > 1:
        print(f"Tags with {min_count}+ occurrences: {len(filtered):,}")
    print()
    print("Top Tags by Frequency:")
    print("-" * 70)
    print(f"{'#':>4}  | {'Count':>5} | {'Tag':<32} | In Stash?")
    print("-" * 70)

    display_tags = sorted_tags[:limit] if limit and limit > 0 else sorted_tags

    for i, tag in enumerate(display_tags, 1):
        in_stash = "Yes" if tag.exists_in_stash else "No"
        # Truncate long tags
        display_name = (
            tag.display_name[:30] + ".."
            if len(tag.display_name) > 32
            else tag.display_name
        )
        print(f"{i:>4}  | {tag.count:>5} | {display_name:<32} | {in_stash}")

    print("-" * 70)
    if limit and limit > 0 and len(sorted_tags) > limit:
        print(f"Showing {limit} of {len(sorted_tags)} tags (use --limit 0 for all)")


def print_json(
    tag_data: dict[str, TagOccurrence],
    total_scenes: int,
    limit: int | None = None,
    min_count: int = 1,
):
    """Print JSON output."""
    filtered = [t for t in tag_data.values() if t.count >= min_count]
    sorted_tags = sorted(filtered, key=lambda t: (-t.count, t.normalized_name))
    display_tags = sorted_tags[:limit] if limit and limit > 0 else sorted_tags

    output = {
        "total_scenes": total_scenes,
        "total_unique_tags": len(tag_data),
        "tags": [
            {
                "tag": t.display_name,
                "normalized": t.normalized_name,
                "count": t.count,
                "exists_in_stash": t.exists_in_stash,
                "stash_tag_id": t.stash_tag_id,
                "scene_ids": t.scene_ids[:5],  # Limit for readability
            }
            for t in display_tags
        ],
    }
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and manage bracketed tags from Stashapp scenes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Analysis options
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=50,
        help="Number of top tags to display (default: 50, use 0 for all)",
    )
    parser.add_argument(
        "--min-count",
        "-m",
        type=int,
        default=1,
        help="Minimum occurrence count to include (default: 1)",
    )

    # Apply mode options
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Enable tag creation/linking mode",
    )
    parser.add_argument(
        "--tags",
        type=str,
        help="Comma-separated list of tags to create/link",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying",
    )

    # Output options
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show verbose output"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.apply and not args.tags:
        print("Error: --apply requires --tags")
        sys.exit(1)

    # Validate environment
    if not STASH_URL or not STASH_API_KEY:
        print("Error: Missing required Stashapp environment variables.")
        print("Please set STASHAPP_URL and STASHAPP_API_KEY in your .env file.")
        sys.exit(1)

    try:
        # Initialize analyzer
        analyzer = StashappTagAnalyzer(STASH_URL, STASH_API_KEY)

        # Fetch and analyze
        scenes = analyzer.fetch_all_scenes(verbose=args.verbose)
        tag_analysis = analyzer.analyze_tags(scenes, verbose=args.verbose)

        if args.apply:
            # Apply mode: create and link tags
            tag_names = [t.strip() for t in args.tags.split(",") if t.strip()]
            if args.dry_run:
                print("\n=== DRY RUN - No changes will be made ===")
            analyzer.apply_tags(
                tag_names, scenes, tag_analysis, dry_run=args.dry_run, verbose=args.verbose
            )
        else:
            # Analysis mode: display results
            if args.json:
                print_json(tag_analysis, len(scenes), args.limit, args.min_count)
            else:
                print_analysis(tag_analysis, len(scenes), args.limit, args.min_count)

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Stashapp: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
