#!/usr/bin/env python3
"""
HotAudio Follow Extractor

Advanced version that integrates with the existing extractor architecture
and can download the actual audio files while following the story tree.

This extractor is specifically designed for Choose Your Own Adventure
type audios where the story branches based on user choices.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


class HotAudioFollowExtractor:
    """Extract and follow HotAudio story trees for CYOA content."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.output_dir = Path(config.get("output_dir", "./data/audio/hotaudio"))
        self.enrichment_dir = Path(
            config.get("enrichment_dir", "./data/enrichment/hotaudio")
        )
        self.download_audio = config.get("download_audio", True)
        self.headless = config.get("headless", True)
        self.max_depth = config.get("max_depth", 10)
        self.browser = None
        self.context = None
        self.playwright = None

    def initialize(self):
        """Initialize the browser."""
        print("Initializing browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 720})

    def cleanup(self):
        """Clean up resources."""
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    def extract_hotaudio_links(self, page) -> list[dict]:
        """Extract all HotAudio links from a page."""
        return page.evaluate(
            """() => {
            const hotAudioLinks = [];
            const seenUrls = new Set();

            // Find all links to HotAudio
            const links = document.querySelectorAll('a[href*="hotaudio.net/u/"]');

            links.forEach(link => {
                const href = link.href;
                if (seenUrls.has(href)) return;

                const match = href.match(/hotaudio\\.net\\/u\\/([^\\/]+)\\/([^\\/\\?]+)/);
                if (match) {
                    seenUrls.add(href);
                    const [, user, audio] = match;

                    // Get link context
                    const linkText = link.textContent.trim();
                    const parentText = link.parentElement?.textContent.trim() || '';

                    hotAudioLinks.push({
                        url: href,
                        title: linkText || `${user}/${audio}`,
                        user: user,
                        audio: audio,
                        context: {
                            linkText,
                            parentText: parentText.substring(0, 200)
                        }
                    });
                }
            });

            return hotAudioLinks;
        }"""
        )

    def extract_page_metadata(self, page, url: str) -> dict:
        """Extract comprehensive page metadata."""
        return page.evaluate(
            """(pageUrl) => {
            const data = {
                url: pageUrl,
                extractedAt: new Date().toISOString()
            };

            // Title extraction - prefer the main title in postbody
            const titleElement = document.querySelector('#postbody .text-4xl') ||
                                document.querySelector('h1') ||
                                document.querySelector('.title') ||
                                document.querySelector('title');
            if (titleElement) {
                data.title = titleElement.textContent.trim();
            }

            // Extract og:description meta tag
            const ogDescription = document.querySelector('meta[property="og:description"]');
            if (ogDescription && ogDescription.content) {
                data.description = ogDescription.content;
            } else {
                // Fallback to other description sources
                const descElement = document.querySelector('.description, [class*="description"], .prose p:first-of-type');
                if (descElement) {
                    data.description = descElement.textContent.trim();
                }
            }

            // Duration extraction from player-progress-text
            const durationElement = document.querySelector('#player-progress-text');
            if (durationElement) {
                const durationText = durationElement.textContent.trim();
                // Extract the total duration after the slash (e.g., "0:00 / 2:30" -> "2:30")
                const durationMatch = durationText.match(/\\d+:\\d+\\s*\\/\\s*(\\d+):(\\d+)/);
                if (durationMatch) {
                    const [, minutes, seconds] = durationMatch;
                    data.duration = `${minutes}:${seconds}`;
                    data.durationSeconds = parseInt(minutes) * 60 + parseInt(seconds);
                }
            } else {
                // Fallback to length tag in metadata
                const lengthTags = document.querySelectorAll('.tagm');
                lengthTags.forEach(tag => {
                    const firstSpan = tag.querySelector('span');
                    if (firstSpan && firstSpan.textContent.trim() === 'length') {
                        const valueSpan = tag.querySelectorAll('span')[2];
                        if (valueSpan) {
                            data.duration = valueSpan.textContent.trim();
                        }
                    }
                });
            }

            // Extract detailed metadata from postbody
            const postBody = document.querySelector('#postbody');
            if (postBody) {
                // Extract credits (by, script, voice, edit)
                const credits = {};
                const creditElements = postBody.querySelectorAll('.tagm');
                creditElements.forEach(el => {
                    const spans = el.querySelectorAll('span');
                    if (spans.length >= 2) {
                        const key = spans[0].textContent.trim();
                        const link = el.querySelector('a');
                        const value = link ? link.textContent.trim() : spans[spans.length - 1].textContent.trim();

                        if (['by', 'script', 'voice', 'edit'].includes(key)) {
                            if (!credits[key]) credits[key] = [];
                            credits[key].push(value);
                        } else if (key === 'length' && !data.duration) {
                            data.duration = value;
                        } else if (key === 'on') {
                            data.publishedDate = value;
                        }
                    }
                });

                if (Object.keys(credits).length > 0) {
                    data.credits = credits;
                    // Add all voice actors to performers list
                    if (credits.voice && credits.voice.length > 0) {
                        data.performers = credits.voice;
                    } else if (credits.by && credits.by.length > 0) {
                        // Fallback to 'by' credit if no voice credits
                        data.performers = credits.by;
                    }
                }

                // Extract tags more intelligently
                const tags = [];
                const tagLinks = postBody.querySelectorAll('a[href^="/t/"] .tag');
                tagLinks.forEach(el => {
                    const tag = el.textContent.trim();
                    if (tag && !tags.includes(tag)) {
                        tags.push(tag);
                    }
                });
                if (tags.length > 0) {
                    data.tags = tags;
                }

                // Extract script link if present
                const scriptLink = postBody.querySelector('a[href*="scriptbin.works"]');
                if (scriptLink) {
                    data.scriptUrl = scriptLink.href;
                }
            }

            // Extract audio source if available
            const audioElement = document.querySelector('audio source, audio');
            if (audioElement) {
                data.audioSource = audioElement.src || audioElement.querySelector('source')?.src;
            }

            return data;
        }""",
            url,
        )

    def download_audio_file(self, page, audio_data: dict) -> dict | None:
        """Download audio file if available."""
        if not self.download_audio:
            return None

        try:
            # Wait for audio player to be ready
            page.wait_for_selector("#player-playpause, audio", timeout=10000)

            # Try to get the audio source URL
            audio_url = page.evaluate(
                """() => {
                const audio = document.querySelector('audio');
                if (audio && audio.src) return audio.src;

                const source = document.querySelector('audio source');
                if (source && source.src) return source.src;

                // Check for any data attributes or hidden inputs
                const playerEl = document.querySelector('[data-audio-url], [data-src]');
                if (playerEl) return playerEl.dataset.audioUrl || playerEl.dataset.src;

                return null;
            }"""
            )

            if not audio_url:
                print("  Could not find audio URL on page")
                return None

            # Create file path
            user = audio_data.get("user", "unknown")
            audio = audio_data.get("audio", "unknown")
            file_name = f"{user}_{audio}.mp3"
            file_path = self.output_dir / user / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if already downloaded
            if file_path.exists():
                print(f"  Audio already downloaded: {file_name}")
                return {
                    "fileName": file_name,
                    "filePath": str(file_path),
                    "alreadyExists": True,
                }

            print(f"  Downloading audio: {file_name}")

            # Download using page context to maintain cookies/auth
            response = self.context.request.get(audio_url)
            buffer = response.body()
            file_path.write_bytes(buffer)

            print("  Downloaded successfully")
            return {
                "fileName": file_name,
                "filePath": str(file_path),
                "size": len(buffer),
                "url": audio_url,
            }

        except Exception as error:
            print(f"  Error downloading audio: {error}")
            return None

    def follow_story_tree(self, start_url: str) -> dict:
        """Follow and extract a story tree starting from a URL."""
        visited_urls: set[str] = set()
        page = self.context.new_page()

        try:
            story_tree = self._recursive_follow(page, start_url, visited_urls, 0)
            return story_tree
        finally:
            page.close()

    def _recursive_follow(
        self, page, url: str, visited_urls: set[str], depth: int
    ) -> dict:
        """Recursively follow links and build story tree."""
        if url in visited_urls:
            return {"url": url, "alreadyVisited": True}

        if depth > self.max_depth:
            return {"url": url, "maxDepthReached": True}

        indent = "  " * depth
        print(f"{indent}[{depth}] Processing: {url}")
        visited_urls.add(url)

        node: dict = {
            "url": url,
            "depth": depth,
            "processedAt": datetime.now(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
        }

        try:
            # Navigate to page
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)  # Wait for dynamic content

            # Extract metadata
            metadata = self.extract_page_metadata(page, url)
            node.update(metadata)

            # Parse URL for user/audio info
            url_match = re.search(r"hotaudio\.net/u/([^/]+)/([^/\?]+)", url)
            if url_match:
                node["user"] = url_match.group(1)
                node["audio"] = url_match.group(2)

            # Download audio if enabled
            if self.download_audio and node.get("user") and node.get("audio"):
                download_result = self.download_audio_file(page, node)
                if download_result:
                    node["download"] = download_result

            # Extract linked audios
            links = self.extract_hotaudio_links(page)
            print(f"{indent}  Found {len(links)} HotAudio links")

            # Save page HTML for enrichment data
            if node.get("user") and node.get("audio"):
                html_path = self.enrichment_dir / node["user"] / f"{node['audio']}.html"
                html_path.parent.mkdir(parents=True, exist_ok=True)
                html_content = page.content()
                html_path.write_text(html_content, encoding="utf-8")
                node["htmlSaved"] = True

            # Recursively follow each link
            node["children"] = []
            for link in links:
                child_indent = "  " * (depth + 1)
                print(f"{child_indent}Following: {link.get('title', 'unknown')}")
                child_node = self._recursive_follow(
                    page, link["url"], visited_urls, depth + 1
                )
                # Merge link context with child node
                merged_child = {**link, **child_node}
                node["children"].append(merged_child)

        except Exception as error:
            print(f"{indent}  Error: {error}")
            node["error"] = str(error)

        return node

    def generate_content_hash(self, story_tree: dict) -> str:
        """Generate a content hash for the story tree."""
        # Exclude volatile fields from hash
        volatile_fields = {"processedAt", "extractedAt", "download"}

        def filter_volatile(obj):
            if isinstance(obj, dict):
                return {
                    k: filter_volatile(v)
                    for k, v in obj.items()
                    if k not in volatile_fields
                }
            if isinstance(obj, list):
                return [filter_volatile(item) for item in obj]
            return obj

        filtered = filter_volatile(story_tree)
        content = json.dumps(filtered, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def save_results(self, story_tree: dict, start_url: str) -> dict | None:
        """Save story tree and metadata."""
        url_match = re.search(r"hotaudio\.net/u/([^/]+)/([^/\?]+)", start_url)
        if not url_match:
            return None

        user = url_match.group(1)
        audio = url_match.group(2)
        output_path = self.enrichment_dir / user / audio
        output_path.mkdir(parents=True, exist_ok=True)

        # Save full story tree
        tree_file = output_path / "story-tree.json"
        tree_file.write_text(
            json.dumps(story_tree, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nStory tree saved to: {tree_file}")

        # Generate and save summary
        summary = self.generate_summary(story_tree)
        summary_file = output_path / "story-summary.json"
        summary_file.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Save text visualization
        text_tree = self.generate_text_tree(story_tree)
        text_file = output_path / "story-tree.txt"
        text_file.write_text(text_tree, encoding="utf-8")

        return {
            "treeFile": str(tree_file),
            "summaryFile": str(summary_file),
            "textFile": str(text_file),
        }

    def generate_summary(self, story_tree: dict) -> dict:
        """Generate a summary of the story tree."""
        summary: dict = {
            "rootUrl": story_tree.get("url"),
            "title": story_tree.get("title"),
            "user": story_tree.get("user"),
            "processedAt": story_tree.get("processedAt"),
            "contentHash": self.generate_content_hash(story_tree),
            "stats": {
                "totalNodes": 0,
                "totalAudioFiles": 0,
                "downloadedFiles": 0,
                "totalDurationSeconds": 0,
                "maxDepth": 0,
                "performers": set(),
                "tags": set(),
            },
            "audioFiles": [],
        }

        def collect_stats(node: dict, current_depth: int = 0):
            stats = summary["stats"]
            stats["totalNodes"] += 1
            stats["maxDepth"] = max(stats["maxDepth"], current_depth)

            if node.get("audio") and not node.get("alreadyVisited"):
                stats["totalAudioFiles"] += 1

                audio_info = {
                    "url": node.get("url"),
                    "user": node.get("user"),
                    "audio": node.get("audio"),
                    "title": node.get("title"),
                    "duration": node.get("duration"),
                    "depth": current_depth,
                }

                if node.get("download"):
                    stats["downloadedFiles"] += 1
                    audio_info["downloaded"] = True
                    audio_info["filePath"] = node["download"].get("filePath")

                summary["audioFiles"].append(audio_info)

            if node.get("durationSeconds"):
                stats["totalDurationSeconds"] += node["durationSeconds"]

            performers = node.get("performers")
            if performers and isinstance(performers, list):
                for performer in performers:
                    stats["performers"].add(performer)

            tags = node.get("tags")
            if tags and isinstance(tags, list):
                for tag in tags:
                    stats["tags"].add(tag)

            children = node.get("children")
            if children:
                for child in children:
                    collect_stats(child, current_depth + 1)

        collect_stats(story_tree)

        # Convert sets to lists
        summary["stats"]["performers"] = list(summary["stats"]["performers"])
        summary["stats"]["tags"] = list(summary["stats"]["tags"])

        # Format total duration
        total_seconds = summary["stats"]["totalDurationSeconds"]
        if total_seconds > 0:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            summary["stats"]["formattedTotalDuration"] = f"{hours}h {minutes}m"

        return summary

    def generate_text_tree(self, node: dict, depth: int = 0) -> str:
        """Generate text representation of story tree."""
        lines: list[str] = []
        indent = "  " * depth

        if depth == 0:
            lines.append("HOTAUDIO STORY TREE")
            lines.append("==================")
            lines.append("")

        # Node info
        title = node.get("title") or node.get("audio") or "Unknown"
        lines.append(f"{indent}[{depth}] {title}")
        lines.append(f"{indent}    URL: {node.get('url', 'N/A')}")

        if node.get("duration"):
            lines.append(f"{indent}    Duration: {node['duration']}")

        performers = node.get("performers")
        if performers and len(performers) > 0:
            lines.append(f"{indent}    Performers: {', '.join(performers)}")

        if node.get("download"):
            lines.append(f"{indent}    Downloaded: {node['download'].get('fileName')}")

        if node.get("error"):
            lines.append(f"{indent}    ERROR: {node['error']}")

        if node.get("alreadyVisited"):
            lines.append(f"{indent}    (Already visited)")

        lines.append("")

        # Children
        children = node.get("children")
        if children and len(children) > 0:
            for child in children:
                lines.append(self.generate_text_tree(child, depth + 1))

        return "\n".join(lines)

    def extract(self, url: str, options: dict | None = None) -> dict:
        """Main extraction method."""
        options = options or {}

        # Update config from options
        if "download_audio" in options:
            self.download_audio = options["download_audio"]
        if "headless" in options:
            self.headless = options["headless"]
        if "max_depth" in options:
            self.max_depth = options["max_depth"]
        if "output_dir" in options:
            self.output_dir = Path(options["output_dir"])
        if "enrichment_dir" in options:
            self.enrichment_dir = Path(options["enrichment_dir"])

        try:
            self.initialize()

            print("Starting HotAudio story tree extraction...")
            print(f"URL: {url}")
            print(f"Download audio: {self.download_audio}")
            print(f"Max depth: {self.max_depth}")
            print("")

            story_tree = self.follow_story_tree(url)

            summary = self.generate_summary(story_tree)
            print("\n=== EXTRACTION COMPLETE ===")
            print(f"Total nodes: {summary['stats']['totalNodes']}")
            print(f"Total audio files: {summary['stats']['totalAudioFiles']}")
            print(f"Downloaded files: {summary['stats']['downloadedFiles']}")
            print(f"Max depth reached: {summary['stats']['maxDepth']}")
            if summary["stats"].get("formattedTotalDuration"):
                print(f"Total duration: {summary['stats']['formattedTotalDuration']}")

            saved_files = self.save_results(story_tree, url)
            if saved_files:
                print(f"\nResults saved to: {saved_files['treeFile']}")

            return {
                "storyTree": story_tree,
                "summary": summary,
                "savedFiles": saved_files,
            }

        finally:
            self.cleanup()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract HotAudio story trees for CYOA content"
    )
    parser.add_argument("url", nargs="?", help="HotAudio URL to extract")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Do not download audio files",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Show browser window",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum depth to follow (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for audio files",
    )
    parser.add_argument(
        "--enrichment-dir",
        help="Directory for metadata files",
    )

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        print("\nExample:")
        print(
            "  uv run python hotaudio_follow_extractor.py "
            "https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up"
        )
        return 1

    config: dict = {}
    if args.output_dir:
        config["output_dir"] = args.output_dir
    if args.enrichment_dir:
        config["enrichment_dir"] = args.enrichment_dir

    options = {
        "download_audio": not args.no_download,
        "headless": not args.show_browser,
        "max_depth": args.max_depth,
    }

    extractor = HotAudioFollowExtractor(config)

    try:
        extractor.extract(args.url, options)
        return 0
    except Exception as error:
        print(f"Fatal error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
