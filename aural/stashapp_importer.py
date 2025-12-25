#!/usr/bin/env python3
"""
Stashapp Importer - Import releases to Stashapp

This script transforms audio files to video and imports them into Stashapp
with full metadata including performers, studios, and tags.

Usage:
    python stashapp_importer.py <release_directory>

Example:
    python stashapp_importer.py data/releases/SweetnEvil86/1oj6y4p_hitting_on_and_picking_up_your_taken
"""

import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

# Stashapp Configuration
STASH_URL = os.getenv("STASHAPP_URL", "https://stash-aural.chiefsclub.com/graphql")
STASH_API_KEY = os.getenv(
    "STASHAPP_API_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJzdGFzaCIsInN1YiI6IkFQSUtleSIsImlhdCI6MTcyMzQ1MzA5OH0.V7_yGP7-07drQoLZsZNJ46WSriQ1NfirT5QjhfZsvNw",
)
STASH_OUTPUT_DIR = Path("/Volumes/Culture 1/Aural_Stash")

# Static image for audio-to-video conversion
STATIC_IMAGE = Path(__file__).parent / "gwa.png"


class StashappClient:
    """Simple Stashapp GraphQL client."""

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

    def find_performer(self, name: str) -> dict | None:
        """Find performer by name."""
        query = """
        query FindPerformers($filter: FindFilterType!) {
            findPerformers(filter: $filter) {
                performers { id name disambiguation }
            }
        }
        """
        result = self.query(query, {"filter": {"q": name, "per_page": 10}})
        performers = result.get("findPerformers", {}).get("performers", [])
        # Exact match
        for p in performers:
            if p["name"].lower() == name.lower():
                return p
        return None

    def create_performer(self, name: str, image_url: str | None = None) -> dict:
        """Create a new performer."""
        query = """
        mutation PerformerCreate($input: PerformerCreateInput!) {
            performerCreate(input: $input) { id name }
        }
        """
        input_data = {"name": name}
        if image_url:
            input_data["image"] = image_url
        result = self.query(query, {"input": input_data})
        return result["performerCreate"]

    def update_performer_image(self, performer_id: str, image_url: str) -> dict:
        """Update performer's image."""
        query = """
        mutation PerformerUpdate($input: PerformerUpdateInput!) {
            performerUpdate(input: $input) { id name image_path }
        }
        """
        result = self.query(query, {"input": {"id": performer_id, "image": image_url}})
        return result["performerUpdate"]

    def find_or_create_performer(
        self, name: str, image_url: str | None = None
    ) -> dict:
        """Find or create a performer by name, optionally setting their image."""
        performer = self.find_performer(name)
        if performer:
            print(
                f"  Found existing performer: {performer['name']} (ID: {performer['id']})"
            )
            return performer
        performer = self.create_performer(name, image_url)
        if image_url:
            print(
                f"  Created new performer: {performer['name']} (ID: {performer['id']}) with avatar"
            )
        else:
            print(
                f"  Created new performer: {performer['name']} (ID: {performer['id']})"
            )
        return performer

    def find_studio(self, name: str) -> dict | None:
        """Find studio by name."""
        query = """
        query FindStudios($filter: FindFilterType!) {
            findStudios(filter: $filter) {
                studios { id name }
            }
        }
        """
        result = self.query(query, {"filter": {"q": name, "per_page": 10}})
        studios = result.get("findStudios", {}).get("studios", [])
        for s in studios:
            if s["name"].lower() == name.lower():
                return s
        return None

    def create_studio(self, name: str) -> dict:
        """Create a new studio."""
        query = """
        mutation StudioCreate($input: StudioCreateInput!) {
            studioCreate(input: $input) { id name }
        }
        """
        result = self.query(query, {"input": {"name": name}})
        return result["studioCreate"]

    def find_or_create_studio(self, name: str) -> dict:
        """Find or create a studio by name."""
        studio = self.find_studio(name)
        if studio:
            print(f"  Found existing studio: {studio['name']} (ID: {studio['id']})")
            return studio
        studio = self.create_studio(name)
        print(f"  Created new studio: {studio['name']} (ID: {studio['id']})")
        return studio

    def get_all_tags(self) -> list[dict]:
        """Get all tags with their aliases."""
        query = """
        query FindTags {
            findTags(filter: { per_page: -1 }) {
                tags { id name aliases }
            }
        }
        """
        result = self.query(query)
        return result.get("findTags", {}).get("tags", [])

    def trigger_scan(self, paths: list[str] = None) -> str:
        """Trigger a metadata scan. Empty paths = scan all stash directories."""
        query = """
        mutation MetadataScan($input: ScanMetadataInput!) {
            metadataScan(input: $input)
        }
        """
        # Use empty paths to trigger full scan (works across different OS path formats)
        result = self.query(query, {"input": {"paths": []}})
        return result["metadataScan"]

    def wait_for_scan(self, timeout: int = 30) -> bool:
        """Wait for any running scan jobs to complete."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            query = "query { jobQueue { id status } }"
            result = self.query(query)
            jobs = result.get("jobQueue") or []
            if not jobs:
                return True
            time.sleep(1)
        return False

    def find_scene_by_basename(self, basename: str) -> dict | None:
        """Find a scene by file basename (filename without path)."""
        query = """
        query FindScenes($filter: FindFilterType!) {
            findScenes(filter: $filter) {
                scenes { id title files { path basename } }
            }
        }
        """
        # Search by filename
        result = self.query(query, {"filter": {"q": basename, "per_page": 10}})
        scenes = result.get("findScenes", {}).get("scenes", [])
        for scene in scenes:
            for f in scene.get("files", []):
                if f.get("basename") == basename:
                    return scene
        return None

    def find_scene_by_path(self, path: str) -> dict | None:
        """Find a scene by file path."""
        query = """
        query FindScenes($filter: SceneFilterType!) {
            findScenes(scene_filter: $filter) {
                scenes { id title files { path } }
            }
        }
        """
        result = self.query(
            query,
            {"filter": {"path": {"value": path, "modifier": "EQUALS"}}},
        )
        scenes = result.get("findScenes", {}).get("scenes", [])
        return scenes[0] if scenes else None

    def update_scene(self, scene_id: str, updates: dict) -> dict:
        """Update a scene with metadata."""
        query = """
        mutation SceneUpdate($input: SceneUpdateInput!) {
            sceneUpdate(input: $input) { id title }
        }
        """
        updates["id"] = scene_id
        result = self.query(query, {"input": updates})
        return result["sceneUpdate"]


def extract_tags_from_title(title: str) -> list[str]:
    """Extract bracketed tags from title."""
    # Match [Tag Name] patterns
    pattern = r"\[([^\]]+)\]"
    tags = re.findall(pattern, title)
    return [tag.strip() for tag in tags]


def extract_tags_from_text(text: str) -> list[str]:
    """Extract bracketed tags from post body text.

    Post body often has escaped brackets like \\[Tag\\]
    """
    # Match escaped brackets: \[Tag\]
    escaped_pattern = r"\\+\[([^\]]+)\\+\]"
    tags = re.findall(escaped_pattern, text)
    return [tag.strip() for tag in tags]


def get_reddit_avatar(username: str) -> str | None:
    """Fetch the avatar URL for a Reddit user."""
    try:
        url = f"https://www.reddit.com/user/{username}/about.json"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; audio-extractor/1.0)"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            icon_url = data.get("data", {}).get("icon_img", "")
            if icon_url:
                # Unescape HTML entities in URL
                return html.unescape(icon_url)
    except Exception as e:
        print(f"    Warning: Could not fetch Reddit avatar for {username}: {e}")
    return None


def extract_all_tags(release: dict) -> list[str]:
    """Extract all tags from release title and post body."""
    tags = []

    # Tags from title
    title = release.get("title", "")
    tags.extend(extract_tags_from_title(title))

    # Tags from Reddit post body
    reddit_data = release.get("enrichmentData", {}).get("reddit", {})
    selftext = reddit_data.get("selftext", "")
    if selftext:
        tags.extend(extract_tags_from_text(selftext))

    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_tags.append(tag)

    return unique_tags


def match_tags_with_stash(extracted_tags: list[str], stash_tags: list[dict]) -> list[str]:
    """Match extracted tags with existing Stashapp tags (including aliases)."""
    matched_tag_ids = []

    # Build lookup dict: lowercase name/alias -> tag
    tag_lookup = {}
    for tag in stash_tags:
        tag_lookup[tag["name"].lower()] = tag["id"]
        for alias in tag.get("aliases", []):
            tag_lookup[alias.lower()] = tag["id"]

    for extracted in extracted_tags:
        extracted_lower = extracted.lower()
        if extracted_lower in tag_lookup:
            tag_id = tag_lookup[extracted_lower]
            if tag_id not in matched_tag_ids:
                matched_tag_ids.append(tag_id)
                print(f"    Matched tag: {extracted} -> ID {tag_id}")

    return matched_tag_ids


def convert_audio_to_video(audio_path: Path, output_path: Path) -> bool:
    """Convert audio file to video with static image using ffmpeg."""
    if not STATIC_IMAGE.exists():
        print(f"  Warning: Static image not found at {STATIC_IMAGE}")
        print("  Creating a simple black image...")
        # Create a simple black image if gwa.png doesn't exist
        subprocess.run(
            [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=1280x720:d=1",
                "-frames:v",
                "1",
                str(STATIC_IMAGE),
            ],
            capture_output=True,
        )

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-loop",
        "1",
        "-i",
        str(STATIC_IMAGE),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        str(output_path),
    ]

    print(f"  Running ffmpeg conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr}")
        return False

    return output_path.exists()


def format_output_filename(release: dict) -> str:
    """Generate output filename in Stashapp format."""
    # Format: Studio - Performer - Date - ID - Title.mp4
    performer = release.get("primaryPerformer", "Unknown")

    # Parse date from Unix timestamp
    release_date = release.get("releaseDate")
    if release_date:
        date_str = datetime.fromtimestamp(release_date).strftime("%Y-%m-%d")
    else:
        date_str = "Unknown"

    # Get Reddit post ID
    reddit_data = release.get("enrichmentData", {}).get("reddit", {})
    post_id = reddit_data.get("id", "unknown")

    # Get clean title (remove emoji and brackets)
    title = release.get("title", "Unknown")
    # Remove bracketed tags for filename
    clean_title = re.sub(r"\[[^\]]+\]", "", title).strip()
    # Remove emoji
    clean_title = re.sub(r"[^\w\s\-\.\,\!\?\'\"]", "", clean_title).strip()
    # Truncate if too long
    if len(clean_title) > 100:
        clean_title = clean_title[:100].rsplit(" ", 1)[0]

    # Sanitize for filesystem
    clean_title = re.sub(r'[<>:"/\\|?*]', "", clean_title)

    filename = f"{performer} - {date_str} - {post_id} - {clean_title}.mp4"
    return filename


def process_release(release_dir: Path, stash_client: StashappClient) -> bool:
    """Process a release directory and import to Stashapp."""
    release_json = release_dir / "release.json"

    if not release_json.exists():
        print(f"Error: release.json not found in {release_dir}")
        return False

    with open(release_json) as f:
        release = json.load(f)

    print(f"\n{'='*60}")
    print(f"Processing: {release.get('title', 'Unknown')[:60]}...")
    print(f"{'='*60}")

    # Find audio files
    audio_sources = release.get("audioSources", [])
    if not audio_sources:
        print("Error: No audio sources found in release")
        return False

    # Get all Stashapp tags for matching
    print("\nFetching Stashapp tags...")
    stash_tags = stash_client.get_all_tags()
    print(f"  Found {len(stash_tags)} tags in Stashapp")

    # Process each audio source
    for i, source in enumerate(audio_sources):
        audio_info = source.get("audio", {})
        audio_path = Path(audio_info.get("filePath", ""))

        # Make path absolute if relative
        if not audio_path.is_absolute():
            audio_path = Path(__file__).parent / audio_path

        if not audio_path.exists():
            print(f"  Warning: Audio file not found: {audio_path}")
            continue

        print(f"\n[Audio {i+1}/{len(audio_sources)}] {audio_path.name}")

        # Generate output filename
        output_filename = format_output_filename(release)
        output_path = STASH_OUTPUT_DIR / output_filename

        print(f"  Output: {output_filename}")

        # Convert audio to video
        if output_path.exists():
            print(f"  Video already exists, skipping conversion")
        else:
            if not convert_audio_to_video(audio_path, output_path):
                print(f"  Error: Failed to convert audio to video")
                continue
            print(f"  Conversion successful: {output_path}")

        # Trigger Stashapp scan
        print(f"\n  Triggering Stashapp scan...")
        job_id = stash_client.trigger_scan()
        print(f"  Scan job started: {job_id}")

        # Wait for scan to complete
        print("  Waiting for scan to complete...")
        stash_client.wait_for_scan(timeout=60)

        # Find the scene by basename (cross-platform compatible)
        scene = stash_client.find_scene_by_basename(output_filename)
        if not scene:
            print(f"  Warning: Scene not found after scan. May need manual refresh.")
            continue

        print(f"  Found scene ID: {scene['id']}")

        # Prepare metadata updates
        updates = {}

        # Title
        updates["title"] = release.get("title", "")

        # Date
        release_date = release.get("releaseDate")
        if release_date:
            updates["date"] = datetime.fromtimestamp(release_date).strftime("%Y-%m-%d")

        # URLs
        urls = []
        reddit_data = release.get("enrichmentData", {}).get("reddit", {})
        if reddit_data.get("url"):
            urls.append(reddit_data["url"])
        # Add audio source URL
        if audio_info.get("sourceUrl"):
            urls.append(audio_info["sourceUrl"])
        if urls:
            updates["urls"] = urls

        # Details (description)
        selftext = reddit_data.get("selftext", "")
        if selftext:
            # Clean up markdown
            details = re.sub(r"\*\*([^*]+)\*\*", r"\1", selftext)  # Bold
            details = re.sub(r"\*([^*]+)\*", r"\1", details)  # Italic
            details = re.sub(r"\\", "", details)  # Escape chars
            updates["details"] = details[:5000]  # Limit length

        # Director (script author)
        script_author = release.get("scriptAuthor")
        if not script_author:
            # Try to extract from description
            match = re.search(r"u/(\w+)", source.get("metadata", {}).get("description", ""))
            if match and match.group(1) != release.get("primaryPerformer"):
                script_author = match.group(1)
        if script_author:
            updates["director"] = script_author
            print(f"  Director (script author): {script_author}")

        # Performers
        print("\n  Processing performers...")
        performer_ids = []
        primary_performer = release.get("primaryPerformer")
        if primary_performer:
            # Fetch Reddit avatar for new performers
            avatar_url = get_reddit_avatar(primary_performer)
            if avatar_url:
                print(f"    Found Reddit avatar for {primary_performer}")
            performer = stash_client.find_or_create_performer(
                primary_performer, image_url=avatar_url
            )
            performer_ids.append(performer["id"])

        for additional in release.get("additionalPerformers", []):
            avatar_url = get_reddit_avatar(additional)
            if avatar_url:
                print(f"    Found Reddit avatar for {additional}")
            performer = stash_client.find_or_create_performer(
                additional, image_url=avatar_url
            )
            performer_ids.append(performer["id"])

        if performer_ids:
            updates["performer_ids"] = performer_ids

        # Studio (same as primary performer for solo releases)
        print("\n  Processing studio...")
        if primary_performer:
            studio = stash_client.find_or_create_studio(primary_performer)
            updates["studio_id"] = studio["id"]

        # Tags (from title and post body)
        print("\n  Processing tags...")
        extracted_tags = extract_all_tags(release)
        print(f"    Extracted {len(extracted_tags)} tags from title and post body")

        if stash_tags and extracted_tags:
            matched_tag_ids = match_tags_with_stash(extracted_tags, stash_tags)
            if matched_tag_ids:
                updates["tag_ids"] = matched_tag_ids
                print(f"    Matched {len(matched_tag_ids)} tags")

        # Update scene
        print("\n  Updating scene metadata...")
        stash_client.update_scene(scene["id"], updates)
        print(f"  Scene updated successfully!")

    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    release_dir = Path(sys.argv[1])
    if not release_dir.exists():
        print(f"Error: Directory not found: {release_dir}")
        sys.exit(1)

    # Check output directory
    if not STASH_OUTPUT_DIR.exists():
        print(f"Error: Stash output directory not found: {STASH_OUTPUT_DIR}")
        print("Make sure the volume is mounted.")
        sys.exit(1)

    # Initialize Stashapp client
    stash_client = StashappClient(STASH_URL, STASH_API_KEY)

    # Test connection
    print("Testing Stashapp connection...")
    try:
        result = stash_client.query("query { version { version } }")
        print(f"Connected to Stashapp {result['version']['version']}")
    except Exception as e:
        print(f"Error connecting to Stashapp: {e}")
        sys.exit(1)

    # Process release
    success = process_release(release_dir, stash_client)

    if success:
        print("\n" + "="*60)
        print("Import completed successfully!")
        print("="*60)
    else:
        print("\nImport failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
