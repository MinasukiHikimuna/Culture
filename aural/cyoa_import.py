#!/usr/bin/env python3
"""
CYOA Import Script

Imports Choose Your Own Adventure releases to Stashapp with decision tree navigation.
This is a specialized script for complex CYOA releases that need linked scene descriptions.

Usage:
    uv run python cyoa_import.py <cyoa-json-file> [options]

Options:
    --download-only    Only download audio files, don't import to Stashapp
    --update-only      Only update scene descriptions (requires scene-mapping.json)
    --dry-run          Show what would be done without making changes
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone, UTC
from pathlib import Path

import httpx
from dotenv import load_dotenv
from stashapp_importer import (
    STASH_BASE_URL,
    STASH_OUTPUT_DIR,
    StashappClient,
    convert_audio_to_video,
)


# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")


def download_soundgasm_audio(url: str, output_path: Path) -> Path:
    """Download audio from Soundgasm."""
    print(f"  Downloading: {url}")

    # Extract audio URL from Soundgasm page
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch Soundgasm page: {response.status_code}"
            )

        html = response.text
        audio_match = re.search(r'm4a:\s*"([^"]+)"', html)
        if not audio_match:
            raise RuntimeError("Could not find audio URL in Soundgasm page")

        audio_url = audio_match.group(1)
        print(f"  Audio URL: {audio_url}")

        # Download the audio file
        audio_response = client.get(audio_url)
        if audio_response.status_code != 200:
            raise RuntimeError(
                f"Failed to download audio: {audio_response.status_code}"
            )

        output_path.write_bytes(audio_response.content)
        print(f"  Downloaded: {output_path}")

    return output_path


def generate_description(
    audio_data: dict,
    cyoa_data: dict,
    scene_mapping: dict[str, str],
    start_scene_id: str | None,
) -> str:
    """Generate scene description with decision tree links."""
    lines: list[str] = []

    # Title
    lines.append(f"# {audio_data['title']}")
    lines.append("")

    # Ending indicator
    if audio_data.get("isEnding"):
        ending_labels = {
            "bad": "**BAD ENDING**",
            "good": "**GOOD ENDING**",
            "best": "**BEST ENDING**",
        }
        ending_label = ending_labels.get(audio_data.get("endingType"), "**ENDING**")
        lines.append(ending_label)
        lines.append("")

    # Tags
    tags = audio_data.get("tags", [])
    if tags:
        # Filter out ending type tags
        display_tags = [
            t for t in tags if t not in ["Bad Ending", "Good Ending", "Best Ending"]
        ]
        if display_tags:
            lines.append(f"Tags: {', '.join(display_tags)}")
            lines.append("")

    # Choices (if not an ending)
    choices = audio_data.get("choices", [])
    if choices:
        lines.append("## Choose your path:")
        lines.append("")

        for choice in choices:
            target_scene_id = scene_mapping.get(choice["leadsTo"])
            if target_scene_id:
                lines.append(f"- [{choice['label']}](/scenes/{target_scene_id})")
            else:
                lines.append(f"- {choice['label']} (scene not yet imported)")
        lines.append("")

    # Navigation
    lines.append("---")
    if start_scene_id:
        lines.append(f"[Start Over](/scenes/{start_scene_id})")

    return "\n".join(lines)


class CYOAImporter:
    """Main CYOA import class."""

    def __init__(
        self,
        output_dir: Path | None = None,
        dry_run: bool = False,
        download_only: bool = False,
        update_only: bool = False,
    ):
        self.client = StashappClient()
        self.output_dir = output_dir or STASH_OUTPUT_DIR
        self.dry_run = dry_run
        self.download_only = download_only
        self.update_only = update_only

    def load_cyoa_data(self, json_path: Path) -> dict:
        """Load CYOA data from JSON file."""
        content = json_path.read_text(encoding="utf-8")
        return json.loads(content)

    def load_scene_mapping(self, mapping_path: Path) -> dict[str, str]:
        """Load or create scene mapping."""
        try:
            content = mapping_path.read_text(encoding="utf-8")
            return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_scene_mapping(self, mapping_path: Path, mapping: dict[str, str]) -> None:
        """Save scene mapping."""
        mapping_path.write_text(
            json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def process_audio(
        self,
        audio_key: str,
        audio_data: dict,
        cyoa_data: dict,
        download_dir: Path,
        performer: str,
        date: str,
        post_id: str,
    ) -> dict:
        """Process a single audio."""
        print(f"\n[{audio_key}] {audio_data['title']}")

        # Generate filenames
        title_slug = re.sub(r"[^a-zA-Z0-9]", "_", audio_data["title"])[:30]
        audio_filename = f"{audio_key}_{title_slug}.m4a"
        audio_path = download_dir / audio_filename

        title_clean = re.sub(r"[^a-zA-Z0-9 ]", "", audio_data["title"])[:40]
        video_filename = (
            f"{performer} - {date} - {post_id} - CYOA {audio_key} - {title_clean}.mp4"
        )
        video_path = self.output_dir / video_filename

        # Download audio if needed
        if audio_path.exists():
            print("  Audio already downloaded")
        elif self.dry_run:
            print(f"  [DRY RUN] Would download: {audio_data['url']}")
        else:
            download_soundgasm_audio(audio_data["url"], audio_path)

        if self.download_only:
            return {"audioPath": audio_path, "videoPath": None, "sceneId": None}

        # Convert to video if needed
        if video_path.exists():
            print("  Video already exists")
        elif self.dry_run:
            print(f"  [DRY RUN] Would convert to video: {video_filename}")
        else:
            success = convert_audio_to_video(audio_path, video_path)
            if not success:
                print("  Error: Failed to convert audio to video")
                return {"audioPath": audio_path, "videoPath": None, "sceneId": None}

        return {"audioPath": audio_path, "videoPath": video_path, "sceneId": None}

    def import_audios(self, cyoa_data: dict, download_dir: Path) -> dict[str, dict]:
        """Import all audios and collect scene IDs."""
        performer = cyoa_data["performer"]
        post_id = cyoa_data["reddit_post_id"]

        # Get date from Reddit post (assume current date if not available)
        date = datetime.now(UTC).strftime("%Y-%m-%d")

        results: dict[str, dict] = {}
        audio_keys = list(cyoa_data["audios"].keys())

        print(f"\nProcessing {len(audio_keys)} audios...")

        for audio_key in audio_keys:
            audio_data = cyoa_data["audios"][audio_key]
            result = self.process_audio(
                audio_key, audio_data, cyoa_data, download_dir, performer, date, post_id
            )
            results[audio_key] = result

            # Small delay between downloads
            if not self.dry_run:
                time.sleep(1)

        return results

    def scan_and_find_scenes(
        self, cyoa_data: dict, download_dir: Path
    ) -> dict[str, str]:
        """Trigger scan and find scenes."""
        print("\nTriggering Stashapp scan...")

        if self.dry_run:
            print("[DRY RUN] Would trigger scan")
            return {}

        self.client.trigger_scan()
        print("Waiting for scan to complete...")
        self.client.wait_for_scan(120)  # Wait up to 2 minutes

        # Wait a bit more for indexing
        time.sleep(5)

        # Find scenes by searching for the CYOA prefix
        scene_mapping: dict[str, str] = {}
        post_id = cyoa_data["reddit_post_id"]

        print("\nFinding imported scenes...")

        for audio_key in cyoa_data["audios"].keys():
            # Search by path
            query = """
                query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
                    findScenes(scene_filter: $scene_filter, filter: $filter) {
                        scenes { id title files { basename } }
                    }
                }
            """

            result = self.client.query(
                query,
                {
                    "scene_filter": {
                        "path": {"value": post_id, "modifier": "INCLUDES"}
                    },
                    "filter": {"per_page": 100},
                },
            )

            scenes = result.get("findScenes", {}).get("scenes", [])

            # Find the scene matching this audio key
            for scene in scenes:
                for file in scene.get("files", []):
                    if f"CYOA {audio_key} -" in file.get("basename", ""):
                        scene_mapping[audio_key] = scene["id"]
                        print(f"  Found [{audio_key}]: Scene {scene['id']}")
                        break
                if audio_key in scene_mapping:
                    break

            if audio_key not in scene_mapping:
                print(f"  Warning: Scene not found for [{audio_key}]")

        return scene_mapping

    def create_group(
        self, cyoa_data: dict, scene_mapping: dict[str, str]
    ) -> dict | None:
        """Create group and add scenes."""
        group_name = (
            f"CYOA: {cyoa_data['title'].replace('Choose Your Own Adventure: ', '')}"
        )

        print(f"\nCreating group: {group_name}")

        if self.dry_run:
            print("[DRY RUN] Would create group")
            return None

        group = self.client.find_or_create_group(
            group_name,
            {
                "synopsis": f"Choose Your Own Adventure with {cyoa_data['total_audios']} audios and {cyoa_data['total_endings']} endings."
            },
        )

        # Add scenes to group with ordering
        audio_keys = list(cyoa_data["audios"].keys())
        for i, audio_key in enumerate(audio_keys):
            scene_id = scene_mapping.get(audio_key)

            if scene_id:
                self.client.add_scene_to_group(scene_id, group["id"], i + 1)
                print(f"  Added [{audio_key}] to group at index {i + 1}")

        return group

    def update_scene_metadata(
        self, scene_id: str, audio_data: dict, cyoa_data: dict, performer: str
    ) -> None:
        """Update scene with metadata."""
        cyoa_title = cyoa_data["title"].replace("Choose Your Own Adventure: ", "")
        updates: dict = {"title": f"[CYOA] {cyoa_title} - {audio_data['title']}"}

        # Add performer
        performer_obj = self.client.find_performer(performer)
        if performer_obj:
            updates["performer_ids"] = [performer_obj["id"]]

        # Add studio
        studio = self.client.find_studio(performer)
        if studio:
            updates["studio_id"] = studio["id"]

        # Add date from CYOA JSON
        if cyoa_data.get("release_date"):
            updates["date"] = cyoa_data["release_date"]

        # Match and add tags
        tags = audio_data.get("tags", [])
        if tags:
            tag_ids: list[str] = []
            for tag_name in tags:
                tag = self.client.find_tag(tag_name)
                if tag:
                    tag_ids.append(tag["id"])
                    print(f"    Matched tag: {tag_name} -> {tag['id']}")
                else:
                    print(f"    Tag not found: {tag_name}")
            if tag_ids:
                updates["tag_ids"] = tag_ids

        self.client.update_scene(scene_id, updates)

    def update_descriptions(
        self, cyoa_data: dict, scene_mapping: dict[str, str]
    ) -> None:
        """Update all scene descriptions with decision tree links."""
        print("\nUpdating scene descriptions with decision tree links...")

        start_scene_id = scene_mapping.get("0")

        for audio_key, audio_data in cyoa_data["audios"].items():
            scene_id = scene_mapping.get(audio_key)

            if not scene_id:
                print(f"  Skipping [{audio_key}]: No scene ID")
                continue

            description = generate_description(
                audio_data, cyoa_data, scene_mapping, start_scene_id
            )

            if self.dry_run:
                print(f"  [DRY RUN] Would update [{audio_key}] (Scene {scene_id})")
                print(f"    Description preview: {description[:100]}...")
            else:
                self.client.update_scene(scene_id, {"details": description})
                print(f"  Updated [{audio_key}] (Scene {scene_id})")

    def run(self, json_path: Path) -> None:
        """Run the full import process."""
        # Load CYOA data
        print(f"Loading CYOA data from: {json_path}")
        cyoa_data = self.load_cyoa_data(json_path)

        print(f"\nCYOA: {cyoa_data['title']}")
        print(f"Performer: {cyoa_data['performer']}")
        print(f"Audios: {cyoa_data['total_audios']}")
        print(f"Endings: {cyoa_data['total_endings']}")

        # Setup directories
        base_dir = json_path.parent
        download_dir = base_dir / cyoa_data["reddit_post_id"]
        mapping_path = base_dir / f"{cyoa_data['reddit_post_id']}_scene_mapping.json"

        # Create download directory
        download_dir.mkdir(parents=True, exist_ok=True)

        scene_mapping = self.load_scene_mapping(mapping_path)

        if self.update_only:
            # Only update descriptions and metadata
            if not scene_mapping:
                print("Error: No scene mapping found. Run import first.")
                return

            # Update metadata for all scenes
            print("\nUpdating scene metadata...")
            for audio_key, audio_data in cyoa_data["audios"].items():
                scene_id = scene_mapping.get(audio_key)
                if scene_id:
                    print(f"  Updating [{audio_key}] (Scene {scene_id})")
                    self.update_scene_metadata(
                        scene_id, audio_data, cyoa_data, cyoa_data["performer"]
                    )

            self.update_descriptions(cyoa_data, scene_mapping)
            print("\nUpdate complete!")
            return

        # Test connection
        print("\nTesting Stashapp connection...")
        if not self.dry_run and not self.download_only:
            version = self.client.get_version()
            print(f"Connected to Stashapp {version}")

        # Download and convert all audios
        self.import_audios(cyoa_data, download_dir)

        if self.download_only:
            print("\nDownload complete!")
            return

        # Scan and find scenes
        scene_mapping = self.scan_and_find_scenes(cyoa_data, download_dir)

        # Save mapping
        if not self.dry_run:
            self.save_scene_mapping(mapping_path, scene_mapping)
            print(f"\nScene mapping saved to: {mapping_path}")

        # Create group
        group = self.create_group(cyoa_data, scene_mapping)

        # Update scene metadata and descriptions
        print("\nUpdating scene metadata...")
        for audio_key, audio_data in cyoa_data["audios"].items():
            scene_id = scene_mapping.get(audio_key)
            if scene_id and not self.dry_run:
                self.update_scene_metadata(
                    scene_id, audio_data, cyoa_data, cyoa_data["performer"]
                )

        self.update_descriptions(cyoa_data, scene_mapping)

        # Generate cover images
        print("\nGenerating cover images...")
        if not self.dry_run:
            self.client.generate_covers()
            self.client.wait_for_scan(60)
            print("Covers generated!")

        # Summary
        print(f"\n{'=' * 60}")
        print("CYOA Import Complete!")
        print("=" * 60)
        print(f"Scenes imported: {len(scene_mapping)}")
        if group:
            print(f"Group URL: {STASH_BASE_URL}/groups/{group['id']}")
        if scene_mapping.get("0"):
            print(f"Start scene: {STASH_BASE_URL}/scenes/{scene_mapping['0']}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CYOA Import Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Imports Choose Your Own Adventure releases to Stashapp with decision tree navigation.

Examples:
  uv run python cyoa_import.py data/cyoa/ni2wma_high_school_reunion.json
  uv run python cyoa_import.py data/cyoa/ni2wma_high_school_reunion.json --download-only
  uv run python cyoa_import.py data/cyoa/ni2wma_high_school_reunion.json --update-only
""",
    )
    parser.add_argument("cyoa_json_file", help="Path to the CYOA JSON file")
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Only download audio files, don't import to Stashapp",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Only update scene descriptions (requires existing scene mapping)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    json_path = Path(args.cyoa_json_file)

    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        return 1

    # Check output directory (unless download-only)
    if not args.download_only and not STASH_OUTPUT_DIR.exists():
        print(f"Error: Stash output directory not found: {STASH_OUTPUT_DIR}")
        print("Make sure the volume is mounted.")
        return 1

    importer = CYOAImporter(
        dry_run=args.dry_run,
        download_only=args.download_only,
        update_only=args.update_only,
    )

    try:
        importer.run(json_path)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
