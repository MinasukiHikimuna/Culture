#!/usr/bin/env python3
"""
Stashapp Importer - Import releases to Stashapp

This module transforms audio files to video and imports them into Stashapp
with full metadata including performers, studios, and tags.

Usage (CLI):
    uv run python stashapp_importer.py <release_directory>

Usage (Module):
    from stashapp_importer import StashappImporter
    importer = StashappImporter()
    result = importer.process_release(release_dir)
"""

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import oshash
from config import STASH_BASE_URL as CONFIG_STASH_BASE_URL
from config import STASH_OUTPUT_DIR as CONFIG_STASH_OUTPUT_DIR
from config import local_path_to_windows
from dotenv import load_dotenv
from exceptions import StashappUnavailableError


# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")


class StashScanStuckError(Exception):
    """Raised when Stashapp scan appears to be stuck and not completing."""

    pass

# Stashapp Configuration
_stash_base = os.getenv("AURAL_STASHAPP_URL")
STASH_URL = f"{_stash_base}/graphql" if _stash_base else None
STASH_API_KEY = os.getenv("AURAL_STASHAPP_API_KEY")
STASH_OUTPUT_DIR = CONFIG_STASH_OUTPUT_DIR
STASH_BASE_URL = CONFIG_STASH_BASE_URL or "https://stash-aural.chiefsclub.com"

# Static image for audio-to-video conversion
STATIC_IMAGE = Path(__file__).parent / "gwa.png"

# LM Studio Configuration
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")


class StashappClient:
    """Simple Stashapp GraphQL client."""

    def __init__(self, url: str | None = None, api_key: str | None = None):
        url = url or STASH_URL
        api_key = api_key or STASH_API_KEY

        if not url or not api_key:
            raise ValueError(
                "Missing required Stashapp credentials. "
                "Please set STASHAPP_URL and STASHAPP_API_KEY in your .env file."
            )
        self.url = url
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)

    def query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query."""
        variables = variables or {}
        try:
            response = self.client.post(
                self.url,
                headers={"ApiKey": self.api_key, "Content-Type": "application/json"},
                json={"query": query, "variables": variables},
            )
        except (httpx.ConnectError, OSError) as e:
            # Network errors indicate Stashapp is unavailable
            raise StashappUnavailableError(self.url, e) from e

        if response.status_code != 200:
            raise RuntimeError(f"HTTP error: {response.status_code} {response.text}")

        result = response.json()
        if result.get("errors"):
            raise RuntimeError(f"GraphQL errors: {json.dumps(result['errors'])}")

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

        # Exact match (case-insensitive)
        for p in performers:
            if p["name"].lower() == name.lower():
                return p
        return None

    def find_performer_by_url(self, url: str) -> dict | None:
        """Find performer by URL (checks if any of their URLs contain the given string)."""
        query = """
            query FindPerformers($performer_filter: PerformerFilterType!) {
                findPerformers(performer_filter: $performer_filter) {
                    performers { id name disambiguation urls }
                }
            }
        """
        result = self.query(
            query,
            {
                "performer_filter": {
                    "url": {"value": url, "modifier": "INCLUDES"}
                }
            },
        )
        performers = result.get("findPerformers", {}).get("performers", [])
        return performers[0] if performers else None

    def create_performer(
        self,
        name: str,
        image_url: str | None = None,
        reddit_username: str | None = None,
        gender: str | None = None,
    ) -> dict:
        """Create a new performer."""
        query = """
            mutation PerformerCreate($input: PerformerCreateInput!) {
                performerCreate(input: $input) { id name }
            }
        """
        input_data: dict = {"name": name}
        if image_url:
            input_data["image"] = image_url
        if reddit_username:
            input_data["url"] = f"https://www.reddit.com/user/{reddit_username}/"
        if gender:
            input_data["gender"] = gender

        result = self.query(query, {"input": input_data})
        return result["performerCreate"]

    def find_or_create_performer(
        self,
        name: str,
        image_url: str | None = None,
        reddit_username: str | None = None,
        gender: str | None = None,
    ) -> dict:
        """Find or create a performer by name."""
        performer = self.find_performer(name)
        if performer:
            print(
                f"  Found existing performer: {performer['name']} (ID: {performer['id']})"
            )
            return performer

        performer = self.create_performer(name, image_url, reddit_username, gender)
        extras = []
        if image_url:
            extras.append("avatar")
        if gender:
            extras.append(f"gender: {gender}")
        if extras:
            print(
                f"  Created new performer: {performer['name']} "
                f"(ID: {performer['id']}) with {', '.join(extras)}"
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

    def find_group(self, name: str) -> dict | None:
        """Find group by name."""
        query = """
            query FindGroups($filter: FindFilterType!) {
                findGroups(filter: $filter) {
                    groups { id name }
                }
            }
        """
        result = self.query(query, {"filter": {"q": name, "per_page": 10}})
        groups = result.get("findGroups", {}).get("groups", [])

        # Exact match (case-insensitive)
        for g in groups:
            if g["name"].lower() == name.lower():
                return g
        return None

    def create_group(self, input_data: dict) -> dict:
        """Create a new group."""
        query = """
            mutation GroupCreate($input: GroupCreateInput!) {
                groupCreate(input: $input) { id name }
            }
        """
        result = self.query(query, {"input": input_data})
        return result["groupCreate"]

    def find_or_create_group(self, name: str, options: dict | None = None) -> dict:
        """Find or create a group by name."""
        options = options or {}
        group = self.find_group(name)
        if group:
            print(f"  Found existing group: {group['name']} (ID: {group['id']})")
            return group

        group = self.create_group({"name": name, **options})
        print(f"  Created new group: {group['name']} (ID: {group['id']})")
        return group

    def add_scene_to_group(
        self, scene_id: str, group_id: str, scene_index: int | None = None
    ) -> None:
        """Add a scene to a group with optional scene_index."""
        query = """
            mutation SceneUpdate($input: SceneUpdateInput!) {
                sceneUpdate(input: $input) { id }
            }
        """
        group_input: dict = {"group_id": group_id}
        if scene_index is not None:
            group_input["scene_index"] = scene_index

        input_data = {"id": scene_id, "groups": [group_input]}
        self.query(query, {"input": input_data})

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

    def find_tag(self, name: str) -> dict | None:
        """Find a tag by name (case-insensitive, checks aliases too)."""
        tags = self.get_all_tags()
        normalized_name = name.lower()

        for tag in tags:
            if tag["name"].lower() == normalized_name:
                return tag
            # Check aliases
            for alias in tag.get("aliases", []):
                if alias.lower() == normalized_name:
                    return tag
        return None

    def trigger_scan(self, paths: list[str] | None = None) -> str:
        """Trigger a metadata scan with minimal configuration.

        Args:
            paths: Optional list of paths to scan. If empty or None, scans all.
                   Paths should be in the format expected by Stashapp (Windows paths).
        """
        query = """
            mutation MetadataScan($input: ScanMetadataInput!) {
                metadataScan(input: $input)
            }
        """
        scan_input: dict = {
            "paths": paths if paths else [],
            "scanGenerateCovers": True,
            "scanGenerateClipPreviews": False,
            "scanGenerateImagePreviews": False,
            "scanGeneratePhashes": False,
            "scanGeneratePreviews": False,
            "scanGenerateSprites": False,
            "scanGenerateThumbnails": False,
        }
        result = self.query(query, {"input": scan_input})
        return result["metadataScan"]

    def wait_for_scan(self, timeout: int = 30) -> bool:
        """Wait for any running scan jobs to complete."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.query("query { jobQueue { id status } }")
            jobs = result.get("jobQueue") or []
            if len(jobs) == 0:
                return True
            time.sleep(1)
        return False

    def find_recent_scenes(self, limit: int = 20) -> list[dict]:
        """Find most recently created scenes."""
        query = """
            query FindScenes($filter: FindFilterType!) {
                findScenes(filter: $filter) {
                    scenes { id title created_at files { path basename } }
                }
            }
        """
        result = self.query(
            query,
            {"filter": {"per_page": limit, "sort": "created_at", "direction": "DESC"}},
        )
        return result.get("findScenes", {}).get("scenes", [])

    def find_scene_by_basename(self, basename: str) -> dict | None:
        """Find a scene by file basename using path filter."""
        # Extract the video/post ID from the filename
        # Format: "Author - YYYY-MM-DD - ID - Title.mp4"
        # IDs can be: Reddit (alphanumeric), YouTube (with hyphens/underscores), etc.
        post_id_match = re.search(r"- ([\w\-]{6,}) -", basename)
        search_value = post_id_match.group(1) if post_id_match else basename

        query = """
            query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
                findScenes(scene_filter: $scene_filter, filter: $filter) {
                    scenes { id title files { path basename } }
                }
            }
        """
        result = self.query(
            query,
            {
                "scene_filter": {
                    "path": {"value": search_value, "modifier": "INCLUDES"}
                },
                "filter": {"per_page": 10},
            },
        )
        scenes = result.get("findScenes", {}).get("scenes", [])

        for scene in scenes:
            for f in scene.get("files", []):
                if f.get("basename") == basename:
                    return scene
        return None

    def find_scene_by_oshash(self, file_oshash: str) -> dict | None:
        """Find a scene by oshash using findSceneByHash query."""
        query = """
            query FindSceneByHash($input: SceneHashInput!) {
                findSceneByHash(input: $input) {
                    id
                    title
                    files { id path basename }
                }
            }
        """
        result = self.query(query, {"input": {"oshash": file_oshash}})
        return result.get("findSceneByHash")

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

    def get_version(self) -> str:
        """Get Stashapp version (for connection testing)."""
        result = self.query("query { version { version } }")
        return result.get("version", {}).get("version", "unknown")

    def generate_covers(self) -> str:
        """Generate cover images for scenes."""
        query = """
            mutation MetadataGenerate($input: GenerateMetadataInput!) {
                metadataGenerate(input: $input)
            }
        """
        input_data = {
            "covers": True,
            "markers": False,
            "phashes": False,
            "previewOptions": {
                "previewPreset": "slow",
                "previewSegmentDuration": 0.75,
                "previewSegments": 12,
                "previewExcludeStart": "0",
                "previewExcludeEnd": "0",
            },
            "previews": False,
            "sprites": False,
        }
        result = self.query(query, {"input": input_data})
        return result.get("metadataGenerate", "")

    def get_scene_with_files(self, scene_id: str) -> dict | None:
        """Get a scene with its files and fingerprints."""
        query = """
            query GetScene($id: ID!) {
                findScene(id: $id) {
                    id
                    title
                    date
                    urls
                    files {
                        id
                        path
                        basename
                        fingerprints {
                            type
                            value
                        }
                    }
                }
            }
        """
        result = self.query(query, {"id": scene_id})
        return result.get("findScene")

    def set_file_fingerprint(self, file_id: str, fp_type: str, value: str) -> dict:
        """Set a fingerprint on a file."""
        query = """
            mutation SetFingerprints($input: FileSetFingerprintsInput!) {
                fileSetFingerprints(input: $input)
            }
        """
        return self.query(
            query,
            {
                "input": {
                    "id": file_id,
                    "fingerprints": [{"type": fp_type, "value": value}],
                }
            },
        )

    def find_scenes_by_performer_and_date(
        self, performer_name: str, date: str
    ) -> list[dict]:
        """Find scenes by performer name and date."""
        performer = self.find_performer(performer_name)
        if not performer:
            return []

        query = """
            query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
                findScenes(scene_filter: $scene_filter, filter: $filter) {
                    scenes {
                        id
                        title
                        date
                        urls
                        files {
                            id
                            path
                            basename
                            fingerprints {
                                type
                                value
                            }
                        }
                    }
                }
            }
        """
        result = self.query(
            query,
            {
                "scene_filter": {
                    "performers": {"value": [performer["id"]], "modifier": "INCLUDES"},
                    "date": {"value": date, "modifier": "EQUALS"},
                },
                "filter": {"per_page": 100},
            },
        )
        return result.get("findScenes", {}).get("scenes", [])

    def find_scenes_by_performer(self, performer_name: str) -> list[dict]:
        """Find scenes by performer name (no date filter)."""
        performer = self.find_performer(performer_name)
        if not performer:
            return []

        query = """
            query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
                findScenes(scene_filter: $scene_filter, filter: $filter) {
                    scenes {
                        id
                        title
                        date
                        urls
                        performers {
                            id
                            name
                        }
                        files {
                            id
                            path
                            basename
                            fingerprints {
                                type
                                value
                            }
                        }
                    }
                }
            }
        """
        result = self.query(
            query,
            {
                "scene_filter": {
                    "performers": {"value": [performer["id"]], "modifier": "INCLUDES"}
                },
                "filter": {"per_page": -1},
            },
        )
        return result.get("findScenes", {}).get("scenes", [])

    def find_scene_by_fingerprint(
        self, fingerprint_type: str, fingerprint_value: str
    ) -> dict | None:
        """Find a scene by fingerprint."""
        query = """
            query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
                findScenes(scene_filter: $scene_filter, filter: $filter) {
                    scenes {
                        id
                        title
                        files {
                            id
                            fingerprints {
                                type
                                value
                            }
                        }
                    }
                }
            }
        """
        # Search for scenes and filter by fingerprint
        result = self.query(query, {"scene_filter": {}, "filter": {"per_page": -1}})

        scenes = result.get("findScenes", {}).get("scenes", [])
        for scene in scenes:
            for file in scene.get("files", []):
                for fp in file.get("fingerprints", []):
                    if (
                        fp["type"] == fingerprint_type
                        and fp["value"] == fingerprint_value
                    ):
                        return scene
        return None


def extract_tags_from_title(title: str) -> list[str]:
    """Extract bracketed tags from title."""
    pattern = re.compile(r"\[([^\]]+)\]")
    return [match.strip() for match in pattern.findall(title)]


def extract_tags_from_text(text: str) -> list[str]:
    """Extract bracketed tags from post body text (handles escaped brackets)."""
    pattern = re.compile(r"\\+\[([^\]]+)\\+\]")
    return [match.strip() for match in pattern.findall(text)]


def parse_gender_from_flair(flair_text: str | None) -> str | None:
    """
    Parse gender from Reddit flair text.

    Returns Stashapp GenderEnum value:
    MALE, FEMALE, TRANSGENDER_MALE, TRANSGENDER_FEMALE, INTERSEX, NON_BINARY
    """
    if not flair_text:
        return None

    flair = flair_text.lower()

    # Check for Reddit emoji placeholders (most common in GWA)
    if ":female:" in flair:
        return "FEMALE"
    if ":male:" in flair:
        return "MALE"
    if ":nonbinary:" in flair or ":non-binary:" in flair or ":nb:" in flair:
        return "NON_BINARY"
    if ":trans:" in flair:
        if ":transm:" in flair or ":ftm:" in flair:
            return "TRANSGENDER_MALE"
        if ":transf:" in flair or ":mtf:" in flair:
            return "TRANSGENDER_FEMALE"
        return None  # Can't determine specific type

    # Check for Unicode symbols
    if "\u2640" in flair_text:  # Female sign
        return "FEMALE"
    if "\u2642" in flair_text:  # Male sign
        return "MALE"

    # Check for pronoun indicators
    if "she/her" in flair or "(she)" in flair:
        return "FEMALE"
    if "he/him" in flair or "(he)" in flair:
        return "MALE"
    if "they/them" in flair:
        return "NON_BINARY"

    # Check for bracketed gender markers [F], [M], [NB]
    if re.search(r"\[f\]", flair):
        return "FEMALE"
    if re.search(r"\[m\]", flair) and not re.search(r"\[fm\]|\[mf\]", flair):
        return "MALE"
    if re.search(r"\[nb\]", flair):
        return "NON_BINARY"

    # Text patterns
    if "female" in flair:
        return "FEMALE"
    if "male" in flair and "female" not in flair:
        return "MALE"
    if "non-binary" in flair or "nonbinary" in flair:
        return "NON_BINARY"

    return None


def generate_group_name(release_title: str, primary_performer: str) -> str:
    """Generate a clean group name using LLM."""
    prompt = f"""Generate a short, clean group name for organizing audio files.

Original title: {release_title}
Performer: {primary_performer}

Rules:
- Remove all tags in brackets like [F4A], [2 Parts], [Script Fill], etc.
- Remove special characters and emoji
- Keep the core title essence (usually 3-6 words)
- Don't include performer name (it's stored separately)
- Don't add quotes around the name

Return ONLY the group name, nothing else."""

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                LM_STUDIO_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "model": "local-model",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 100,
                },
            )

        if response.status_code != 200:
            raise RuntimeError(f"LLM request failed: {response.status_code}")

        data = response.json()
        group_name = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        group_name = group_name.strip()

        if group_name:
            # Clean up any remaining quotes or extra whitespace
            return group_name.strip("\"'").strip()

    except Exception as error:
        print(f"  Warning: LLM group name generation failed: {error}")

    # Fallback: simple regex-based cleanup
    fallback = re.sub(r"\[[^\]]+\]", "", release_title)  # Remove bracketed tags
    fallback = re.sub(r"[^\w\s\-\'\,\.\!\?]", "", fallback)  # Remove special chars
    fallback = fallback.strip()

    # Truncate if too long
    if len(fallback) > 60:
        fallback = fallback[:60].rsplit(" ", 1)[0]

    return fallback or "Untitled Group"


def get_reddit_avatar(username: str) -> str | None:
    """Fetch Reddit avatar for a user."""
    try:
        url = f"https://www.reddit.com/user/{username}/about.json"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; audio-extractor/1.0)"},
            )

        if response.status_code == 200:
            data = response.json()
            icon_url = data.get("data", {}).get("icon_img", "")
            if icon_url:
                # Unescape HTML entities in URL
                icon_url = icon_url.replace("&amp;", "&")
                return icon_url
    except Exception as e:
        print(f"    Warning: Could not fetch Reddit avatar for {username}: {e}")
    return None


def extract_all_tags(release: dict) -> list[str]:
    """Extract all tags from release title and post body."""
    tags: list[str] = []

    # Tags from title
    title = release.get("title", "")
    tags.extend(extract_tags_from_title(title))

    # Tags from Reddit post body
    reddit_data = release.get("enrichmentData", {}).get("reddit", {})
    selftext = reddit_data.get("selftext", "")
    if selftext:
        tags.extend(extract_tags_from_text(selftext))

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_tags: list[str] = []
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_tags.append(tag)

    return unique_tags


def match_tags_with_stash(
    extracted_tags: list[str], stash_tags: list[dict]
) -> list[str]:
    """Match extracted tags with existing Stashapp tags (including aliases)."""
    matched_tag_ids: list[str] = []

    # Build lookup dict: lowercase name/alias -> tag id
    tag_lookup: dict[str, str] = {}
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
    static_image = STATIC_IMAGE

    # Check if static image exists
    if not static_image.exists():
        print(f"  Warning: Static image not found at {static_image}")
        print("  Creating a simple black image...")
        subprocess.run(
            [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=1280x720:d=1",
                "-frames:v",
                "1",
                str(static_image),
            ],
            capture_output=True,
            check=True,
        )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(static_image),
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

    print("  Running ffmpeg conversion...")

    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"  ffmpeg error: {e}")
        return False

    return output_path.exists()


def format_output_filename(
    release: dict,
    audio_source: dict | None = None,
    index: int = 0,
    total_sources: int = 1,
) -> str:
    """
    Generate output filename in Stashapp format.

    Args:
        release: The release data
        audio_source: The audio source being processed (optional)
        index: The index of the audio source (optional)
        total_sources: Total number of audio sources (optional)
    """
    performer = release.get("primaryPerformer", "Unknown")

    # Parse date from Unix timestamp
    date_str = "Unknown"
    release_date = release.get("releaseDate")
    if release_date:
        date = datetime.fromtimestamp(release_date, tz=timezone.utc)
        date_str = date.strftime("%Y-%m-%d")

    # Get Reddit post ID (try both 'id' and 'post_id' keys)
    reddit_data = release.get("enrichmentData", {}).get("reddit", {})
    post_id = reddit_data.get("id") or reddit_data.get("post_id") or release.get("id") or "unknown"

    # Get clean title (remove emoji and brackets)
    title = release.get("title", "Unknown")
    # Remove bracketed tags for filename
    clean_title = re.sub(r"\[[^\]]+\]", "", title).strip()
    # Remove emoji and special chars (keep unicode letters)
    clean_title = re.sub(r"[^\w\s\-\.\,\!\?\'\"\u0080-\uFFFF]", "", clean_title).strip()
    # Truncate if too long
    if len(clean_title) > 100:
        clean_title = clean_title[:100].rsplit(" ", 1)[0]
    # Sanitize for filesystem
    clean_title = re.sub(r'[<>:"/\\|?*]', "", clean_title)

    # Add version identifier for multi-version releases
    version_suffix = ""
    if total_sources > 1:
        version_slug = (
            audio_source.get("versionInfo", {}).get("slug") if audio_source else None
        ) or f"v{index + 1}"
        version_suffix = f" - {version_slug}"

    return f"{performer} - {date_str} - {post_id} - {clean_title}{version_suffix}.mp4"


class StashappImporter:
    """Main importer class."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        output_dir: Path | str | None = None,
        verbose: bool = False,
    ):
        self.client = StashappClient(url or STASH_URL, api_key or STASH_API_KEY)
        self.output_dir = Path(output_dir) if output_dir else STASH_OUTPUT_DIR
        self.verbose = verbose

    def test_connection(self) -> str:
        """Test connection to Stashapp."""
        print("Testing Stashapp connection...")
        version = self.client.get_version()
        print(f"Connected to Stashapp {version}")
        return version

    def process_release(self, release_dir: str | Path) -> dict:
        """
        Process a release directory and import to Stashapp.

        Returns:
            Result dict with sceneId and success status
        """
        release_dir = Path(release_dir)
        release_json_path = release_dir / "release.json"

        try:
            release_data = json.loads(release_json_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error: release.json not found in {release_dir}")
            return {"success": False, "error": f"release.json not found: {e}"}

        print(f"\n{'=' * 60}")
        title = release_data.get("title", "Unknown")[:60]
        print(f"Processing: {title}...")
        print("=" * 60)

        # Find audio files
        audio_sources = release_data.get("audioSources", [])
        if len(audio_sources) == 0:
            print("Error: No audio sources found in release")
            return {"success": False, "error": "No audio sources"}

        # Get all Stashapp tags for matching
        print("\nFetching Stashapp tags...")
        stash_tags = self.client.get_all_tags()
        print(f"  Found {len(stash_tags)} tags in Stashapp")

        # Create studio subdirectory (named after primary performer)
        studio_name = release_data.get("primaryPerformer", "Unknown")
        # Sanitize for filesystem: remove/replace problematic characters
        safe_studio_name = re.sub(r'[<>:"/\\|?*]', "_", studio_name).strip()
        studio_dir = self.output_dir / safe_studio_name
        studio_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nStudio directory: {studio_dir}")

        last_scene_id: str | None = None
        scene_ids: list[dict] = []  # Track all scene IDs for grouping

        # Process each audio source
        for i, source in enumerate(audio_sources):
            audio_info = source.get("audio", {})
            audio_path_str = audio_info.get("filePath", "")

            # Make path absolute if relative
            audio_path = Path(audio_path_str)
            if not audio_path.is_absolute():
                audio_path = Path(__file__).parent / audio_path_str

            if not audio_path.exists():
                print(f"  Warning: Audio file not found: {audio_path}")
                continue

            print(f"\n[Audio {i + 1}/{len(audio_sources)}] {audio_path.name}")

            # Check for duplicate audio by fingerprint before converting
            audio_checksum = source.get("audio", {}).get("checksum", {}).get("sha256")
            if audio_checksum:
                existing_scene = self.client.find_scene_by_fingerprint(
                    "audio_sha256", audio_checksum
                )
                if existing_scene:
                    print(
                        f"  Duplicate detected: audio already imported as scene "
                        f"{existing_scene['id']}"
                    )
                    scene_ids.append({"id": existing_scene["id"], "index": i})
                    last_scene_id = existing_scene["id"]
                    continue

            # Generate output filename (with version slug for multi-version releases)
            output_filename = format_output_filename(
                release_data, source, i, len(audio_sources)
            )
            output_path = studio_dir / output_filename

            print(f"  Output: {output_filename}")

            # Convert audio to video
            if output_path.exists():
                print("  Video already exists, skipping conversion")
            else:
                success = convert_audio_to_video(audio_path, output_path)
                if not success:
                    print("  Error: Failed to convert audio to video")
                    continue
                print(f"  Conversion successful: {output_path}")

            # Trigger Stashapp scan for the studio directory only
            print("\n  Triggering Stashapp scan...")
            try:
                windows_path = local_path_to_windows(studio_dir)
                print(f"  Scanning: {windows_path}")
                job_id = self.client.trigger_scan(paths=[windows_path])
            except ValueError as e:
                print(f"  Warning: Path mapping failed ({e}), scanning all")
                job_id = self.client.trigger_scan()
            print(f"  Scan job started: {job_id}")

            # Wait for scan to complete
            print("  Waiting for scan to complete...")
            scan_completed = self.client.wait_for_scan(60)

            if not scan_completed:
                raise StashScanStuckError(
                    f"Stashapp scan job {job_id} did not complete within 60 seconds. "
                    "The scan may be stuck. Please check Stashapp and restart if needed."
                )

            # Compute oshash for the converted video (used for scene lookup)
            file_oshash = oshash.oshash(str(output_path))

            # Find the scene by oshash (with retries to allow for database indexing)
            scene = None
            max_retries = 10
            retry_delay = 2  # seconds

            for retry in range(max_retries):
                scene = self.client.find_scene_by_oshash(file_oshash)
                if scene:
                    break
                if retry < max_retries - 1:
                    print(
                        f"  Scene not found yet, retrying in {retry_delay}s... "
                        f"({retry + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)

            if not scene:
                raise StashScanStuckError(
                    f"Scene not found after scan completed. oshash: {file_oshash}. "
                    "Stashapp may not be scanning the expected directory, or the scan is stuck."
                )

            print(f"  Found scene ID: {scene['id']}")
            last_scene_id = scene["id"]
            scene_ids.append({"id": scene["id"], "index": i})

            # Prepare metadata updates
            updates: dict = {}

            # Title (add version name for multi-version releases)
            scene_title = release_data.get("title", "")
            version_name = source.get("versionInfo", {}).get("version_name")
            if len(audio_sources) > 1 and version_name:
                scene_title = f"{scene_title} [{version_name}]"
            updates["title"] = scene_title

            # Date
            release_date = release_data.get("releaseDate")
            if release_date:
                date = datetime.fromtimestamp(release_date, tz=timezone.utc)
                updates["date"] = date.strftime("%Y-%m-%d")

            # URLs
            urls: list[str] = []
            reddit_data = release_data.get("enrichmentData", {}).get("reddit", {})
            if reddit_data.get("url"):
                urls.append(reddit_data["url"])
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
                details = details.replace("\\", "")  # Escape chars
                updates["details"] = details[:5000]

            # Director (script author)
            llm_analysis = release_data.get("enrichmentData", {}).get("llmAnalysis", {})
            script_author = llm_analysis.get("script", {}).get("author")
            if not script_author:
                script_author = release_data.get("scriptAuthor")
            if script_author:
                updates["director"] = script_author
                print(f"  Director (script author): {script_author}")

            # Performers - use per-audio performers if available, fallback to release-level
            print("\n  Processing performers...")
            performer_ids: list[str] = []

            # Check for per-audio performers first
            per_audio_performers = source.get("versionInfo", {}).get("performers", [])

            if per_audio_performers:
                # Use per-audio performers for this specific scene
                print(
                    f"    Using per-audio performers: {', '.join(per_audio_performers)}"
                )
                for performer_name in per_audio_performers:
                    avatar_url = get_reddit_avatar(performer_name)
                    if avatar_url:
                        print(f"    Found Reddit avatar for {performer_name}")
                    performer = self.client.find_or_create_performer(
                        performer_name,
                        image_url=avatar_url,
                        reddit_username=performer_name,
                    )
                    performer_ids.append(performer["id"])
            else:
                # Fallback to release-level performers
                primary_performer = release_data.get("primaryPerformer")

                # Get author flair for gender (from Reddit post data)
                author_flair_text = reddit_data.get("author_flair_text", "")
                primary_gender = parse_gender_from_flair(author_flair_text)
                if primary_gender:
                    print(
                        f'    Detected gender from flair "{author_flair_text}": '
                        f"{primary_gender}"
                    )

                if primary_performer:
                    avatar_url = get_reddit_avatar(primary_performer)
                    if avatar_url:
                        print(f"    Found Reddit avatar for {primary_performer}")
                    performer = self.client.find_or_create_performer(
                        primary_performer,
                        image_url=avatar_url,
                        reddit_username=primary_performer,
                        gender=primary_gender,
                    )
                    performer_ids.append(performer["id"])

                # Additional performers
                additional_performers = llm_analysis.get("performers", {}).get(
                    "additional", []
                )
                if not additional_performers:
                    additional_performers = release_data.get("additionalPerformers", [])

                for additional in additional_performers:
                    avatar_url = get_reddit_avatar(additional)
                    if avatar_url:
                        print(f"    Found Reddit avatar for {additional}")
                    # Note: We don't have flair for additional performers from the post data
                    performer = self.client.find_or_create_performer(
                        additional,
                        image_url=avatar_url,
                        reddit_username=additional,
                    )
                    performer_ids.append(performer["id"])

            if performer_ids:
                updates["performer_ids"] = performer_ids

            # Studio (same as primary performer for solo releases)
            print("\n  Processing studio...")
            if release_data.get("primaryPerformer"):
                studio = self.client.find_or_create_studio(
                    release_data["primaryPerformer"]
                )
                updates["studio_id"] = studio["id"]

            # Tags - use per-audio tags if available, fallback to release-level
            print("\n  Processing tags...")
            per_audio_tags = source.get("versionInfo", {}).get("tags", [])

            if per_audio_tags:
                # Use per-audio tags for this specific scene
                print(f"    Using per-audio tags: {len(per_audio_tags)} tags")
                extracted_tags = per_audio_tags
            else:
                # Fallback to release-level tags
                extracted_tags = extract_all_tags(release_data)
                print(
                    f"    Extracted {len(extracted_tags)} tags from title and post body"
                )

            if stash_tags and extracted_tags:
                matched_tag_ids = match_tags_with_stash(extracted_tags, stash_tags)
                if matched_tag_ids:
                    updates["tag_ids"] = matched_tag_ids
                    print(f"    Matched {len(matched_tag_ids)} tags")

            # Update scene
            print("\n  Updating scene metadata...")
            self.client.update_scene(scene["id"], updates)
            print("  Scene updated successfully!")

            # Set audio fingerprint for duplicate detection
            if audio_checksum:
                scene_with_files = self.client.get_scene_with_files(scene["id"])
                files = scene_with_files.get("files", []) if scene_with_files else []
                file_id = files[0]["id"] if files else None
                if file_id:
                    self.client.set_file_fingerprint(
                        file_id, "audio_sha256", audio_checksum
                    )
                    print(f"  Set audio fingerprint: {audio_checksum[:16]}...")

            # Clean up source audio file after successful import
            if audio_path.exists():
                audio_path.unlink()
                print(f"  Cleaned up source audio: {audio_path.name}")

        # Create group if multiple scenes were processed
        group_id: str | None = None
        if len(scene_ids) > 1:
            print("\n  Creating group for multi-audio release...")
            group_name = generate_group_name(
                release_data.get("title", ""),
                release_data.get("primaryPerformer", ""),
            )
            print(f'  Group name: "{group_name}"')

            group_options: dict = {}
            release_date = release_data.get("releaseDate")
            if release_date:
                date = datetime.fromtimestamp(release_date, tz=timezone.utc)
                group_options["date"] = date.strftime("%Y-%m-%d")
            reddit_data = release_data.get("enrichmentData", {}).get("reddit", {})
            if reddit_data.get("url"):
                group_options["urls"] = [reddit_data["url"]]

            group = self.client.find_or_create_group(group_name, group_options)
            group_id = group["id"]

            # Associate scenes with group
            for scene_info in scene_ids:
                self.client.add_scene_to_group(
                    scene_info["id"], group["id"], scene_info["index"] + 1
                )
                print(
                    f"    Added scene {scene_info['id']} to group at index "
                    f"{scene_info['index'] + 1}"
                )
            print(f"  Group created/updated: {STASH_BASE_URL}/groups/{group['id']}")

        # Save Stashapp scene IDs to release.json for idempotency
        if scene_ids:
            release_data["stashapp_scene_ids"] = [s["id"] for s in scene_ids]
            release_data["stashapp_scene_id"] = last_scene_id
            if group_id:
                release_data["stashapp_group_id"] = group_id
            release_json_path.write_text(
                json.dumps(release_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        return {
            "success": True,
            "sceneId": last_scene_id,
            "sceneUrl": f"{STASH_BASE_URL}/scenes/{last_scene_id}"
            if last_scene_id
            else None,
            "groupId": group_id,
            "groupUrl": f"{STASH_BASE_URL}/groups/{group_id}" if group_id else None,
        }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import releases to Stashapp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python stashapp_importer.py data/releases/SweetnEvil86/1oj6y4p_hitting_on

This script transforms audio files to video and imports them into Stashapp
with full metadata including performers, studios, and tags.
""",
    )
    parser.add_argument("release_dir", help="Path to the release directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    release_dir = Path(args.release_dir)
    if not release_dir.exists():
        print(f"Error: Directory not found: {release_dir}")
        return 1

    # Check output directory
    if not STASH_OUTPUT_DIR.exists():
        print(f"Error: Stash output directory not found: {STASH_OUTPUT_DIR}")
        print("Make sure the volume is mounted.")
        return 1

    try:
        importer = StashappImporter(verbose=args.verbose)
        importer.test_connection()
        result = importer.process_release(release_dir)

        if result["success"]:
            print(f"\n{'=' * 60}")
            print("Import completed successfully!")
            if result.get("sceneUrl"):
                print(f"Scene URL: {result['sceneUrl']}")
            if result.get("groupUrl"):
                print(f"Group URL: {result['groupUrl']}")
            print("=" * 60)
            return 0
        else:
            print(f"\nImport failed: {result.get('error')}")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
