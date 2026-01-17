#!/usr/bin/env python3
"""
ScriptBin.works Data Extractor

This script extracts adult audio scripts from scriptbin.works using Playwright.
It handles the terms agreement page and extracts both metadata and script content.

Requirements:
1. Install dependencies: uv sync
2. Install browser: uv run playwright install chromium
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import config as aural_config
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sys


class ScriptBinExtractor:
    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir).resolve() if output_dir else aural_config.SCRIPTBIN_DIR
        self.request_delay = 2.0  # Seconds between requests
        self.last_request_time = 0.0

        # Playwright setup
        self.browser = None
        self.page = None
        self.playwright = None
        self.context = None
        self._owns_browser = False  # Track if we own the browser instance

    def setup_playwright(self, headless: bool = True, page=None, context=None):
        """Initialize Playwright browser or use provided page/context."""
        if page is not None:
            # Use externally provided page (shared browser)
            self.page = page
            self.context = context
            self._owns_browser = False
            print("Using shared Playwright browser")
            return

        try:
            print("Starting Playwright browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=headless)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
            self._owns_browser = True
            print("Playwright browser initialized successfully")
        except Exception as error:
            print(f"Failed to initialize Playwright: {error}")
            print('Run "uv run playwright install chromium" to install browser')
            raise

    def close_browser(self):
        """Close Playwright browser if we own it."""
        if not self._owns_browser:
            # Don't close shared browser
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
        print("Playwright browser closed")

    def rate_limit(self):
        """Ensure rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_delay:
            sleep_time = self.request_delay - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def handle_terms_agreement(self, url: str) -> str:
        """Handle terms agreement page if present."""
        self.rate_limit()

        try:
            self.page.goto(url, wait_until="networkidle")

            # Check if we're on the terms agreement page
            if "agree-terms" in self.page.url:
                print("Terms agreement page detected, clicking Agree...")

                try:
                    # Wait for and click the Agree button
                    agree_button = self.page.wait_for_selector(
                        'input[name="agree"][value="Agree"]', timeout=5000
                    )
                    agree_button.click()

                    # Wait for navigation away from terms page
                    self.page.wait_for_function(
                        "() => !window.location.href.includes('agree-terms')",
                        timeout=10000,
                    )

                    print(
                        f"Successfully agreed to terms, redirected to: {self.page.url}"
                    )
                except Exception:
                    print("Could not find Agree button, continuing anyway...")

            # Wait for script content to load
            try:
                self.page.wait_for_selector(
                    '.script-text-real, h3, p:has-text("words")', timeout=10000
                )
                self.page.wait_for_timeout(2000)  # Additional wait for dynamic content
                print("Script content loaded successfully")
            except Exception:
                print("Script content may not have fully loaded, continuing...")

            return self.page.url

        except Exception as error:
            print(f"Error handling page load: {error}")
            return url

    def extract_script_metadata(self, soup: BeautifulSoup, url: str) -> dict:
        """Extract metadata from script page."""
        metadata = {
            "url": url,
            "extracted_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }

        # Extract username from URL first (more reliable)
        username_match = re.search(r"/u/([^/]+)", url)
        if username_match:
            metadata["username"] = username_match.group(1)

        # Extract title from the specific span structure
        title_and_tags = soup.select_one("span.title-and-tags span")
        if title_and_tags:
            metadata["title"] = title_and_tags.get_text(strip=True)

        # Extract tags from the script-audience span
        tags_element = soup.select_one("span.script-audience")
        if tags_element:
            metadata["tags"] = tags_element.get_text(strip=True)

        # Extract author from the breadcrumb (fallback if username not in URL)
        author_link = soup.select_one('a[href*="/u/"]')
        if author_link:
            author_text = author_link.get_text().replace("\u2039 ", "").strip()
            metadata["author"] = author_text
            href = author_link.get("href", "")
            if href:
                from urllib.parse import urljoin

                metadata["author_url"] = urljoin(url, href)

            # Use author from link if username wasn't extracted from URL
            if "username" not in metadata:
                metadata["username"] = author_text

        # Extract performers/listeners info - handle <br> tags properly
        for p_tag in soup.find_all("p"):
            html_content = str(p_tag)
            if "Performers:" in html_content and "Listeners:" in html_content:
                # Split by <br> tag to handle the line break
                parts = re.split(r"<br\s*/?>", html_content, flags=re.IGNORECASE)

                for part in parts:
                    # Clean the part and get text content
                    clean_part = re.sub(r"<[^>]+>", "", part).strip()

                    if clean_part.startswith("Performers:"):
                        metadata["performers"] = clean_part.replace(
                            "Performers:", ""
                        ).strip()
                    elif clean_part.startswith("Listeners:"):
                        metadata["listeners"] = clean_part.replace(
                            "Listeners:", ""
                        ).strip()

        # Extract word count and character count
        for p_tag in soup.find_all("p"):
            text = p_tag.get_text()
            if "words" in text and "characters" in text:
                word_match = re.search(r"(\d+)\s+words", text)
                char_match = re.search(r"(\d+)\s+characters", text)

                if word_match:
                    metadata["word_count"] = int(word_match.group(1))
                if char_match:
                    metadata["character_count"] = int(char_match.group(1))
                break

        # Extract short link
        for p_tag in soup.find_all("p"):
            text = p_tag.get_text()
            if "Short link:" in text:
                short_link_match = re.search(r"https://scriptbin\.works/s/\w+", text)
                if short_link_match:
                    metadata["short_link"] = short_link_match.group(0)
                break

        # Try to extract the script ID from URL
        script_id_match = re.search(r"/([^/]+)$", url)
        if script_id_match:
            metadata["script_id"] = script_id_match.group(1)

        return metadata

    def extract_script_content(self, soup: BeautifulSoup) -> list[str]:
        """Extract script content from page."""
        script_lines = []

        # Target the specific script container based on the HTML structure
        script_container = soup.select_one(".script-text-real")

        if script_container:
            print("Found script container, extracting content...")

            # Extract from .line-raw divs within the script container
            for element in script_container.select(".line-raw"):
                text = element.get_text(strip=True)

                # Skip blank lines (marked with &nbsp; or very short)
                if (
                    len(text) < 2
                    or text == "\u00a0"
                    or element.get("data-isblank") == "yes"
                ):
                    continue

                script_lines.append(text)

            # If line-raw approach didn't work, try direct text extraction
            if not script_lines:
                all_text = script_container.get_text(strip=True)
                if all_text:
                    # Split by common line breaks and clean up
                    lines = [
                        line.strip() for line in all_text.split("\n") if line.strip()
                    ]
                    lines = [line for line in lines if len(line) > 2]
                    script_lines.extend(lines)

        # Fallback: look for other potential script containers
        if not script_lines:
            print("No content in script-text-real, trying fallback methods...")

            # Try pre elements that might contain script text
            for pre_tag in soup.find_all("pre"):
                text = pre_tag.get_text(strip=True)

                if len(text) > 50:  # Substantial content
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    lines = [line for line in lines if len(line) > 2]
                    if len(lines) > 5:  # Looks like script content
                        script_lines.extend(lines)

            # Try main content area with paragraphs (scriptbin new layout)
            if not script_lines:
                main_tag = soup.find("main")
                if main_tag:
                    # Find all paragraphs in main, skip metadata at the start
                    paragraphs = main_tag.find_all("p")
                    in_script_content = False
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        # Skip metadata paragraphs
                        if text.startswith("Performers:") or text.startswith("Listeners:"):
                            continue
                        if text.startswith("Short link:") or "scriptbin.works" in text:
                            continue
                        if "words" in text and "characters" in text:
                            in_script_content = True  # Script content starts after this
                            continue
                        if in_script_content and len(text) > 2:
                            script_lines.append(text)

            # Last resort: look for divs with substantial dialogue-like content
            if not script_lines:
                skip_patterns = [
                    "performers:",
                    "listeners:",
                    "words",
                    "characters",
                    "short link:",
                    "show line numbers",
                    "font size:",
                    "additional width:",
                    "scriptbin",
                    "copyright",
                    "log in with reddit",
                    "agree below",
                    "legal age",
                    "fictional depictions",
                    "consensually",
                    "generated in",
                    "site:",
                    "individual works",
                    "\u2039",  # Left single angle quote
                    "prompter",
                    "script fill",
                ]

                for div_tag in soup.find_all("div"):
                    text = div_tag.get_text(strip=True)

                    # Skip common metadata patterns
                    lower_text = text.lower()
                    is_metadata = any(
                        pattern in lower_text for pattern in skip_patterns
                    )

                    if not is_metadata and 20 < len(text) < 500:
                        # Check if this looks like dialogue or stage direction
                        has_dialogue_markers = (
                            any(
                                marker in text for marker in ["(", ":", "<", "[", "..."]
                            )
                            or text[0].isupper()
                        )

                        if has_dialogue_markers and text not in script_lines:
                            script_lines.append(text)

        print(f"Extracted {len(script_lines)} script lines")
        return script_lines[:500]  # Reasonable limit for script length

    def get_script_data(self, url: str) -> dict | None:
        """Get script data from URL."""
        try:
            print(f"Fetching script from: {url}")

            # Handle terms agreement if needed
            final_url = self.handle_terms_agreement(url)

            # Get page source after JavaScript execution
            page_source = self.page.content()
            soup = BeautifulSoup(page_source, "html.parser")

            # Extract metadata
            metadata = self.extract_script_metadata(soup, final_url)

            # Extract script content
            script_content = self.extract_script_content(soup)

            if not script_content:
                print("No script content found")
                return None

            # Build content preview
            content_text = " ".join(script_content[:3])
            content_preview = content_text[:200]
            if len(content_text) > 200:
                content_preview += "..."

            script_data = {
                **metadata,
                "script_content": script_content,
                "content_preview": content_preview,
                "html_backup_saved": True,
                "html_content": page_source,  # Include HTML for caller to save
            }

            # Save HTML backup to default location
            self.save_html_backup(script_data, page_source)

            print(
                f"Successfully extracted script: {metadata.get('title', 'Unknown Title')}"
            )
            print(
                f"Content: {len(script_content)} lines, {metadata.get('word_count', 'unknown')} words"
            )

            return script_data

        except Exception as error:
            print(f"Error extracting script from {url}: {error}")
            return None

    def ensure_output_dir(self):
        """Ensure output directory exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_individual_script(self, script_data: dict):
        """Save individual script to JSON file."""
        # Use username first, then author, then fallback
        username = script_data.get("username") or script_data.get("author") or "unknown"
        clean_username = username.replace(" ", "_")
        script_id = script_data.get("script_id", "unknown")

        # Create username directory
        user_dir = self.output_dir / clean_username
        user_dir.mkdir(parents=True, exist_ok=True)

        # Save script as JSON (exclude html_content from saved file)
        save_data = {k: v for k, v in script_data.items() if k != "html_content"}
        filename = f"{script_id}.json"
        filepath = user_dir / filename

        try:
            filepath.write_text(
                json.dumps(save_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Saved individual script to {filepath}")
        except Exception as error:
            print(f"Error saving individual script {script_id}: {error}")

    def save_html_backup(self, script_data: dict, page_source: str):
        """Save HTML backup of script page."""
        # Use username first, then author, then fallback
        username = script_data.get("username") or script_data.get("author") or "unknown"
        clean_username = username.replace(" ", "_")
        script_id = script_data.get("script_id", "unknown")

        # Create username directory
        user_dir = self.output_dir / clean_username
        user_dir.mkdir(parents=True, exist_ok=True)

        # Save HTML backup
        html_filename = f"{script_id}.html"
        html_filepath = user_dir / html_filename

        try:
            html_filepath.write_text(page_source, encoding="utf-8")
            print(f"Saved HTML backup to {html_filepath}")
        except Exception as error:
            print(f"Error saving HTML backup {script_id}: {error}")

    def save_to_json(self, data: list, filename: str):
        """Save data to JSON file."""
        if not data:
            print("No data to save")
            return

        filepath = self.output_dir / filename

        try:
            # Exclude html_content from batch saves
            clean_data = []
            for item in data:
                clean_item = {k: v for k, v in item.items() if k != "html_content"}
                clean_data.append(clean_item)

            filepath.write_text(
                json.dumps(clean_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Saved {len(data)} entries to {filepath}")
        except Exception as error:
            print(f"Error saving to JSON: {error}")

    def save_to_csv(self, data: list, filename: str):
        """Save data to CSV file."""
        if not data:
            print("No data to save")
            return

        filepath = self.output_dir / filename

        try:
            import csv

            # Flatten script_content for CSV
            flattened_data = []
            for entry in data:
                flattened = {k: v for k, v in entry.items() if k != "html_content"}
                if "script_content" in flattened:
                    flattened["script_content"] = "\n".join(flattened["script_content"])
                flattened_data.append(flattened)

            # Get all columns
            all_columns: set[str] = set()
            for entry in flattened_data:
                all_columns.update(entry.keys())

            columns = sorted(all_columns)

            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=columns)
                writer.writeheader()

                for entry in flattened_data:
                    row = {col: entry.get(col, "") for col in columns}
                    writer.writerow(row)

            print(f"Saved {len(data)} entries to {filepath}")
        except Exception as error:
            print(f"Error saving to CSV: {error}")

    def extract_from_urls(
        self, urls: list[str], max_scripts: int | None = None
    ) -> list:
        """Extract scripts from multiple URLs."""
        print(f"Starting ScriptBin extraction for {len(urls)} URLs...")

        extracted_data = []
        failed_urls = []

        # Apply limit if specified
        urls_to_process = urls[:max_scripts] if max_scripts else urls

        if max_scripts and len(urls) > max_scripts:
            print(
                f"Processing {len(urls_to_process)} URLs (limited by max-scripts={max_scripts})"
            )

        for i, url in enumerate(urls_to_process):
            print(f"Processing script {i + 1}/{len(urls_to_process)}: {url}")

            script_data = self.get_script_data(url)
            if script_data:
                extracted_data.append(script_data)
                self.save_individual_script(script_data)
            else:
                failed_urls.append(url)

        print("\nExtraction Summary:")
        print(f"Successfully processed: {len(extracted_data)}")
        print(f"Failed: {len(failed_urls)}")

        # Save failed URLs if any
        if failed_urls:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            self.save_to_json(failed_urls, f"failed_urls_{timestamp}.json")

        return extracted_data


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Extract scripts from scriptbin.works")
    parser.add_argument("urls", nargs="*", help="ScriptBin.works URLs to extract")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help=f"Output directory (default: {aural_config.SCRIPTBIN_DIR})",
    )
    parser.add_argument(
        "--max-scripts",
        "-m",
        type=int,
        help="Maximum number of scripts to process",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=int,
        default=2000,
        help="Delay between requests in milliseconds (default: 2000)",
    )
    parser.add_argument(
        "--url-file",
        "-f",
        help="File containing URLs (one per line)",
    )

    args = parser.parse_args()

    urls = list(args.urls)

    try:
        # Get URLs from file if specified
        if args.url_file:
            url_file = Path(args.url_file).resolve()
            try:
                content = url_file.read_text(encoding="utf-8")
                file_urls = [
                    line.strip()
                    for line in content.split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
                urls.extend(file_urls)
                print(f"Loaded {len(file_urls)} URLs from {args.url_file}")
            except FileNotFoundError:
                print(f"URL file not found: {args.url_file}")
                return 1

        if not urls:
            print("No URLs provided")
            parser.print_help()
            return 1

        # Initialize extractor
        extractor = ScriptBinExtractor(args.output)
        extractor.request_delay = args.delay / 1000.0  # Convert to seconds

        extractor.ensure_output_dir()
        extractor.setup_playwright()

        # Extract scripts
        extracted_data = extractor.extract_from_urls(urls, args.max_scripts)

        print("\nExtraction complete!")
        print(f"Results saved to: {extractor.output_dir}")
        print(f"Processed {len(extracted_data)} scripts successfully")

        # Close browser
        extractor.close_browser()
        return 0

    except KeyboardInterrupt:
        print("\nExtraction interrupted by user")
        return 0
    except Exception as error:
        print(f"\nError: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
