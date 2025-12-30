#!/usr/bin/env python3
"""
Stashapp Release Checker - Query Stashapp GraphQL API for release information.

Usage:
    python scripts/stash_check.py <query>           # Search scenes by title
    python scripts/stash_check.py --id <scene_id>  # Get scene by ID
    python scripts/stash_check.py --performer <name>  # Find scenes by performer

Examples:
    python scripts/stash_check.py "shy ghost girl"
    python scripts/stash_check.py --id 123
    python scripts/stash_check.py --performer "SnakeySmut"
"""

import argparse
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).resolve().parents[4]
load_dotenv(project_root / ".env")

# Stashapp Configuration
STASH_URL = os.getenv("STASHAPP_URL")
STASH_API_KEY = os.getenv("STASHAPP_API_KEY")


class StashappChecker:
    """Stashapp GraphQL client for checking releases."""

    def __init__(self, url: str, api_key: str):
        self.url = url
        self.headers = {"ApiKey": api_key, "Content-Type": "application/json"}

    def query(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query."""
        response = requests.post(
            self.url,
            json={"query": query, "variables": variables or {}},
            headers=self.headers,
        )
        response.raise_for_status()
        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")
        return result.get("data", {})

    def find_scene_by_id(self, scene_id: int) -> dict | None:
        """Get a specific scene by ID."""
        query = """
        query FindScene($id: ID!) {
            findScene(id: $id) {
                id
                title
                date
                details
                urls
                organized
                play_count
                o_counter
                performers { id name disambiguation }
                studio { id name }
                tags { id name }
                files { path basename duration size }
            }
        }
        """
        result = self.query(query, {"id": str(scene_id)})
        return result.get("findScene")

    def search_scenes(self, search_query: str, limit: int = 10) -> list[dict]:
        """Search scenes by title/text."""
        query = """
        query FindScenes($filter: FindFilterType!) {
            findScenes(filter: $filter) {
                scenes {
                    id
                    title
                    date
                    urls
                    organized
                    performers { id name }
                    studio { id name }
                    tags { id name }
                    files { path basename duration }
                }
            }
        }
        """
        result = self.query(query, {"filter": {"q": search_query, "per_page": limit}})
        return result.get("findScenes", {}).get("scenes", [])

    def find_performer(self, name: str) -> dict | None:
        """Find a performer by name."""
        query = """
        query FindPerformers($filter: FindFilterType!) {
            findPerformers(filter: $filter) {
                performers { id name disambiguation scene_count }
            }
        }
        """
        result = self.query(query, {"filter": {"q": name, "per_page": 10}})
        performers = result.get("findPerformers", {}).get("performers", [])
        # Exact match first
        for p in performers:
            if p["name"].lower() == name.lower():
                return p
        # Return first result if no exact match
        return performers[0] if performers else None

    def find_scenes_by_performer(self, performer_id: int, limit: int = 20) -> list[dict]:
        """Find scenes featuring a specific performer."""
        query = """
        query FindScenes($filter: SceneFilterType!, $find_filter: FindFilterType!) {
            findScenes(scene_filter: $filter, filter: $find_filter) {
                scenes {
                    id
                    title
                    date
                    organized
                    performers { id name }
                    studio { id name }
                    tags { id name }
                }
            }
        }
        """
        result = self.query(
            query,
            {
                "filter": {
                    "performers": {
                        "value": [str(performer_id)],
                        "modifier": "INCLUDES",
                    }
                },
                "find_filter": {"per_page": limit, "sort": "date", "direction": "DESC"},
            },
        )
        return result.get("findScenes", {}).get("scenes", [])

    def get_stats(self) -> dict:
        """Get Stashapp statistics."""
        query = """
        query Stats {
            stats {
                scene_count
                performer_count
                studio_count
                tag_count
                scenes_size
                total_play_duration
            }
        }
        """
        result = self.query(query)
        return result.get("stats", {})


def format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "N/A"
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_size(size_bytes: int) -> str:
    """Format file size in bytes to human readable."""
    if not size_bytes:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def print_scene(scene: dict, verbose: bool = False):
    """Print scene information."""
    print(f"\nScene: {scene.get('title', 'Untitled')}")
    print(f"ID: {scene.get('id')}")
    print(f"Date: {scene.get('date', 'N/A')}")
    print(f"Organized: {'Yes' if scene.get('organized') else 'No'}")

    if scene.get("play_count") is not None:
        print(f"Play Count: {scene.get('play_count', 0)}")

    performers = scene.get("performers", [])
    if performers:
        print("\nPerformers:")
        for p in performers:
            disambiguation = f" ({p['disambiguation']})" if p.get("disambiguation") else ""
            print(f"  - {p['name']}{disambiguation} (ID: {p['id']})")

    studio = scene.get("studio")
    if studio:
        print(f"\nStudio: {studio['name']} (ID: {studio['id']})")

    tags = scene.get("tags", [])
    if tags:
        tag_names = [t["name"] for t in tags]
        print(f"\nTags: {', '.join(tag_names)}")

    files = scene.get("files", [])
    if files:
        print("\nFiles:")
        for f in files:
            duration = format_duration(f.get("duration"))
            size = format_size(f.get("size")) if f.get("size") else ""
            size_str = f", size: {size}" if size else ""
            print(f"  - {f.get('basename', 'unknown')} (duration: {duration}{size_str})")
            if verbose and f.get("path"):
                print(f"    Path: {f['path']}")

    urls = scene.get("urls", [])
    if urls:
        print("\nURLs:")
        for url in urls:
            print(f"  - {url}")

    if verbose and scene.get("details"):
        print(f"\nDetails:\n{scene['details'][:500]}...")


def print_scene_summary(scene: dict):
    """Print a brief scene summary for lists."""
    title = scene.get("title", "Untitled")[:60]
    date = scene.get("date", "N/A")
    organized = "✓" if scene.get("organized") else "✗"
    performers = ", ".join(p["name"] for p in scene.get("performers", []))[:30]
    print(f"  [{scene['id']:>4}] {organized} {date} | {title}")
    if performers:
        print(f"         Performers: {performers}")


def main():
    parser = argparse.ArgumentParser(
        description="Check Stashapp releases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", nargs="?", help="Search query for scene title")
    parser.add_argument("--id", type=int, help="Get scene by ID")
    parser.add_argument("--performer", "-p", help="Find scenes by performer name")
    parser.add_argument("--stats", action="store_true", help="Show Stashapp statistics")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Limit results (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Check that at least one action is specified
    if not any([args.query, args.id, args.performer, args.stats]):
        parser.print_help()
        sys.exit(1)

    # Validate required environment variables
    if not STASH_URL or not STASH_API_KEY:
        print("Error: Missing required Stashapp environment variables.")
        print("Please set STASHAPP_URL and STASHAPP_API_KEY in your .env file.")
        sys.exit(1)

    # Initialize client
    client = StashappChecker(STASH_URL, STASH_API_KEY)

    try:
        if args.stats:
            stats = client.get_stats()
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("\nStashapp Statistics:")
                print(f"  Scenes: {stats.get('scene_count', 0)}")
                print(f"  Performers: {stats.get('performer_count', 0)}")
                print(f"  Studios: {stats.get('studio_count', 0)}")
                print(f"  Tags: {stats.get('tag_count', 0)}")
                print(f"  Total Size: {format_size(stats.get('scenes_size', 0))}")
                total_duration = stats.get("total_play_duration", 0)
                print(f"  Total Play Duration: {format_duration(total_duration)}")

        elif args.id:
            scene = client.find_scene_by_id(args.id)
            if scene:
                if args.json:
                    print(json.dumps(scene, indent=2))
                else:
                    print_scene(scene, verbose=args.verbose)
            else:
                print(f"Scene with ID {args.id} not found.")
                sys.exit(1)

        elif args.performer:
            performer = client.find_performer(args.performer)
            if not performer:
                print(f"Performer '{args.performer}' not found.")
                sys.exit(1)

            disambiguation = f" ({performer['disambiguation']})" if performer.get("disambiguation") else ""
            print(f"\nPerformer: {performer['name']}{disambiguation}")
            print(f"ID: {performer['id']}")
            print(f"Scene Count: {performer.get('scene_count', 0)}")

            scenes = client.find_scenes_by_performer(int(performer["id"]), limit=args.limit)
            if scenes:
                if args.json:
                    print(json.dumps(scenes, indent=2))
                else:
                    print(f"\nScenes ({len(scenes)}):")
                    for scene in scenes:
                        print_scene_summary(scene)
            else:
                print("\nNo scenes found for this performer.")

        elif args.query:
            scenes = client.search_scenes(args.query, limit=args.limit)
            if scenes:
                if args.json:
                    print(json.dumps(scenes, indent=2))
                else:
                    print(f"\nSearch results for '{args.query}' ({len(scenes)} scenes):")
                    for scene in scenes:
                        print_scene_summary(scene)
                    if len(scenes) == 1:
                        print("\n--- Detailed View ---")
                        print_scene(scenes[0], verbose=args.verbose)
            else:
                print(f"No scenes found matching '{args.query}'.")
                sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Stashapp: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
