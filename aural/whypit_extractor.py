#!/usr/bin/env python3
"""
Whyp.it Extractor

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


class WhypitExtractor:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.platform = "whypit"
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
        print("🔧 Playwright browser closed")

    def extract(self, url: str, target_path: dict) -> dict:
        """
        Extract content from Whyp.it URL.

        Args:
            url: Whyp.it URL to extract
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

            # Navigate to page (use domcontentloaded instead of networkidle to avoid timeout)
            self.page.goto(url, wait_until="domcontentloaded")
            # Wait a bit for dynamic content
            time.sleep(2)

            # Extract metadata from the page
            page_data = self.extract_page_data()

            # Extract track info from URL (strip query params first)
            clean_url = url.split("?")[0]
            url_match = re.search(r"/tracks/(\d+)/(.+)$", clean_url)
            if not url_match:
                raise ValueError("Invalid Whyp.it URL format")

            track_id = url_match.group(1)
            title_slug = url_match.group(2)
            performer = page_data.get("performer") or "unknown"
            title = page_data.get("title") or title_slug

            # Capture audio URL
            audio_url = self.capture_audio_url()

            # Determine audio format from URL
            clean_audio_url = audio_url.split("?")[0]
            if clean_audio_url.endswith(".flac"):
                audio_format = "flac"
            else:
                audio_format = "mp3"

            # Download audio
            audio_file_path = target_dir / f"{basename}.{audio_format}"
            self.download_file(audio_url, audio_file_path)

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
                    "downloadUrl": clean_audio_url,
                    "filePath": str(audio_file_path),
                    "format": audio_format,
                    "fileSize": stats.st_size,
                    "checksum": {"sha256": checksum},
                },
                "metadata": {
                    "title": title,
                    "author": performer,
                    "description": page_data.get("description") or "",
                    "tags": page_data.get("tags") or [],
                    "duration": None,
                    "platform": {"name": "whypit", "url": "https://whyp.it"},
                },
                "platformData": {
                    "trackId": track_id,
                    "titleSlug": title_slug,
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

            print(f"✅ Successfully extracted: {title} by {performer}")
            return result

        except Exception as error:
            print(f"❌ Failed to extract {url}: {error}")
            raise

    def extract_page_data(self) -> dict:
        """Extract metadata from Whyp.it page."""
        return self.page.evaluate(
            """() => {
            // Extract title
            const titleElement = document.querySelector("h1");
            const title = titleElement ? titleElement.textContent.trim() : null;

            // Extract performer from uploader link
            // The uploader link contains "tracks" text (e.g., "598 tracks")
            let performer = null;
            const userLinks = document.querySelectorAll('a[href*="/users/"]');
            for (const link of userLinks) {
                if (link.textContent.includes('tracks')) {
                    const href = link.getAttribute('href');
                    // Format: /users/4994/lurkydip
                    const match = href.match(/\\/users\\/\\d+\\/([^/?]+)/);
                    if (match) {
                        performer = match[1];
                    }
                    break;
                }
            }

            // Extract description and tags from meta description
            const metaDescriptionElement = document.querySelector('meta[name="description"]');
            let description = null;
            let tags = [];

            if (metaDescriptionElement) {
                description = metaDescriptionElement.getAttribute('content');
                if (description) {
                    description = description.trim();

                    // Extract tags from [tag] format
                    const tagMatches = description.match(/\\[([^\\]]+?)\\]/g);
                    if (tagMatches) {
                        tags = tagMatches
                            .map(tag => tag.replace(/[\\[\\]]/g, "").trim())
                            .filter(tag => tag.length > 0);
                    }
                }
            }

            return {
                title: title,
                performer: performer,
                description: description,
                tags: tags
            };
        }"""
        )

    def capture_audio_url(self) -> str:
        """Capture audio URL by clicking play button and intercepting network requests."""
        print("🎯 Looking for play button...")

        def is_audio_response(r):
            """Check if response is an audio file (mp3 or flac)."""
            if "cdn.whyp.it" not in r.url:
                return False
            url_path = r.url.split("?")[0]
            return url_path.endswith((".mp3", ".flac"))

        # Use expect_response to wait for audio URL (mp3 or flac) while clicking play
        with self.page.expect_response(is_audio_response, timeout=30000) as response_info:
            play_button_clicked = self.page.evaluate(
                """() => {
                const buttons = document.querySelectorAll('button');
                for (const button of buttons) {
                    const hasPlayIcon = button.innerHTML.includes('play') ||
                                       button.querySelector('svg path[d*="8,5.14V19.14L19,12.14L8,5.14Z"]') ||
                                       button.querySelector('path[d*="play"]');

                    if (hasPlayIcon || button.getAttribute('aria-label')?.includes('play')) {
                        button.click();
                        return true;
                    }
                }

                const audioPlayerButtons = document.querySelectorAll('button[class*="relative"], button[class*="cursor-pointer"]');
                if (audioPlayerButtons.length > 0) {
                    audioPlayerButtons[0].click();
                    return true;
                }

                return false;
            }"""
            )

            if not play_button_clicked:
                raise ValueError("Could not find or click play button")

            print("▶️ Play button clicked, waiting for audio URL...")

        response = response_info.value
        audio_url = response.url
        # Strip query parameters for logging (keep full URL for download)
        clean_url = audio_url.split("?")[0]
        print(f"🎵 Found audio URL: {clean_url}")

        return audio_url

    def download_file(self, url: str, file_path: Path, max_retries: int = 5):
        """Download file from URL with retries using streaming."""
        for attempt in range(1, max_retries + 1):
            try:
                print(f"📥 Download attempt {attempt}/{max_retries}...")

                with httpx.stream(
                    "GET",
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    follow_redirects=True,
                    timeout=60.0,
                ) as response:
                    response.raise_for_status()
                    with file_path.open("wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)

                print("✅ Audio download completed successfully")
                return True

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

    def sanitize_filename(self, name: str) -> str:
        """Sanitize filename by removing invalid characters."""
        return re.sub(r"[^A-Za-z0-9 \-_]", "", name)

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
        description="Extract audio content from Whyp.it URLs"
    )
    parser.add_argument("url", help="Whyp.it URL to extract")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="data/whypit",
        help="Output directory (default: data/whypit)",
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
        # Strip query parameters before extracting basename
        clean_url = args.url.split("?")[0]
        url_match = re.search(r"/tracks/\d+/(.+)$", clean_url)
        if url_match:
            basename = url_match.group(1)
        else:
            print("❌ Could not extract basename from URL. Please provide --basename")
            return 1

    target_path = {"dir": args.output_dir, "basename": basename}

    extractor = WhypitExtractor()

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
