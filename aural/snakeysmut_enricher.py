#!/usr/bin/env python3
"""
SnakeySmut Enricher - Enrich Stashapp scenes with SnakeySmut metadata.

Matches scenes by Pornhub viewkey and adds:
- SnakeySmut URL
- Description as details (if empty)
"""

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
    response.raise_for_status()
    result = response.json()
    if "errors" in result:
        raise Exception(f"GraphQL error: {result['errors']}")
    return result["data"]


def get_scene(scene_id: int) -> dict:
    """Get scene by ID with URLs and details."""
    query = """
        query FindScene($id: ID!) {
            findScene(id: $id) {
                id
                title
                urls
                details
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
) -> dict:
    """Update scene with new URLs and optionally details/title."""
    query = """
        mutation SceneUpdate($input: SceneUpdateInput!) {
            sceneUpdate(input: $input) { id title urls details }
        }
    """
    input_data = {"id": str(scene_id), "urls": urls}
    if details:
        input_data["details"] = details
    if title:
        input_data["title"] = title
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


def enrich_scene(scene_id: int) -> dict | None:
    """Enrich a Stashapp scene with SnakeySmut metadata."""
    scene = get_scene(scene_id)
    if not scene:
        print(f"Scene {scene_id} not found")
        return None

    print(f"Scene: {scene['title']}")
    print(f"Current URLs: {scene['urls']}")
    print(f"Current details: {scene['details'][:100] if scene['details'] else '(empty)'}...")

    # Find Pornhub viewkey in existing URLs
    viewkey = None
    for url in scene.get("urls", []):
        viewkey = extract_viewkey(url)
        if viewkey:
            break

    if not viewkey:
        print("No Pornhub viewkey found in scene URLs")
        return None

    print(f"Viewkey: {viewkey}")

    # Find matching SnakeySmut post
    post = find_snakeysmut_by_viewkey(viewkey)
    if not post:
        print("No matching SnakeySmut post found")
        return None

    print(f"Found SnakeySmut post: {post['slug']}")

    # Build updated URLs (append snakeysmut URL if not already present)
    snakeysmut_url = post["url"]
    existing_urls = scene.get("urls", [])
    if snakeysmut_url not in existing_urls:
        updated_urls = [*existing_urls, snakeysmut_url]
        print(f"Adding URL: {snakeysmut_url}")
    else:
        updated_urls = existing_urls
        print("SnakeySmut URL already present")

    # Set details if empty
    details = None
    if not scene.get("details"):
        details = format_details(post)
        print("Setting details from SnakeySmut post")

    # Update title (SnakeySmut has cleaner titles than Pornhub)
    title = None
    snakeysmut_title = post["title"]
    if scene["title"] != snakeysmut_title:
        title = snakeysmut_title
        print(f"Updating title: {snakeysmut_title}")

    # Update scene
    if updated_urls != existing_urls or details or title:
        result = update_scene(scene_id, updated_urls, details, title)
        print(f"Updated scene {scene_id}")
        return result
    print("No changes needed")
    return scene


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: uv run python snakeysmut_enricher.py <scene_id>")
        sys.exit(1)

    scene_id = int(sys.argv[1])
    enrich_scene(scene_id)
