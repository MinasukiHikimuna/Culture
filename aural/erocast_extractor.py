#!/usr/bin/env python3
"""
Erocast Extractor

Pure audio extractor - downloads HLS streams from erocast.me.
Uses Playwright for metadata extraction and yt-dlp for HLS download.
Returns platform-agnostic schema.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import UTC, datetime, timezone
from pathlib import Path

import config as aural_config
import yt_dlp
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


class ErocastExtractor:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.platform = "erocast"
        self.request_delay = config.get("request_delay", 2.0)
        self.last_request_time = 0
        self.browser = None
        self.page = None
        self.playwright = None
        self.context = None

    def setup_playwright(self):
        """Initialize Playwright browser."""
        try:
            print("Starting Playwright browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self.page = self.context.new_page()
            print("Playwright browser initialized successfully")
        except Exception as error:
            print(f"Failed to initialize Playwright: {error}")
            raise

    def close_browser(self):
        """Close Playwright browser."""
        if self.page:
            self.page.close()
            self.page = None
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        print("Playwright browser closed")

    def extract(self, url: str, target_path: dict) -> dict:
        """
        Extract content from Erocast URL.

        Args:
            url: Erocast URL to extract (e.g., https://erocast.me/track/14078/slug)
            target_path: Dict with 'dir' and 'basename' keys

        Returns:
            Platform-agnostic metadata dict
        """
        self.ensure_rate_limit()

        try:
            print(f"Processing: {url}")

            target_dir = Path(target_path["dir"])
            basename = target_path["basename"]
            target_dir.mkdir(parents=True, exist_ok=True)

            # Check if already extracted (JSON exists)
            json_path = target_dir / f"{basename}.json"
            if json_path.exists():
                try:
                    cached = json.loads(json_path.read_text(encoding="utf-8"))
                    print(f"Using cached extraction for: {url}")
                    return cached
                except json.JSONDecodeError:
                    print(f"Cached JSON unreadable, re-extracting: {url}")

            # Parse track ID from URL
            track_id = self.parse_track_id(url)
            if not track_id:
                raise ValueError(f"Could not parse track ID from URL: {url}")

            # Navigate to page
            print("Loading page...")
            self.page.goto(url, wait_until="domcontentloaded")
            time.sleep(2)  # Wait for dynamic content

            # Extract metadata from JavaScript variable
            song_data = self.extract_metadata(track_id)
            if not song_data:
                raise ValueError(f"Could not extract song_data_{track_id} from page")

            # Get stream URL
            stream_url = song_data.get("stream_url") or song_data.get("file_url")
            if not stream_url:
                raise ValueError("No stream URL found in metadata")

            print(f"Title: {song_data.get('title')}")
            print(f"Author: {song_data.get('user', {}).get('username')}")
            print(f"Duration: {song_data.get('duration')}s")
            print(f"Stream URL: {stream_url[:60]}...")

            # Download audio using yt-dlp
            audio_file_path = target_dir / f"{basename}.m4a"
            self.download_hls(stream_url, audio_file_path)

            # Calculate checksum
            checksum = self.calculate_checksum(audio_file_path)

            # Get file stats
            stats = audio_file_path.stat()

            # Save HTML backup
            html_path = target_dir / f"{basename}.html"
            self.save_html_backup(html_path)

            # Extract tags from song_data
            tags = []
            for tag_obj in song_data.get("tags", []):
                if isinstance(tag_obj, dict) and tag_obj.get("tag"):
                    tags.append(tag_obj["tag"])

            # Build result in platform-agnostic schema
            user_data = song_data.get("user", {})
            result = {
                "audio": {
                    "sourceUrl": url,
                    "downloadUrl": stream_url,
                    "filePath": str(audio_file_path),
                    "format": "m4a",
                    "fileSize": stats.st_size,
                    "checksum": {"sha256": checksum},
                },
                "metadata": {
                    "title": song_data.get("title"),
                    "author": user_data.get("username") or user_data.get("name"),
                    "description": song_data.get("description") or "",
                    "tags": tags,
                    "duration": float(song_data.get("duration", 0)),
                    "platform": {"name": "erocast", "url": "https://erocast.me"},
                },
                "platformData": {
                    "trackId": str(track_id),
                    "slug": self.parse_slug(url),
                    "userId": user_data.get("id"),
                    "username": user_data.get("username"),
                    "artworkUrl": song_data.get("artwork_url"),
                    "releasedAt": song_data.get("released_at"),
                    "plays": song_data.get("plays"),
                    "loves": song_data.get("loves"),
                    "extractedAt": datetime.now(UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                "backupFiles": {"html": str(html_path), "metadata": str(json_path)},
            }

            # Save metadata (serves as completion marker)
            json_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            print(f"Successfully extracted: {song_data.get('title')}")
            return result

        except Exception as error:
            print(f"Failed to extract {url}: {error}")
            raise

    def parse_track_id(self, url: str) -> str | None:
        """Extract track ID from Erocast URL."""
        # URL format: https://erocast.me/track/{id}/{slug}
        match = re.search(r"/track/(\d+)", url)
        return match.group(1) if match else None

    def parse_slug(self, url: str) -> str | None:
        """Extract slug from Erocast URL."""
        # URL format: https://erocast.me/track/{id}/{slug}
        match = re.search(r"/track/\d+/([^/?]+)", url)
        return match.group(1) if match else None

    def extract_metadata(self, track_id: str) -> dict | None:
        """Extract song_data from page JavaScript."""
        return self.page.evaluate(
            f"""() => {{
            return window.song_data_{track_id} || null;
        }}"""
        )

    def download_hls(self, m3u8_url: str, output_path: Path):
        """Download HLS stream using yt-dlp."""
        print("Downloading HLS stream...")

        # yt-dlp adds extension automatically, so use path without extension
        output_template = str(output_path.with_suffix(""))

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            "extract_flat": False,
            # Force mp4/m4a container
            "merge_output_format": "mp4",
            "postprocessors": [],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([m3u8_url])

            # yt-dlp may output without extension or with various extensions
            # Check all possibilities and rename to target .m4a
            no_ext_path = Path(output_template)
            mp4_path = output_path.with_suffix(".mp4")

            if no_ext_path.exists() and not no_ext_path.suffix:
                # File exists without extension - rename to .m4a
                no_ext_path.rename(output_path)
            elif mp4_path.exists() and not output_path.exists():
                mp4_path.rename(output_path)
            elif not output_path.exists():
                # Check for other possible output files
                for ext in ["", ".mp4", ".m4a", ".aac", ".ts"]:
                    candidate = Path(output_template + ext)
                    if candidate.exists():
                        candidate.rename(output_path)
                        break

            if not output_path.exists():
                raise FileNotFoundError(f"Download failed - output file not found: {output_path}")

            print(f"Download complete: {output_path}")

        except Exception as e:
            print(f"yt-dlp download failed: {e}")
            raise

    def save_html_backup(self, html_path: Path):
        """Save HTML content as backup."""
        html_content = self.page.content()
        html_path.write_text(html_content, encoding="utf-8")

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def ensure_rate_limit(self):
        """Ensure rate limiting between requests."""
        now = time.time()
        time_since_last_request = now - self.last_request_time

        if time_since_last_request < self.request_delay:
            delay = self.request_delay - time_since_last_request
            print(f"Rate limiting: waiting {delay * 1000:.0f}ms...")
            time.sleep(delay)

        self.last_request_time = time.time()


def main():
    """CLI entry point for testing."""
    parser = argparse.ArgumentParser(
        description="Extract audio content from Erocast URLs"
    )
    parser.add_argument("url", help="Erocast URL to extract")
    parser.add_argument(
        "--output-dir",
        "-o",
        default=str(aural_config.EROCAST_DIR),
        help=f"Output directory (default: {aural_config.EROCAST_DIR})",
    )
    parser.add_argument(
        "--basename",
        "-b",
        help="Base filename (without extension). If not provided, extracts from URL.",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Extract basename from URL if not provided
    basename = args.basename
    if not basename:
        # Extract slug from URL
        match = re.search(r"/track/\d+/([^/?]+)", args.url)
        if match:
            basename = match.group(1)
        else:
            print("Could not extract basename from URL. Please provide --basename")
            return 1

    target_path = {"dir": args.output_dir, "basename": basename}

    extractor = ErocastExtractor()

    try:
        extractor.setup_playwright()
        result = extractor.extract(args.url, target_path)
        print("\nExtraction complete!")
        print(f"Audio: {result['audio']['filePath']}")
        print(f"Metadata: {result['backupFiles']['metadata']}")
        return 0
    except Exception as e:
        print(f"\nError: {e}")
        return 1
    finally:
        extractor.close_browser()


if __name__ == "__main__":
    sys.exit(main())
