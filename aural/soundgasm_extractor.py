#!/usr/bin/env python3
"""
Soundgasm Extractor

Pure audio extractor - downloads directly to target path provided by caller.
Returns platform-agnostic schema.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


class SoundgasmExtractor:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.platform = "soundgasm"
        self.request_delay = config.get("request_delay", 2.0)
        self.last_request_time = 0
        self.browser = None
        self.page = None
        self.playwright = None
        self.context = None

    def setup_playwright(self, page=None, context=None):
        """Initialize Playwright browser or use provided page/context."""
        if page is not None:
            self.page = page
            self.context = context
            self._owns_browser = False
            print("🔗 Using shared Playwright browser")
            return

        try:
            print("🚀 Starting Playwright browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36"
            )
            self.page = self.context.new_page()
            self._owns_browser = True
            print("✅ Playwright browser initialized successfully")
        except Exception as error:
            print(f"❌ Failed to initialize Playwright: {error}")
            raise

    def close_browser(self):
        """Close Playwright browser if we own it."""
        if not getattr(self, "_owns_browser", True):
            self.page = None
            self.context = None
            return

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

    def extract(self, url: str, target_path: dict) -> dict:
        """
        Extract content from Soundgasm URL.

        Args:
            url: Soundgasm URL to extract
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

            # Navigate to page and extract metadata
            self.page.goto(url, wait_until="networkidle")

            metadata = self.extract_metadata(url)
            audio_url = self.extract_audio_url()

            # Download audio file
            audio_file_path = target_dir / f"{basename}.m4a"
            self.download_audio(audio_url, audio_file_path)

            # Calculate checksum
            checksum = self.calculate_checksum(audio_file_path)

            # Get file stats
            stats = audio_file_path.stat()

            # Save HTML backup
            html_path = target_dir / f"{basename}.html"
            self.save_html_backup(html_path)

            # Build result in platform-agnostic schema
            result = {
                "audio": {
                    "sourceUrl": url,
                    "downloadUrl": audio_url,
                    "filePath": str(audio_file_path),
                    "format": "m4a",
                    "fileSize": stats.st_size,
                    "checksum": {"sha256": checksum},
                },
                "metadata": {
                    "title": metadata["title"],
                    "author": metadata["author"],
                    "description": metadata.get("description", ""),
                    "tags": metadata.get("tags", []),
                    "duration": metadata.get("expectedDuration"),
                    "platform": {"name": "soundgasm", "url": "https://soundgasm.net"},
                },
                "platformData": {
                    "titleFromUrl": metadata["titleFromUrl"],
                    "pageTitle": metadata["pageTitle"],
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

            print(f"✅ Successfully extracted: {metadata['title']}")
            return result

        except Exception as error:
            print(f"❌ Failed to extract {url}: {error}")
            raise

    def extract_metadata(self, url: str) -> dict:
        """Extract metadata from Soundgasm page."""
        try:
            # Extract author and title from URL
            url_match = re.match(
                r"https?://(?:www\.)?soundgasm\.net/u/([A-Za-z0-9\-_]+)/([A-Za-z0-9\-_]+)",
                url,
            )
            if not url_match:
                raise ValueError("Invalid Soundgasm URL format")

            author = url_match.group(1)
            title_from_url = url_match.group(2)

            # Extract detailed title, description, and duration from page
            page_data = self.page.evaluate(
                """() => {
                const titleElement = document.querySelector(".jp-title");
                const descriptionElement = document.querySelector(".jp-description");

                // Try to get duration from the page
                let duration = null;
                const timeElements = document.querySelectorAll('[class*="time"], .jp-duration, .duration');
                for (const el of timeElements) {
                    const text = el.textContent.trim();
                    if (text.includes(':')) {
                        const match = text.match(/-?(\\d+):(\\d+)/);
                        if (match) {
                            const minutes = parseInt(match[1]);
                            const seconds = parseInt(match[2]);
                            duration = minutes * 60 + seconds;
                        }
                    }
                }

                return {
                    detailedTitle: titleElement ? titleElement.textContent.trim() : null,
                    description: descriptionElement ? descriptionElement.textContent.trim() : null,
                    duration: duration
                };
            }"""
            )

            # Get page title as fallback
            page_title = self.page.title()
            title = (
                page_data.get("detailedTitle") or page_title or title_from_url
            ).strip()

            # Extract tags from description
            description = page_data.get("description") or ""
            tags = self.parse_tags(description)

            return {
                "title": title,
                "author": author.strip(),
                "titleFromUrl": title_from_url,  # For filename
                "pageTitle": page_title,
                "description": description.strip(),
                "tags": tags,
                "expectedDuration": page_data.get("duration"),  # Duration in seconds
            }
        except Exception as error:
            print(f"Failed to extract metadata: {error}")
            raise

    def extract_audio_url(self) -> str:
        """Extract audio URL from Soundgasm page."""
        try:
            audio_url = self.page.evaluate(
                """() => {
                // First try to find the audio element
                const audioElement = document.querySelector("audio");
                if (audioElement && audioElement.src) {
                    return audioElement.src;
                }

                // Fallback to searching in HTML content
                const content = document.documentElement.innerHTML;
                const match = content.match(
                    /(https?:\\/\\/media\\.soundgasm\\.net\\/sounds\\/[A-Z0-9a-z]+\\.m4a)/i
                );
                return match ? match[1] : null;
            }"""
            )

            if not audio_url:
                raise ValueError("Could not find audio URL in Soundgasm page")

            return audio_url
        except Exception as error:
            print(f"Failed to extract audio URL: {error}")
            raise

    def download_audio(self, audio_url: str, audio_file_path: Path, max_retries: int = 5):
        """Download audio file from URL with retries using streaming."""
        for attempt in range(1, max_retries + 1):
            try:
                print(f"📥 Download attempt {attempt}/{max_retries}...")

                with httpx.stream(
                    "GET",
                    audio_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    follow_redirects=True,
                    timeout=60.0,
                ) as response:
                    response.raise_for_status()
                    with audio_file_path.open("wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)

                print(f"✅ Audio saved: {audio_file_path}")
                return

            except Exception as error:
                print(f"❌ Download attempt {attempt}/{max_retries} failed: {error}")
                if attempt < max_retries:
                    wait_time = 5 * attempt
                    print(f"⏱️ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    raise

    def save_html_backup(self, html_path: Path):
        """Save HTML content as backup."""
        html_content = self.page.content()
        html_path.write_text(html_content, encoding="utf-8")

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        file_buffer = file_path.read_bytes()
        hash_sum = hashlib.sha256()
        hash_sum.update(file_buffer)
        return hash_sum.hexdigest()

    def parse_tags(self, description: str) -> list[str]:
        """Parse tags from description (text in square brackets)."""
        tag_regex = re.compile(r"\[([^\]]+)\]")
        tags = tag_regex.findall(description)
        return tags

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename by removing invalid characters."""
        sanitized = re.sub(r'[<>:"/\\|?*]', "-", filename)
        sanitized = re.sub(r"\s+", "-", sanitized)
        return sanitized

    def ensure_rate_limit(self):
        """Ensure rate limiting between requests."""
        now = time.time()
        time_since_last_request = now - self.last_request_time

        if time_since_last_request < self.request_delay:
            delay = self.request_delay - time_since_last_request
            print(f"⏳ Rate limiting: waiting {delay * 1000:.0f}ms")
            time.sleep(delay)

        self.last_request_time = time.time()


def main():
    """CLI entry point for testing."""
    parser = argparse.ArgumentParser(
        description="Extract audio content from Soundgasm URLs"
    )
    parser.add_argument("url", help="Soundgasm URL to extract")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="data/soundgasm",
        help="Output directory (default: data/soundgasm)",
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
        url_match = re.match(
            r"https?://(?:www\.)?soundgasm\.net/u/([A-Za-z0-9\-_]+)/([A-Za-z0-9\-_]+)",
            args.url,
        )
        if url_match:
            basename = url_match.group(2)
        else:
            print("❌ Could not extract basename from URL. Please provide --basename")
            return 1

    target_path = {"dir": args.output_dir, "basename": basename}

    extractor = SoundgasmExtractor()

    try:
        extractor.setup_playwright()
        result = extractor.extract(args.url, target_path)
        print("\n✅ Extraction complete!")
        print(f"📁 Files saved to: {target_path['dir']}")
        print(f"🎵 Audio: {result['audio']['filePath']}")
        print(f"📄 Metadata: {result['backupFiles']['metadata']}")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    finally:
        extractor.close_browser()


if __name__ == "__main__":
    sys.exit(main())
