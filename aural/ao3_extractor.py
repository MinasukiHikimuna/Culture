#!/usr/bin/env python3
"""
Archive of Our Own (AO3) Data Extractor

This script extracts works from archiveofourown.org using Playwright.
It handles the adult content warning and TOS agreement, then extracts
both metadata and work content.

Requirements:
1. Install dependencies: uv sync
2. Install browser: uv run playwright install chromium
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone, UTC
from pathlib import Path

import config as aural_config
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sys


class AO3Extractor:
    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir).resolve() if output_dir else aural_config.AO3_DIR
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

    def handle_adult_content_and_tos(self, url: str) -> str:
        """Handle adult content warning and TOS agreement if present."""
        self.rate_limit()

        try:
            # Add view_adult=true to bypass adult content warning
            if "view_adult=true" not in url:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}view_adult=true"

            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Check for TOS prompt and accept it if present
            try:
                tos_checkbox = self.page.wait_for_selector(
                    "#tos_agree", timeout=3000, state="visible"
                )
                if tos_checkbox:
                    print("TOS agreement detected, accepting...")
                    tos_checkbox.click()

                    # Also check the data processing checkbox
                    data_checkbox = self.page.wait_for_selector(
                        "#data_processing_agree", timeout=2000
                    )
                    if data_checkbox:
                        data_checkbox.click()

                    # Click the accept button
                    accept_button = self.page.wait_for_selector(
                        "#accept_tos", timeout=2000
                    )
                    if accept_button:
                        accept_button.click()
                        self.page.wait_for_timeout(1000)
                        print("TOS accepted successfully")
            except Exception:
                # TOS prompt not present or already accepted
                pass

            # Wait for work content to load
            try:
                self.page.wait_for_selector(
                    ".userstuff, #workskin, .work.meta", timeout=10000
                )
                self.page.wait_for_timeout(1000)  # Additional wait for dynamic content
                print("Work content loaded successfully")
            except Exception:
                print("Work content may not have fully loaded, continuing...")

            return self.page.url

        except Exception as error:
            print(f"Error handling page load: {error}")
            return url

    def extract_work_metadata(self, soup: BeautifulSoup, url: str) -> dict:
        """Extract metadata from AO3 work page."""
        metadata = {
            "url": url,
            "extracted_at": datetime.now(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
        }

        # Extract work ID from URL
        work_id_match = re.search(r"/works/(\d+)", url)
        if work_id_match:
            metadata["work_id"] = work_id_match.group(1)

        # Extract title
        title_elem = soup.select_one(".preface h2.title")
        if title_elem:
            metadata["title"] = title_elem.get_text(strip=True)

        # Extract author(s)
        author_links = soup.select(".preface h3.byline a[rel='author']")
        if author_links:
            authors = [a.get_text(strip=True) for a in author_links]
            metadata["authors"] = authors
            metadata["author"] = authors[0] if len(authors) == 1 else authors
            # Build author URLs and extract usernames
            author_urls = []
            usernames = []
            for a in author_links:
                href = a.get("href", "")
                if href:
                    from urllib.parse import urljoin

                    author_urls.append(urljoin(url, href))
                    # Extract username from URL pattern /users/{username}
                    username_match = re.search(r"/users/([^/]+)", href)
                    if username_match:
                        usernames.append(username_match.group(1))
            metadata["author_urls"] = author_urls
            if usernames:
                metadata["usernames"] = usernames
                metadata["username"] = usernames[0]  # Primary username for compatibility

        # Extract rating
        rating_elem = soup.select_one("dd.rating a.tag")
        if rating_elem:
            metadata["rating"] = rating_elem.get_text(strip=True)

        # Extract archive warnings
        warning_elems = soup.select("dd.warning a.tag")
        if warning_elems:
            metadata["archive_warnings"] = [
                w.get_text(strip=True) for w in warning_elems
            ]

        # Extract categories
        category_elems = soup.select("dd.category a.tag")
        if category_elems:
            metadata["categories"] = [c.get_text(strip=True) for c in category_elems]

        # Extract fandoms
        fandom_elems = soup.select("dd.fandom a.tag")
        if fandom_elems:
            metadata["fandoms"] = [f.get_text(strip=True) for f in fandom_elems]

        # Extract relationships
        relationship_elems = soup.select("dd.relationship a.tag")
        if relationship_elems:
            metadata["relationships"] = [
                r.get_text(strip=True) for r in relationship_elems
            ]

        # Extract characters
        character_elems = soup.select("dd.character a.tag")
        if character_elems:
            metadata["characters"] = [c.get_text(strip=True) for c in character_elems]

        # Extract additional/freeform tags
        freeform_elems = soup.select("dd.freeform a.tag")
        if freeform_elems:
            metadata["additional_tags"] = [
                t.get_text(strip=True) for t in freeform_elems
            ]

        # Extract language
        language_elem = soup.select_one("dd.language")
        if language_elem:
            metadata["language"] = language_elem.get_text(strip=True)

        # Extract stats
        stats_dl = soup.select_one("dl.stats")
        if stats_dl:
            # Published date
            published_elem = stats_dl.select_one("dd.published")
            if published_elem:
                metadata["published"] = published_elem.get_text(strip=True)

            # Updated date (for multi-chapter works)
            updated_elem = stats_dl.select_one("dd.status")
            if updated_elem:
                metadata["updated"] = updated_elem.get_text(strip=True)

            # Word count
            words_elem = stats_dl.select_one("dd.words")
            if words_elem:
                word_text = words_elem.get_text(strip=True).replace(",", "")
                try:
                    metadata["word_count"] = int(word_text)
                except ValueError:
                    metadata["word_count_text"] = words_elem.get_text(strip=True)

            # Chapter count
            chapters_elem = stats_dl.select_one("dd.chapters")
            if chapters_elem:
                chapters_text = chapters_elem.get_text(strip=True)
                metadata["chapters"] = chapters_text
                # Parse current/total chapters
                chapter_match = re.match(r"(\d+)/(\d+|\?)", chapters_text)
                if chapter_match:
                    metadata["chapters_current"] = int(chapter_match.group(1))
                    total = chapter_match.group(2)
                    metadata["chapters_total"] = None if total == "?" else int(total)

            # Kudos
            kudos_elem = stats_dl.select_one("dd.kudos")
            if kudos_elem:
                kudos_text = kudos_elem.get_text(strip=True).replace(",", "")
                try:
                    metadata["kudos"] = int(kudos_text)
                except ValueError:
                    pass

            # Bookmarks
            bookmarks_elem = stats_dl.select_one("dd.bookmarks a")
            if bookmarks_elem:
                bookmarks_text = bookmarks_elem.get_text(strip=True).replace(",", "")
                try:
                    metadata["bookmarks"] = int(bookmarks_text)
                except ValueError:
                    pass

            # Hits
            hits_elem = stats_dl.select_one("dd.hits")
            if hits_elem:
                hits_text = hits_elem.get_text(strip=True).replace(",", "")
                try:
                    metadata["hits"] = int(hits_text)
                except ValueError:
                    pass

            # Comments
            comments_elem = stats_dl.select_one("dd.comments")
            if comments_elem:
                comments_text = comments_elem.get_text(strip=True).replace(",", "")
                try:
                    metadata["comments"] = int(comments_text)
                except ValueError:
                    pass

        # Extract summary
        summary_elem = soup.select_one(".summary .userstuff")
        if summary_elem:
            metadata["summary"] = summary_elem.get_text(strip=True)

        # Extract notes (beginning notes)
        notes_elem = soup.select_one(".preface .notes .userstuff")
        if notes_elem:
            metadata["notes"] = notes_elem.get_text(strip=True)

        # Extract end notes
        end_notes_elem = soup.select_one("#work_endnotes .userstuff")
        if end_notes_elem:
            metadata["end_notes"] = end_notes_elem.get_text(strip=True)

        # Check if work is part of a series
        series_elems = soup.select(".series span.position a")
        if series_elems:
            series_info = []
            for s in series_elems:
                series_info.append(
                    {"name": s.get_text(strip=True), "url": s.get("href", "")}
                )
            metadata["series"] = series_info

        return metadata

    def extract_work_content(self, soup: BeautifulSoup) -> list[str]:
        """Extract work content from page."""
        content_lines = []

        # Target the userstuff div within chapters
        work_content = soup.select_one("#chapters .userstuff")

        if work_content:
            print("Found work content, extracting...")

            # Get all paragraphs
            for p_elem in work_content.find_all("p"):
                text = p_elem.get_text(strip=True)
                if text:
                    content_lines.append(text)

            # If no paragraphs, try getting all text
            if not content_lines:
                all_text = work_content.get_text(separator="\n", strip=True)
                if all_text:
                    lines = [
                        line.strip() for line in all_text.split("\n") if line.strip()
                    ]
                    content_lines.extend(lines)

        # Fallback: look for any userstuff content
        if not content_lines:
            print("No content in #chapters .userstuff, trying fallback methods...")

            all_userstuff = soup.select("#workskin .userstuff")
            for userstuff in all_userstuff:
                # Skip summary and notes
                parent_classes = " ".join(userstuff.parent.get("class", []))
                if "summary" in parent_classes or "notes" in parent_classes:
                    continue

                for p_elem in userstuff.find_all("p"):
                    text = p_elem.get_text(strip=True)
                    if text and text not in content_lines:
                        content_lines.append(text)

        print(f"Extracted {len(content_lines)} content lines")
        return content_lines

    def get_work_data(self, url: str) -> dict | None:
        """Get work data from URL."""
        try:
            print(f"Fetching work from: {url}")

            # Handle adult content warning and TOS if needed
            final_url = self.handle_adult_content_and_tos(url)

            # Get page source after JavaScript execution
            page_source = self.page.content()
            soup = BeautifulSoup(page_source, "html.parser")

            # Extract metadata
            metadata = self.extract_work_metadata(soup, final_url)

            # Extract work content
            work_content = self.extract_work_content(soup)

            if not work_content:
                print("No work content found")
                return None

            # Build content preview
            content_text = " ".join(work_content[:3])
            content_preview = content_text[:200]
            if len(content_text) > 200:
                content_preview += "..."

            work_data = {
                **metadata,
                "script_content": work_content,  # Keep same key as scriptbin for compatibility
                "content_preview": content_preview,
                "html_backup_saved": True,
                "html_content": page_source,  # Include HTML for caller to save
            }

            # Save HTML backup to default location
            self.save_html_backup(work_data, page_source)

            print(
                f"Successfully extracted work: {metadata.get('title', 'Unknown Title')}"
            )
            print(
                f"Content: {len(work_content)} lines, {metadata.get('word_count', 'unknown')} words"
            )

            return work_data

        except Exception as error:
            print(f"Error extracting work from {url}: {error}")
            return None

    def ensure_output_dir(self):
        """Ensure output directory exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_individual_work(self, work_data: dict):
        """Save individual work to JSON file."""
        # Use first author or fallback
        authors = work_data.get("authors", [])
        author = authors[0] if authors else work_data.get("author", "unknown")
        if isinstance(author, list):
            author = author[0] if author else "unknown"
        clean_author = author.replace(" ", "_").replace("/", "_")
        work_id = work_data.get("work_id", "unknown")

        # Create author directory
        author_dir = self.output_dir / clean_author
        author_dir.mkdir(parents=True, exist_ok=True)

        # Save work as JSON (exclude html_content from saved file)
        save_data = {k: v for k, v in work_data.items() if k != "html_content"}
        filename = f"{work_id}.json"
        filepath = author_dir / filename

        try:
            filepath.write_text(
                json.dumps(save_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Saved individual work to {filepath}")
        except Exception as error:
            print(f"Error saving individual work {work_id}: {error}")

    def save_html_backup(self, work_data: dict, page_source: str):
        """Save HTML backup of work page."""
        # Use first author or fallback
        authors = work_data.get("authors", [])
        author = authors[0] if authors else work_data.get("author", "unknown")
        if isinstance(author, list):
            author = author[0] if author else "unknown"
        clean_author = author.replace(" ", "_").replace("/", "_")
        work_id = work_data.get("work_id", "unknown")

        # Create author directory
        author_dir = self.output_dir / clean_author
        author_dir.mkdir(parents=True, exist_ok=True)

        # Save HTML backup
        html_filename = f"{work_id}.html"
        html_filepath = author_dir / html_filename

        try:
            html_filepath.write_text(page_source, encoding="utf-8")
            print(f"Saved HTML backup to {html_filepath}")
        except Exception as error:
            print(f"Error saving HTML backup {work_id}: {error}")

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

            # Flatten content and list fields for CSV
            flattened_data = []
            for entry in data:
                flattened = {k: v for k, v in entry.items() if k != "html_content"}
                # Join list fields
                for key in [
                    "script_content",
                    "authors",
                    "author_urls",
                    "archive_warnings",
                    "categories",
                    "fandoms",
                    "relationships",
                    "characters",
                    "additional_tags",
                ]:
                    if key in flattened and isinstance(flattened[key], list):
                        flattened[key] = "\n".join(str(v) for v in flattened[key])
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

    def extract_from_urls(self, urls: list[str], max_works: int | None = None) -> list:
        """Extract works from multiple URLs."""
        print(f"Starting AO3 extraction for {len(urls)} URLs...")

        extracted_data = []
        failed_urls = []

        # Apply limit if specified
        urls_to_process = urls[:max_works] if max_works else urls

        if max_works and len(urls) > max_works:
            print(
                f"Processing {len(urls_to_process)} URLs (limited by max-works={max_works})"
            )

        for i, url in enumerate(urls_to_process):
            print(f"Processing work {i + 1}/{len(urls_to_process)}: {url}")

            work_data = self.get_work_data(url)
            if work_data:
                extracted_data.append(work_data)
                self.save_individual_work(work_data)
            else:
                failed_urls.append(url)

        print("\nExtraction Summary:")
        print(f"Successfully processed: {len(extracted_data)}")
        print(f"Failed: {len(failed_urls)}")

        # Save failed URLs if any
        if failed_urls:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            failed_filepath = self.output_dir / f"failed_urls_{timestamp}.json"
            try:
                failed_filepath.write_text(
                    json.dumps(failed_urls, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"Saved failed URLs to {failed_filepath}")
            except Exception as error:
                print(f"Error saving failed URLs: {error}")

        return extracted_data


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract works from archiveofourown.org"
    )
    parser.add_argument("urls", nargs="*", help="AO3 work URLs to extract")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help=f"Output directory (default: {aural_config.AO3_DIR})",
    )
    parser.add_argument(
        "--max-works",
        "-m",
        type=int,
        help="Maximum number of works to process",
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
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (useful for debugging)",
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
        extractor = AO3Extractor(args.output)
        extractor.request_delay = args.delay / 1000.0  # Convert to seconds

        extractor.ensure_output_dir()
        extractor.setup_playwright(headless=not args.no_headless)

        # Extract works
        extracted_data = extractor.extract_from_urls(urls, args.max_works)

        print("\nExtraction complete!")
        print(f"Results saved to: {extractor.output_dir}")
        print(f"Processed {len(extracted_data)} works successfully")

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
