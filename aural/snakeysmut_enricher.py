#!/usr/bin/env python3
"""
SnakeySmut Enricher - Enrich Stashapp scenes with SnakeySmut metadata.

Matches scenes by Pornhub viewkey and adds:
- SnakeySmut URL
- Description as details (if empty)
"""

import base64
import json
import os
import re
from pathlib import Path

import httpx
from config import SNAKEYSMUT_DIR
from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / ".env")

STASH_URL = f"{os.getenv('AURAL_STASHAPP_URL')}/graphql"
STASH_API_KEY = os.getenv("AURAL_STASHAPP_API_KEY")


def query_stash(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL query against Stashapp."""
    headers = {"ApiKey": STASH_API_KEY, "Content-Type": "application/json"}
    response = httpx.post(
        STASH_URL,
        json={"query": query, "variables": variables or {}},
        headers=headers,
        timeout=30,
    )
    if response.status_code != 200:
        print(f"HTTP Error: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        response.raise_for_status()
    result = response.json()
    if "errors" in result:
        raise Exception(f"GraphQL error: {result['errors']}")
    return result["data"]


def get_scene(scene_id: int, full: bool = False) -> dict:
    """Get scene by ID.

    Args:
        scene_id: The scene ID to fetch
        full: If True, fetch all fields needed for merging
    """
    if full:
        query = """
            query FindScene($id: ID!) {
                findScene(id: $id) {
                    id
                    title
                    date
                    urls
                    details
                    director
                    tags { id name }
                    performers { id }
                    studio { id }
                }
            }
        """
    else:
        query = """
            query FindScene($id: ID!) {
                findScene(id: $id) {
                    id
                    title
                    urls
                    details
                    director
                }
            }
        """
    result = query_stash(query, {"id": str(scene_id)})
    return result["findScene"]


def update_scene(
    scene_id: int,
    urls: list[str],
    details: str | None = None,
    title: str | None = None,
    director: str | None = None,
) -> dict:
    """Update scene with new URLs and optionally details/title/director."""
    query = """
        mutation SceneUpdate($input: SceneUpdateInput!) {
            sceneUpdate(input: $input) { id title urls details director }
        }
    """
    input_data = {"id": str(scene_id), "urls": urls}
    if details:
        input_data["details"] = details
    if title:
        input_data["title"] = title
    if director:
        input_data["director"] = director
    result = query_stash(query, {"input": input_data})
    return result["sceneUpdate"]


def load_snakeysmut_post(slug: str) -> dict:
    """Load a SnakeySmut post by slug."""
    post_path = SNAKEYSMUT_DIR / "posts" / f"{slug}.json"
    with post_path.open() as f:
        return json.load(f)


def find_snakeysmut_by_viewkey(viewkey: str) -> dict | None:
    """Find SnakeySmut post by Pornhub viewkey."""
    posts_dir = SNAKEYSMUT_DIR / "posts"
    for post_file in posts_dir.glob("*.json"):
        with post_file.open() as f:
            post = json.load(f)
        for platform in post.get("platforms", []):
            if viewkey in platform.get("url", ""):
                return post
    return None


def extract_viewkey(url: str) -> str | None:
    """Extract Pornhub viewkey from URL."""
    match = re.search(r"viewkey=([a-f0-9]+)", url)
    return match.group(1) if match else None


def normalize_url(url: str) -> str:
    """Normalize URL for comparison (http->https, remove www)."""
    url = url.replace("http://", "https://")
    url = url.replace("://www.", "://")
    return url


def add_url_if_new(url: str, url_list: list[str]) -> bool:
    """Add URL to list if not already present. Prefers https over http.

    Returns True if URL was added or upgraded, False if already present.
    """
    normalized = normalize_url(url)

    for i, existing in enumerate(url_list):
        if normalize_url(existing) == normalized:
            # URL exists - upgrade http to https if needed
            if existing.startswith("http://") and url.startswith("https://"):
                url_list[i] = url
                return True
            return False

    # URL doesn't exist, add it
    url_list.append(url)
    return True


def format_details(post: dict) -> str:
    """Format SnakeySmut post data as scene details."""
    lines = []

    if post.get("inline_tags"):
        tags_str = " ".join(f"[{tag}]" for tag in post["inline_tags"])
        lines.append(tags_str)

    if post.get("script_credit"):
        credit = post["script_credit"]
        author = credit.get("author", "Unknown")
        script_type = credit.get("type", "")
        if lines:
            lines.append("")
        if script_type:
            lines.append(f"Script by {author} ({script_type})")
        else:
            lines.append(f"Script by {author}")

    return "\n".join(lines)


def find_snakeysmut_post_for_scene(scene: dict, url_index: dict[str, dict] | None = None) -> dict | None:
    """Find matching SnakeySmut post for a scene by any URL."""
    # Try Pornhub viewkey first (fastest)
    for url in scene.get("urls", []):
        viewkey = extract_viewkey(url)
        if viewkey:
            post = find_snakeysmut_by_viewkey(viewkey)
            if post:
                return post

    # Fall back to URL index lookup
    if url_index is None:
        url_index = build_url_index()

    for url in scene.get("urls", []):
        normalized = normalize_url(url)
        if normalized in url_index:
            return url_index[normalized]

    return None


def _is_reddit_sourced(scene: dict) -> bool:
    """Check if scene was sourced from Reddit (has Reddit URL and good data)."""
    has_reddit_url = any("reddit.com" in url.lower() for url in scene.get("urls", []))
    has_reddit_title = "[" in scene.get("title", "") and "]" in scene.get("title", "")
    return has_reddit_url and has_reddit_title


def _collect_urls_from_post(post: dict, existing_urls: list[str]) -> list[str]:
    """Collect URLs from SnakeySmut post, adding to existing URLs."""
    updated_urls = list(existing_urls)

    # Add snakeysmut.com URL
    if add_url_if_new(post["url"], updated_urls):
        print(f"  Adding URL: {post['url']}")

    # Add platform URLs (skip user profiles - script writers go in director)
    for platform in post.get("platforms", []):
        platform_url = platform.get("url", "")
        if not platform_url:
            continue
        if "/u/" in platform_url or "/user/" in platform_url:
            continue
        if add_url_if_new(platform_url, updated_urls):
            print(f"  Adding URL: {platform_url}")

    return updated_urls


def enrich_scene(scene_id: int, post: dict | None = None) -> dict | None:
    """Enrich a Stashapp scene with SnakeySmut metadata.

    For Reddit-sourced scenes: only adds missing URLs (title/details already good)
    For Pornhub-sourced scenes: full enrichment (title, details, URLs)

    Args:
        scene_id: The scene ID to enrich
        post: Optional pre-matched SnakeySmut post (avoids re-lookup)
    """
    scene = get_scene(scene_id)
    if not scene:
        print(f"Scene {scene_id} not found")
        return None

    is_reddit = _is_reddit_sourced(scene)
    source_type = "Reddit" if is_reddit else "Pornhub/other"

    print(f"Scene: {scene['title'][:60]}...")
    print(f"Source: {source_type}")
    print(f"Current URLs: {len(scene['urls'])}")

    # Find matching SnakeySmut post if not provided
    if post is None:
        post = find_snakeysmut_post_for_scene(scene)

    if not post:
        print("No matching SnakeySmut post found")
        return None

    print(f"Matched post: {post['slug']}")

    # Build updated URLs (always add missing URLs)
    existing_urls = scene.get("urls", [])
    updated_urls = _collect_urls_from_post(post, existing_urls)

    # For non-Reddit scenes: also update title and details
    details = None
    title = None

    if not is_reddit:
        # Set details if empty
        if not scene.get("details"):
            details = format_details(post)
            print("  Setting details from SnakeySmut post")

        # Update title (SnakeySmut has cleaner titles than Pornhub)
        snakeysmut_title = post["title"]
        if scene["title"] != snakeysmut_title:
            title = snakeysmut_title
            print(f"  Updating title: {snakeysmut_title}")

    # Set director from script credit if not already set
    director = None
    script_credit = post.get("script_credit")
    if script_credit and not scene.get("director"):
        author = script_credit.get("author", "")
        if author:
            director = author
            print(f"  Setting director: {author}")

    # Update scene
    if updated_urls != existing_urls or details or title or director:
        result = update_scene(scene_id, updated_urls, details, title, director)
        print(f"Updated scene {scene_id}")
        return result
    print("No changes needed")
    return scene


def find_snakeysmut_by_url(url: str) -> dict | None:
    """Find SnakeySmut post by any platform URL."""
    posts_dir = SNAKEYSMUT_DIR / "posts"
    normalized = normalize_url(url)

    for post_file in posts_dir.glob("*.json"):
        with post_file.open() as f:
            post = json.load(f)
        for platform in post.get("platforms", []):
            if normalize_url(platform.get("url", "")) == normalized:
                return post
    return None


def get_scene_cover_url(scene_id: int) -> str | None:
    """Get the screenshot/cover URL for a scene."""
    query = """
        query FindScene($id: ID!) {
            findScene(id: $id) {
                paths { screenshot }
            }
        }
    """
    result = query_stash(query, {"id": str(scene_id)})
    scene = result.get("findScene")
    if scene and scene.get("paths"):
        return scene["paths"].get("screenshot")
    return None


def _merge_title(dest: dict, src: dict) -> str:
    """Determine merged title, preferring Reddit format."""
    dest_has_reddit = "[" in dest["title"] and "]" in dest["title"]
    src_has_reddit = "[" in src["title"] and "]" in src["title"]

    if src_has_reddit and not dest_has_reddit:
        print("  Title: using source (Reddit format)")
        return src["title"]
    if dest_has_reddit and not src_has_reddit:
        print("  Title: using destination (Reddit format)")
        return dest["title"]

    # Both or neither have Reddit title - use the longer one
    if len(src["title"]) > len(dest["title"]):
        print("  Title: using source (longer)")
        return src["title"]
    print("  Title: using destination (longer)")
    return dest["title"]


def _merge_details(dest: dict, src: dict) -> str:
    """Merge details, appending SnakeySmut tags if present."""
    dest_details = dest.get("details") or ""
    src_details = src.get("details") or ""

    # Use longer details as base (Reddit posts are longer)
    if len(src_details) > len(dest_details):
        base_details, other_details = src_details, dest_details
        print("  Details: using source as base")
    else:
        base_details, other_details = dest_details, src_details
        print("  Details: using destination as base")

    # Append SnakeySmut tags if they look like tags and aren't already included
    if (
        other_details
        and other_details not in base_details
        and other_details.strip().startswith("[")
    ):
        print("  Details: appending SnakeySmut tags")
        return f"{base_details}\n\n---\n\n{other_details}"

    return base_details


def _copy_cover_from_scene(scene_id: int) -> str | None:
    """Fetch and base64 encode cover image from a scene."""
    cover_url = get_scene_cover_url(scene_id)
    if not cover_url:
        return None

    try:
        response = httpx.get(cover_url, headers={"ApiKey": STASH_API_KEY}, timeout=30)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("utf-8")
    except Exception as e:
        print(f"  Cover: failed to copy ({e})")
        return None


def merge_scenes(scene_id_1: int, scene_id_2: int) -> dict | None:
    """Merge two duplicate scenes into one.

    The scene with the smaller ID becomes the destination.
    Merge strategy:
    - Title: prefer Reddit format (with tags in title)
    - Date: earliest date
    - Details: Reddit post + SnakeySmut tags appended
    - URLs: union of all URLs
    - Tags: union of all tags
    - Cover: preserve from Pornhub scene (custom artwork)
    """
    dest_id, src_id = min(scene_id_1, scene_id_2), max(scene_id_1, scene_id_2)
    print(f"Merging scene {src_id} into {dest_id}")

    dest = get_scene(dest_id, full=True)
    src = get_scene(src_id, full=True)
    if not dest or not src:
        print("One or both scenes not found")
        return None

    print(f"  Destination: {dest['title'][:60]}...")
    print(f"  Source: {src['title'][:60]}...")

    # Merge fields
    merged_title = _merge_title(dest, src)

    dates = [d for d in [dest.get("date"), src.get("date")] if d]
    merged_date = min(dates) if dates else None
    print(f"  Date: {merged_date} (earliest)")

    merged_details = _merge_details(dest, src)

    merged_urls = list(dest.get("urls") or [])
    for url in src.get("urls") or []:
        add_url_if_new(url, merged_urls)
    print(f"  URLs: {len(merged_urls)} total")

    dest_tag_ids = {t["id"] for t in dest.get("tags") or []}
    src_tag_ids = {t["id"] for t in src.get("tags") or []}
    merged_tag_ids = list(dest_tag_ids | src_tag_ids)
    print(f"  Tags: {len(merged_tag_ids)} total (was {len(dest_tag_ids)} + {len(src_tag_ids)})")

    # Handle cover image - prefer Pornhub artwork
    dest_has_pornhub = any("pornhub" in u.lower() for u in dest.get("urls") or [])
    src_has_pornhub = any("pornhub" in u.lower() for u in src.get("urls") or [])

    cover_image = None
    if dest_has_pornhub:
        print("  Cover: keeping destination (Pornhub)")
    elif src_has_pornhub:
        cover_image = _copy_cover_from_scene(src_id)
        if cover_image:
            print("  Cover: copying from source (Pornhub)")

    # Build merge values
    values: dict = {
        "id": str(dest_id),
        "title": merged_title,
        "urls": merged_urls,
        "tag_ids": merged_tag_ids,
    }
    if merged_date:
        values["date"] = merged_date
    if merged_details:
        values["details"] = merged_details
    if cover_image:
        values["cover_image"] = cover_image

    # Execute merge
    query = """
        mutation SceneMerge($input: SceneMergeInput!) {
            sceneMerge(input: $input) { id title urls }
        }
    """
    input_data = {
        "destination": str(dest_id),
        "source": [str(src_id)],
        "o_history": True,
        "play_history": True,
        "values": values,
    }

    result = query_stash(query, {"input": input_data})
    merged = result["sceneMerge"]
    print(f"\nMerged into scene {merged['id']}: {merged['title'][:60]}...")
    print(f"URLs: {len(merged['urls'])}")
    return merged


def build_url_index() -> dict[str, dict]:
    """Build index mapping normalized URLs to SnakeySmut posts."""
    posts_dir = SNAKEYSMUT_DIR / "posts"
    url_index: dict[str, dict] = {}

    for post_file in posts_dir.glob("*.json"):
        with post_file.open() as f:
            post = json.load(f)

        # Index by snakeysmut.com URL
        url_index[normalize_url(post["url"])] = post

        # Index by platform URLs
        for platform in post.get("platforms", []):
            platform_url = platform.get("url", "")
            if platform_url:
                url_index[normalize_url(platform_url)] = post

    return url_index


def find_performer_id(name: str) -> str | None:
    """Find performer ID by name."""
    query = """
        query FindPerformers($filter: FindFilterType!) {
            findPerformers(filter: $filter) {
                performers { id name }
            }
        }
    """
    result = query_stash(query, {"filter": {"q": name, "per_page": 10}})
    performers = result.get("findPerformers", {}).get("performers", [])
    for p in performers:
        if p["name"].lower() == name.lower():
            return p["id"]
    return performers[0]["id"] if performers else None


def get_performer_scenes(performer_name: str) -> list[dict]:
    """Get all scenes for a performer."""
    performer_id = find_performer_id(performer_name)
    if not performer_id:
        print(f"Performer '{performer_name}' not found")
        return []

    query = """
        query FindScenes($filter: FindFilterType!, $scene_filter: SceneFilterType!) {
            findScenes(filter: $filter, scene_filter: $scene_filter) {
                scenes {
                    id
                    title
                    date
                    urls
                    details
                    tags { id name }
                }
            }
        }
    """
    variables = {
        "filter": {"per_page": -1},
        "scene_filter": {
            "performers": {
                "value": [performer_id],
                "modifier": "INCLUDES",
            }
        },
    }
    result = query_stash(query, variables)
    return result["findScenes"]["scenes"]


def _match_scenes_to_posts(
    scenes: list[dict], url_index: dict[str, dict]
) -> dict[str, list[tuple[dict, dict]]]:
    """Match scenes to SnakeySmut posts by URL.

    Returns: dict mapping slug -> list of (scene, post) tuples
    """
    post_to_scenes: dict[str, list[tuple[dict, dict]]] = {}

    for scene in scenes:
        # Skip scenes that already have snakeysmut.com URL
        if any("snakeysmut.com" in url.lower() for url in scene.get("urls", [])):
            continue

        # Find matching post by URL
        for url in scene.get("urls", []):
            normalized = normalize_url(url)
            if normalized in url_index:
                post = url_index[normalized]
                slug = post["slug"]
                if slug not in post_to_scenes:
                    post_to_scenes[slug] = []
                post_to_scenes[slug].append((scene, post))
                break

    return post_to_scenes


def _process_enrichments(
    enrichments: dict[str, tuple[dict, dict]],
    dry_run: bool,
    limit: int | None,
    actions_taken: int,
) -> int:
    """Process scenes that need enrichment."""
    if not enrichments:
        return actions_taken

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Enrichments:")
    for _slug, (scene, post) in enrichments.items():
        if limit is not None and actions_taken >= limit:
            print(f"\n  Limit of {limit} reached, stopping.")
            break

        print(f"\n  Scene {scene['id']}: {scene['title'][:50]}...")
        print(f"    -> Post: {post['title'][:50]}...")

        if not dry_run:
            enrich_scene(int(scene["id"]), post=post)
        actions_taken += 1

    return actions_taken


def batch_enrich(dry_run: bool = True, limit: int | None = None) -> None:
    """Batch enrich SnakeySmut scenes with metadata from snakeysmut.com."""
    print("Building URL index from SnakeySmut data...")
    url_index = build_url_index()
    print(f"  Indexed {len(url_index)} URLs")

    print("\nFetching SnakeySmut scenes from Stashapp...")
    scenes = get_performer_scenes("SnakeySmut")
    print(f"  Found {len(scenes)} scenes")

    post_to_scenes = _match_scenes_to_posts(scenes, url_index)

    # Only process single matches (no duplicates)
    enrichments = {s: pairs[0] for s, pairs in post_to_scenes.items() if len(pairs) == 1}
    duplicates = {s: pairs for s, pairs in post_to_scenes.items() if len(pairs) > 1}

    print("\nResults:")
    print(f"  Scenes to enrich: {len(enrichments)}")
    print(f"  Duplicate groups (skipped): {len(duplicates)}")

    actions = _process_enrichments(enrichments, dry_run, limit, 0)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Total enriched: {actions}")


def find_duplicates() -> None:
    """Find scenes with overlapping URLs that may be duplicates."""
    print("Fetching SnakeySmut scenes from Stashapp...")
    scenes = get_performer_scenes("SnakeySmut")
    print(f"  Found {len(scenes)} scenes")

    # Build URL -> scene mapping
    url_to_scenes: dict[str, list[dict]] = {}
    for scene in scenes:
        for url in scene.get("urls", []):
            normalized = normalize_url(url)
            if normalized not in url_to_scenes:
                url_to_scenes[normalized] = []
            url_to_scenes[normalized].append(scene)

    # Find URLs shared by multiple scenes
    duplicates: dict[str, list[dict]] = {}
    seen_pairs: set[tuple[str, str]] = set()

    for url, dup_scenes in url_to_scenes.items():
        if len(dup_scenes) > 1:
            # Create a unique key for this duplicate group
            scene_ids = tuple(sorted(s["id"] for s in dup_scenes))
            if scene_ids not in seen_pairs:
                seen_pairs.add(scene_ids)
                duplicates[url] = dup_scenes

    if not duplicates:
        print("\nNo duplicates found.")
        return

    print(f"\nFound {len(duplicates)} duplicate groups:\n")
    for url, dup_scenes in duplicates.items():
        scene_ids = sorted(int(s["id"]) for s in dup_scenes)
        print(f"Shared URL: {url[:60]}...")
        for scene in dup_scenes:
            print(f"  Scene {scene['id']}: {scene['title'][:50]}...")
        print(f"  -> Merge command: uv run python snakeysmut_enricher.py merge {scene_ids[0]} {scene_ids[1]}")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SnakeySmut Stashapp Enricher")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Single scene enrichment
    enrich_parser = subparsers.add_parser("enrich", help="Enrich a single scene")
    enrich_parser.add_argument("scene_id", type=int, help="Scene ID to enrich")

    # Merge two scenes
    merge_parser = subparsers.add_parser("merge", help="Merge two scenes")
    merge_parser.add_argument("scene_id_1", type=int, help="First scene ID")
    merge_parser.add_argument("scene_id_2", type=int, help="Second scene ID")

    # Batch enrichment
    batch_parser = subparsers.add_parser("batch", help="Batch enrich all scenes")
    batch_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without applying (default: True)",
    )
    batch_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply changes (disables dry-run)",
    )
    batch_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of scenes to enrich",
    )

    # Find duplicates
    subparsers.add_parser("duplicates", help="Find duplicate scenes by shared URLs")

    args = parser.parse_args()

    if args.command == "enrich":
        enrich_scene(args.scene_id)
    elif args.command == "merge":
        merge_scenes(args.scene_id_1, args.scene_id_2)
    elif args.command == "batch":
        dry_run = not args.apply
        batch_enrich(dry_run=dry_run, limit=args.limit)
    elif args.command == "duplicates":
        find_duplicates()
    else:
        parser.print_help()
