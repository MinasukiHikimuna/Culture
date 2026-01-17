#!/usr/bin/env python3
"""
Audiochan Extractor

Pure audio extractor - downloads directly to target path provided by caller.
Returns platform-agnostic schema.

Audiochan uses a REST API at api.audiochan.com with signed streaming URLs.
No browser automation needed - pure HTTP requests.
"""

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone, UTC
from pathlib import Path

import httpx
from dotenv import load_dotenv
import sys


class AudiochanExtractor:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.platform = "audiochan"
        self.request_delay = config.get("request_delay", 1.0)
        self.last_request_time = 0
        self.api_base = "https://api.audiochan.com"
        self.client = None

    def setup_playwright(self):
        """No-op for interface compatibility - Audiochan doesn't need Playwright."""
        pass

    def close_browser(self):
        """No-op for interface compatibility."""
        pass

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self.client is None:
            self.client = httpx.Client(
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
                follow_redirects=True,
                timeout=60.0,
            )
        return self.client

    def extract(self, url: str, target_path: dict) -> dict:
        """
        Extract content from Audiochan URL.

        Args:
            url: Audiochan URL to extract (e.g., https://audiochan.com/a/Ibm3SEa7bj7tLJizaA)
            target_path: Dict with 'dir' and 'basename' keys

        Returns:
            Platform-agnostic metadata dict
        """
        self.ensure_rate_limit()

        try:
            print(f"📥 Processing: {url}")

            target_dir = Path(target_path["dir"])
            basename = target_path["basename"]
            target_dir.mkdir(parents=True, exist_ok=True)

            # Check if already extracted (JSON exists)
            json_path = target_dir / f"{basename}.json"
            if json_path.exists():
                try:
                    cached = json.loads(json_path.read_text(encoding="utf-8"))
                    print(f"✅ Using cached extraction for: {url}")
                    return cached
                except json.JSONDecodeError:
                    print(f"⚠️  Cached JSON unreadable, re-extracting: {url}")

            # Extract slug from URL
            slug = self.extract_slug(url)
            if not slug:
                raise ValueError(f"Could not extract slug from URL: {url}")

            # Fetch metadata from API
            print(f"🔍 Fetching metadata for slug: {slug}")
            api_data = self.fetch_api_data(slug)

            # Extract relevant fields
            title = api_data.get("title", slug)
            audio_file = api_data.get("audioFile", {})
            audio_url = audio_file.get("url")
            duration = float(audio_file.get("duration", 0))
            mime_type = audio_file.get("mime_type", "audio/mpeg")
            filesize = int(audio_file.get("filesize", 0))

            if not audio_url:
                raise ValueError("No audio URL found in API response")

            # Determine format from mime type
            format_map = {
                "audio/mpeg": "mp3",
                "audio/mp4": "m4a",
                "audio/x-m4a": "m4a",
                "audio/aac": "aac",
                "audio/ogg": "ogg",
                "audio/flac": "flac",
                "audio/wav": "wav",
            }
            audio_format = format_map.get(mime_type, "mp3")

            # Extract performer from credits
            performer = None
            credits = api_data.get("credits", [])
            for credit in credits:
                if credit.get("role") == "voice":
                    user = credit.get("user", {})
                    performer = user.get("display_name") or user.get("username")
                    break

            # Extract tags
            tags = [tag.get("name") for tag in api_data.get("tags", []) if tag.get("name")]

            # Extract description from structured content
            description = self.extract_description(api_data.get("description"))

            # Download audio
            audio_file_path = target_dir / f"{basename}.{audio_format}"
            print(f"📥 Downloading audio ({filesize / 1024 / 1024:.1f} MB)...")
            self.download_file(audio_url, audio_file_path)

            # Calculate checksum
            checksum = self.calculate_checksum(audio_file_path)

            # Get actual file stats
            stats = audio_file_path.stat()

            # Build result in platform-agnostic schema
            result = {
                "audio": {
                    "sourceUrl": url,
                    "downloadUrl": audio_url.split("?")[0],  # Strip signed params for logging
                    "filePath": str(audio_file_path),
                    "format": audio_format,
                    "fileSize": stats.st_size,
                    "checksum": {"sha256": checksum},
                },
                "metadata": {
                    "title": title,
                    "author": performer,
                    "description": description,
                    "tags": tags,
                    "duration": duration,
                    "platform": {"name": "audiochan", "url": "https://audiochan.com"},
                },
                "platformData": {
                    "id": api_data.get("id"),
                    "slug": slug,
                    "type": api_data.get("type"),
                    "visibility": api_data.get("visibility"),
                    "createdAt": api_data.get("created_at"),
                    "extractedAt": datetime.now(UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                "backupFiles": {"metadata": str(json_path)},
            }

            # Save metadata (serves as completion marker)
            json_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            print(f"✅ Successfully extracted: {title}")
            if performer:
                print(f"   By: {performer}")
            print(f"   Duration: {int(duration // 60)}:{int(duration % 60):02d}")

            return result

        except Exception as error:
            print(f"❌ Failed to extract {url}: {error}")
            raise

    def extract_slug(self, url: str) -> str | None:
        """Extract slug from Audiochan URL."""
        # Handle various URL formats:
        # https://audiochan.com/a/Ibm3SEa7bj7tLJizaA
        # https://www.audiochan.com/a/Ibm3SEa7bj7tLJizaA
        match = re.search(r"audiochan\.com/a/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        return None

    def fetch_api_data(self, slug: str) -> dict:
        """Fetch audio metadata from Audiochan API."""
        client = self._get_client()
        response = client.get(f"{self.api_base}/audios/slug/{slug}")
        response.raise_for_status()
        return response.json()

    def extract_description(self, description_obj: dict | None) -> str:
        """Extract plain text description from Audiochan's structured content."""
        if not description_obj:
            return ""

        content = description_obj.get("content", [])
        paragraphs = []

        for block in content:
            if block.get("type") == "paragraph":
                block_content = block.get("content", [])
                text_parts = []
                for item in block_content:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                if text_parts:
                    paragraphs.append("".join(text_parts))

        return "\n\n".join(paragraphs)

    def download_file(self, url: str, file_path: Path, max_retries: int = 5):
        """Download file from URL with retries using streaming."""
        for attempt in range(1, max_retries + 1):
            try:
                print(f"   Download attempt {attempt}/{max_retries}...")

                with httpx.stream(
                    "GET",
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    },
                    follow_redirects=True,
                    timeout=120.0,
                ) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    with open(file_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = (downloaded / total) * 100
                                print(f"\r   Progress: {pct:.1f}%", end="", flush=True)

                print()  # New line after progress
                print("   ✅ Download completed")
                return

            except Exception as error:
                print(f"\n   ❌ Attempt {attempt}/{max_retries} failed: {error}")
                if attempt < max_retries:
                    wait_time = 5 * attempt
                    print(f"   ⏱️ Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        hash_sum = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash_sum.update(chunk)
        return hash_sum.hexdigest()

    def ensure_rate_limit(self):
        """Ensure rate limiting between requests."""
        now = time.time()
        time_since_last_request = now - self.last_request_time

        if time_since_last_request < self.request_delay:
            delay = self.request_delay - time_since_last_request
            print(f"⏳ Rate limiting: waiting {delay * 1000:.0f}ms...")
            time.sleep(delay)

        self.last_request_time = time.time()


def main():
    """CLI entry point for testing."""
    parser = argparse.ArgumentParser(
        description="Extract audio content from Audiochan URLs"
    )
    parser.add_argument("url", help="Audiochan URL to extract")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="data/audiochan",
        help="Output directory (default: data/audiochan)",
    )
    parser.add_argument(
        "--basename",
        "-b",
        help="Base filename (without extension). If not provided, uses slug from URL.",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Extract basename from URL if not provided
    basename = args.basename
    if not basename:
        match = re.search(r"audiochan\.com/a/([A-Za-z0-9_-]+)", args.url)
        if match:
            basename = match.group(1)
        else:
            print("❌ Could not extract basename from URL. Please provide --basename")
            return 1

    target_path = {"dir": args.output_dir, "basename": basename}

    extractor = AudiochanExtractor()

    try:
        result = extractor.extract(args.url, target_path)
        print("\n✅ Extraction complete!")
        print(f"📁 Files saved to: {target_path['dir']}")
        print(f"🎵 Audio: {result['audio']['filePath']}")
        print(f"📄 Metadata: {result['backupFiles']['metadata']}")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
