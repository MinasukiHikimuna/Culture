#!/usr/bin/env python3
"""
HotAudio Indexer

This script discovers and indexes audio releases from HotAudio using Playwright.
It crawls user profiles and creates JSON lists of releases for extraction.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


class HotAudioIndexer:
    """Index HotAudio releases by crawling user profiles."""

    def __init__(self, output_dir: str = "hotaudio_data"):
        self.output_dir = Path(output_dir).resolve()
        self.request_delay = 2.0  # Seconds between requests
        self.last_request_time = 0.0
        self.browser = None
        self.page = None
        self.playwright = None

    def setup_playwright(self):
        """Initialize Playwright browser."""
        try:
            print("Starting Playwright browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()

            # Set user agent
            self.page.set_extra_http_headers(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/76.0.3809.100 Safari/537.36"
                    )
                }
            )

            print("Playwright browser initialized successfully")
        except Exception as error:
            print(f"Failed to initialize Playwright: {error}")
            print('Run "uv run playwright install chromium" to install browser')
            raise

    def close_browser(self):
        """Close browser and cleanup resources."""
        if self.page:
            self.page.close()
            self.page = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        print("Browser closed")

    def rate_limit(self):
        """Apply rate limiting between requests."""
        now = time.time()
        time_since_last_request = now - self.last_request_time

        if time_since_last_request < self.request_delay:
            wait_time = self.request_delay - time_since_last_request
            print(f"Rate limiting: waiting {wait_time:.0f}s...")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def extract_hotaudio_links(self, page) -> list[dict]:
        """Extract all HotAudio links from the current page."""
        return page.evaluate(
            """() => {
            const hotAudioLinks = [];
            const seenIds = new Set();

            // Select links with /u/ pattern (both relative and absolute)
            const links = document.querySelectorAll('a[href*="/u/"]');

            links.forEach(link => {
                const href = link.getAttribute('href');
                if (!href) return;

                // Match both relative (/u/user/audio) and absolute URLs
                const match = href.match(/\\/u\\/([^\\/]+)\\/([^\\/\\?]+)/);
                if (match) {
                    const [, user, audio] = match;
                    const id = `${user}/${audio}`;

                    // Skip duplicates and user profile links (no audio part)
                    if (seenIds.has(id)) return;
                    seenIds.add(id);

                    const title = link.textContent.trim() || `${user}/${audio}`;

                    // Build full URL
                    const fullUrl = href.startsWith('http')
                        ? href
                        : `https://hotaudio.net${href}`;

                    hotAudioLinks.push({
                        id: id,
                        url: fullUrl,
                        title: title,
                        user: user,
                        audioId: audio
                    });
                }
            });

            return hotAudioLinks;
        }"""
        )

    def index_user_profile(self, user_url: str, max_depth: int = 3) -> dict:
        """Index a user profile by crawling from the start URL."""
        print(f"Indexing user profile: {user_url}")

        releases: dict[str, dict] = {}  # Use dict to avoid duplicates
        visited: set[str] = set()
        story_map = {"title": "Root", "url": user_url, "children": []}

        self.crawl_page(user_url, releases, visited, story_map, 0, max_depth)

        return {
            "platform": "hotaudio",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "user": self.extract_user_from_url(user_url),
            "totalReleases": len(releases),
            "storyMap": story_map,
            "releases": list(releases.values()),
        }

    def crawl_page(
        self,
        url: str,
        releases: dict[str, dict],
        visited: set[str],
        story_map: dict,
        depth: int = 0,
        max_depth: int = 3,
    ):
        """Recursively crawl pages and collect releases."""
        if depth > max_depth or url in visited:
            return

        visited.add(url)
        indent = "  " * depth
        print(f"{indent}Crawling: {url} (depth {depth})")

        try:
            self.rate_limit()
            self.page.goto(url, wait_until="networkidle")

            # Extract links for this page
            links = self.extract_hotaudio_links(self.page)
            print(f"{indent}Found {len(links)} HotAudio links on this page")

            # Add releases to our collection
            for link in links:
                link_id = link["id"]
                if link_id not in releases:
                    releases[link_id] = {
                        **link,
                        "discoveredAt": datetime.now(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "discoveredFrom": url,
                        "depth": depth,
                    }

            # Update story map
            if "children" not in story_map:
                story_map["children"] = []

            # Recursively crawl found links
            for link in links:
                child_node = {
                    "title": link["title"],
                    "url": link["url"],
                    "user": link["user"],
                    "audioId": link["audioId"],
                }

                story_map["children"].append(child_node)

                if depth < max_depth:
                    self.crawl_page(
                        link["url"], releases, visited, child_node, depth + 1, max_depth
                    )

        except Exception as error:
            print(f"{indent}Error crawling {url}: {error}")

    def extract_user_from_url(self, url: str) -> str:
        """Extract username from HotAudio URL."""
        match = re.search(r"hotaudio\.net/u/([^/]+)", url)
        return match.group(1) if match else "unknown"

    def save_index(self, index_data: dict, output_file: Path):
        """Save index data to JSON file."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(index_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Index saved to: {output_file}")
        print(f"Total releases found: {index_data['totalReleases']}")

    def save_story_map(self, index_data: dict, output_file: Path):
        """Save story map as text file."""
        map_file = output_file.with_suffix(".story-map.txt")
        lines: list[str] = []

        def build_map_content(node: dict, depth: int = 0):
            indent = "  " * depth
            lines.append(
                f"{indent}{node.get('title', 'Unknown')}: {node.get('url', 'N/A')}"
            )

            children = node.get("children")
            if children:
                for child in children:
                    build_map_content(child, depth + 1)

        build_map_content(index_data["storyMap"])
        map_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"Story map saved to: {map_file}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Index HotAudio releases for extraction"
    )
    parser.add_argument(
        "-u",
        "--user",
        required=True,
        help="HotAudio username to index",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=3,
        help="Maximum crawl depth (default: 3)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="hotaudio_data",
        help="Output directory (default: hotaudio_data)",
    )

    args = parser.parse_args()

    indexer = HotAudioIndexer(args.output)

    try:
        indexer.setup_playwright()

        user_url = f"https://hotaudio.net/u/{args.user}"
        index_data = indexer.index_user_profile(user_url, args.depth)

        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y-%m-%d")
        output_file = Path(args.output) / f"{args.user}_index_{timestamp}.json"

        indexer.save_index(index_data, output_file)
        indexer.save_story_map(index_data, output_file)

        print("Indexing completed successfully!")

    except Exception as error:
        print(f"Indexing failed: {error}")
        return 1
    finally:
        indexer.close_browser()

    return 0


if __name__ == "__main__":
    exit(main())
