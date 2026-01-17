#!/usr/bin/env python3
"""
Process Reddit URL - Complete End-to-End Workflow

Takes a Reddit URL as input and:
1. Fetches the Reddit post
2. Analyzes it with LLM
3. Extracts all audio files
4. Creates a complete release

Usage:
    uv run python process_reddit_url.py <reddit_url> [--output <dir>] [--no-cache]
"""

import argparse
import json
import re
import shutil
from pathlib import Path

import praw
from analyze_reddit_post import EnhancedRedditPostAnalyzer
from dotenv import load_dotenv
from release_orchestrator import ReleaseOrchestrator


# Load environment variables
load_dotenv()


class RedditProcessor:
    """Process Reddit URLs through the complete extraction pipeline."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.output_dir = Path(config.get("outputDir", "data"))
        self.temp_dir = self.output_dir / ".temp"
        self.cache_enabled = config.get("cacheEnabled", True)

        self.orchestrator = ReleaseOrchestrator(
            {
                "dataDir": str(self.output_dir),
                "cacheEnabled": self.cache_enabled,
                "validateExtractions": True,
            }
        )

        # Reddit API client (initialized lazily)
        self._reddit: praw.Reddit | None = None

    @property
    def reddit(self) -> praw.Reddit:
        """Lazy initialization of Reddit API client."""
        if self._reddit is None:
            import os

            client_id = os.getenv("REDDIT_CLIENT_ID")
            client_secret = os.getenv("REDDIT_CLIENT_SECRET")
            user_agent = os.getenv("REDDIT_USER_AGENT", "Aural/1.0")

            if not client_id or not client_secret:
                raise ValueError(
                    "Reddit API credentials not found. "
                    "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env"
                )

            self._reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
        return self._reddit

    def process_reddit_url(self, reddit_url: str) -> dict:
        """Process a Reddit URL through the complete pipeline."""
        print(f"Processing Reddit URL: {reddit_url}")
        print("=" * 60)

        try:
            # Ensure temp directory exists
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Analyze Reddit post
            print("\nStep 1: Analyzing Reddit post...")
            analysis = self.analyze_reddit_post(reddit_url)
            print(f"Analysis complete: {analysis['metadata']['title']}")

            # Step 2: Extract Reddit post data
            print("\nStep 2: Extracting post metadata...")
            reddit_post = self.extract_reddit_data(analysis)
            audio_count = len(analysis.get("audio_versions") or [])
            print(f"Found {audio_count} audio version(s)")

            # Step 3: Process into release
            print("\nStep 3: Extracting audio files...")
            release = self.orchestrator.process_post(reddit_post, analysis)

            # Step 4: Generate summary
            print("\nStep 4: Generating summary...")
            summary = self.generate_summary(release, reddit_url)

            # Cleanup temp directory
            try:
                shutil.rmtree(self.temp_dir)
            except OSError:
                pass  # Ignore cleanup errors

            return {"success": True, "release": release, "summary": summary}

        except Exception as error:
            print(f"\nProcessing failed: {error}")
            raise

    def analyze_reddit_post(self, reddit_url: str) -> dict:
        """Analyze Reddit post using the LLM analyzer."""
        analysis_output = self.temp_dir / "analysis.json"

        try:
            # First, we need to fetch the Reddit post and save it for the analyzer
            post_data = self.fetch_reddit_post(reddit_url)

            if not post_data:
                raise ValueError("Failed to fetch Reddit post")

            # Save post data for the analyzer
            post_file = self.temp_dir / "post_data.json"
            post_file.write_text(
                json.dumps(post_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            # Run the LLM analyzer
            analyzer = EnhancedRedditPostAnalyzer()
            analysis = analyzer.analyze_post(post_file)

            # Save analysis result
            analysis_output.write_text(
                json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            return analysis

        except Exception as error:
            # Fallback to basic analysis
            print(f"Could not run LLM analysis, using basic extraction: {error}")
            return self.basic_reddit_analysis(reddit_url)

    def fetch_reddit_post(self, reddit_url: str) -> dict | None:
        """Fetch Reddit post data using PRAW."""
        post_id = self.extract_post_id(reddit_url)
        if not post_id:
            return None

        try:
            submission = self.reddit.submission(id=post_id)
            # Trigger lazy loading
            _ = submission.title

            # Check for crosspost and resolve if needed
            selftext = submission.selftext
            if self.is_crosspost(submission):
                resolved = self.resolve_crosspost(submission)
                if resolved:
                    selftext = resolved.get("selftext", selftext)

            return {
                "post_id": submission.id,
                "username": str(submission.author)
                if submission.author
                else "[deleted]",
                "reddit_url": reddit_url,
                "date": submission.created_utc,
                "reddit_data": {
                    "post_id": submission.id,
                    "title": submission.title,
                    "selftext": selftext,
                    "author": str(submission.author)
                    if submission.author
                    else "[deleted]",
                    "created_utc": submission.created_utc,
                    "subreddit": str(submission.subreddit),
                    "link_flair_text": submission.link_flair_text,
                    "url": submission.url,
                    "permalink": f"https://www.reddit.com{submission.permalink}",
                },
            }
        except Exception as error:
            print(f"Failed to fetch Reddit post: {error}")
            return None

    def is_crosspost(self, submission) -> bool:
        """Detect if a submission is a crosspost that needs resolution."""
        selftext = getattr(submission, "selftext", "") or ""
        if selftext.strip() and selftext not in ("[deleted]", "[removed]"):
            return False

        # Check explicit crosspost indicators
        if not submission.is_self:
            url = getattr(submission, "url", "") or ""
            if ("/r/" in url or "/u_" in url) and "/comments/" in url:
                return True

        # Check domain
        domain = getattr(submission, "domain", "") or ""
        if domain == "reddit.com":
            return True

        # User profile crossposts
        if not submission.is_self and domain.startswith("self."):
            return True

        # Check crosspost_parent_list
        crosspost_parent_list = getattr(submission, "crosspost_parent_list", None)
        if crosspost_parent_list and len(crosspost_parent_list) > 0:
            return True

        return False

    def resolve_crosspost(self, submission) -> dict | None:
        """Resolve a crosspost to get the original post content."""
        # First, check crosspost_parent_list
        crosspost_parent_list = getattr(submission, "crosspost_parent_list", None)
        if crosspost_parent_list and len(crosspost_parent_list) > 0:
            parent = crosspost_parent_list[0]
            parent_selftext = parent.get("selftext", "")
            if parent_selftext and parent_selftext not in ("[deleted]", "[removed]"):
                print("  Using crosspost_parent_list data")
                return {
                    "selftext": parent_selftext,
                    "resolved_from": "crosspost_parent_list",
                    "original_post_id": parent.get("id"),
                    "original_author": parent.get("author"),
                }

        # Try to resolve via URL
        url = getattr(submission, "url", "") or ""
        if "/comments/" in url:
            target_post_id = self.extract_post_id(url)
            if target_post_id and target_post_id != submission.id:
                print(f"  Resolving crosspost: {url}")
                try:
                    original = self.reddit.submission(id=target_post_id)
                    _ = original.title  # Trigger lazy load
                    original_selftext = getattr(original, "selftext", "") or ""

                    if original_selftext and original_selftext not in (
                        "[deleted]",
                        "[removed]",
                    ):
                        return {
                            "selftext": original_selftext,
                            "resolved_from": url,
                            "original_post_id": original.id,
                            "original_author": str(original.author)
                            if original.author
                            else "[deleted]",
                        }
                except Exception as error:
                    print(f"  Could not resolve crosspost: {error}")

        return None

    def extract_post_id(self, reddit_url: str) -> str | None:
        """Extract post ID from Reddit URL."""
        match = re.search(r"comments/([a-z0-9]+)", reddit_url)
        return match.group(1) if match else None

    def basic_reddit_analysis(self, reddit_url: str) -> dict:
        """Basic Reddit analysis fallback when LLM analysis fails."""
        post_data = self.fetch_reddit_post(reddit_url)

        if not post_data:
            raise ValueError("Failed to fetch Reddit post")

        reddit_data = post_data.get("reddit_data", {})
        content = reddit_data.get("selftext", "")

        # Extract audio URLs
        audio_urls = self.extract_audio_urls(content)

        return {
            "metadata": {
                "post_id": reddit_data.get("post_id"),
                "title": reddit_data.get("title"),
                "username": reddit_data.get("author"),
                "created_utc": reddit_data.get("created_utc"),
                "url": reddit_url,
            },
            "content": {
                "title": reddit_data.get("title"),
                "selftext": content,
            },
            "audio_versions": (
                [
                    {
                        "version_name": "Main",
                        "urls": [
                            {"url": url, "platform": self.detect_platform(url)}
                            for url in audio_urls
                        ],
                    }
                ]
                if audio_urls
                else []
            ),
            "performers": {
                "primary": reddit_data.get("author"),
                "additional": [],
                "count": 1,
            },
            "tags": self.extract_tags((reddit_data.get("title") or "") + " " + content),
        }

    def extract_audio_urls(self, text: str) -> list[str]:
        """Extract audio URLs from text."""
        patterns = [
            r"https?://(?:www\.)?soundgasm\.net/u/[^\s\]\)]+",
            r"https?://(?:www\.)?whyp\.it/tracks/[^\s\]\)]+",
            r"https?://(?:www\.)?hotaudio\.net/u/[^\s\]\)]+",
        ]

        urls = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            # Clean up URLs that might have trailing parentheses
            for url in matches:
                if url.endswith(")") and "(" not in url:
                    url = url[:-1]
                urls.append(url)

        return list(set(urls))  # Remove duplicates

    def detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        if re.search(r"soundgasm\.net", url, re.IGNORECASE):
            return "Soundgasm"
        if re.search(r"whyp\.it", url, re.IGNORECASE):
            return "Whyp.it"
        if re.search(r"hotaudio\.net", url, re.IGNORECASE):
            return "HotAudio"
        return "Unknown"

    def extract_tags(self, text: str) -> list[str]:
        """Extract tags from text."""
        tags = []
        for match in re.finditer(r"\[([^\]]+)\]", text):
            tags.append(match.group(1))
        return tags

    def extract_reddit_data(self, analysis: dict) -> dict:
        """Convert analysis to Reddit post format for orchestrator."""
        metadata = analysis.get("metadata", {})
        return {
            "id": metadata.get("post_id"),
            "title": metadata.get("title"),
            "author": metadata.get("username"),
            "created_utc": metadata.get("created_utc"),
            "selftext": analysis.get("content", {}).get("selftext", ""),
            "url": metadata.get("url"),
        }

    def generate_summary(self, release, reddit_url: str) -> dict:
        """Generate summary report."""
        release_dict = release.to_dict()

        summary = {
            "reddit_url": reddit_url,
            "release_id": release_dict["id"],
            "title": release_dict["title"],
            "performer": release_dict["primaryPerformer"],
            "audio_sources": len(release_dict["audioSources"]),
            "platforms": list(
                {
                    s.get("metadata", {}).get("platform", {}).get("name")
                    for s in release_dict["audioSources"]
                    if s.get("metadata", {}).get("platform", {}).get("name")
                }
            ),
            "extracted_files": [],
        }

        # List extracted files
        for source in release_dict["audioSources"]:
            audio = source.get("audio", {})
            summary["extracted_files"].append(
                {
                    "platform": source.get("metadata", {})
                    .get("platform", {})
                    .get("name"),
                    "file": audio.get("filePath"),
                    "size": audio.get("fileSize"),
                    "checksum": audio.get("checksum", {}).get("sha256"),
                }
            )

        # Save summary
        llm_analysis = release_dict.get("enrichmentData", {}).get("llmAnalysis") or {}
        version_naming = llm_analysis.get("version_naming", {})

        if version_naming.get("release_directory"):
            release_dir = (
                self.output_dir
                / "releases"
                / release_dict["primaryPerformer"]
                / version_naming["release_directory"]
            )
        else:
            release_dir = (
                self.output_dir
                / "releases"
                / release_dict["primaryPerformer"]
                / release_dict["id"]
            )

        summary_path = release_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Print summary
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Release ID: {release_dict['id']}")
        print(f"Title: {release_dict['title']}")
        print(f"Performer: {release_dict['primaryPerformer']}")
        print(f"Audio Sources: {len(release_dict['audioSources'])}")
        print(f"Platforms: {', '.join(summary['platforms'])}")
        print("\nExtracted Files:")

        for file_info in summary["extracted_files"]:
            print(f"  - {file_info['platform']}: {file_info['file']}")
            if file_info["size"]:
                size_mb = file_info["size"] / 1024 / 1024
                print(f"    Size: {size_mb:.2f} MB")
            if file_info["checksum"]:
                print(f"    SHA256: {file_info['checksum'][:16]}...")

        print(f"\nComplete release saved to: {release_dir}")
        print("=" * 60)

        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Process Reddit URL - Complete Aural Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Arguments:
  reddit_url    Full Reddit post URL (e.g., https://www.reddit.com/r/gonewildaudio/comments/...)

Options:
  --output <dir>    Output directory (default: data)
  --no-cache        Disable caching

Example:
  uv run python process_reddit_url.py "https://www.reddit.com/r/gonewildaudio/comments/1abc123/..."

Output Structure:
  data/
  ├── audio/          # Downloaded audio files by platform
  ├── enrichment/     # Reddit post analysis
  └── releases/       # Complete releases with all metadata
""",
    )
    parser.add_argument("reddit_url", nargs="?", help="Reddit post URL to process")
    parser.add_argument(
        "--output",
        "-o",
        default="data",
        help="Output directory (default: data)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching",
    )

    args = parser.parse_args()

    if not args.reddit_url:
        parser.print_help()
        return 0

    try:
        processor = RedditProcessor(
            {
                "outputDir": args.output,
                "cacheEnabled": not args.no_cache,
            }
        )
        result = processor.process_reddit_url(args.reddit_url)

        if result["success"]:
            print("\nProcessing completed successfully!")
            return 0
        else:
            print("\nProcessing failed")
            return 1

    except Exception as error:
        print(f"\nFatal error: {error}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
