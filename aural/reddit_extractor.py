#!/usr/bin/env python3
"""
Reddit Data Extractor using PRAW

This script uses the PRAW library to extract detailed data from Reddit posts
that were previously identified by the gwasi_extractor. It enriches the gwasi
data with additional Reddit metadata like actual post content, flair, upvote
ratio, awards, and more.

Requirements:
1. Install PRAW: conda install praw or pip install praw
2. Set up Reddit API credentials (see setup instructions below)
3. Have gwasi_extractor output files available
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import praw
from config import GWASI_INDEX_DIR, REDDIT_INDEX_DIR, ensure_directories
from dotenv import load_dotenv


def find_latest_gwasi_data() -> Path | None:
    """Find the most recent gwasi_data_*.json file."""
    data_files = sorted(GWASI_INDEX_DIR.glob("gwasi_data_*.json"))
    return data_files[-1] if data_files else None


class RedditExtractor:
    def __init__(self, output_dir: str = "reddit_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize Reddit instance (will be set up in setup_reddit)
        self.reddit = None

        # Rate limiting
        self.request_delay = 5.0  # Seconds between requests
        self.last_request_time = 0

    def setup_reddit(
        self, client_id: str | None = None, client_secret: str | None = None, user_agent: str | None = None
    ):
        """
        Setup Reddit API connection using PRAW.

        Reddit API Setup Instructions:
        1. Go to https://www.reddit.com/prefs/apps
        2. Click "Create App" or "Create Another App"
        3. Choose "script" as the app type
        4. Note down your client_id and client_secret
        5. Set environment variables or pass them as parameters

        Environment Variables:
        - REDDIT_CLIENT_ID
        - REDDIT_CLIENT_SECRET
        - REDDIT_USER_AGENT (optional, defaults to script name)
        """

        # Load environment variables from .env file
        load_dotenv()

        # Get credentials from parameters or environment variables
        client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = user_agent or os.getenv("REDDIT_USER_AGENT", "DirtyOldFella")

        if not client_id or not client_secret:
            raise ValueError(
                "Reddit API credentials not found. Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET "
                "environment variables or pass them as parameters.\n\n"
                "Setup instructions:\n"
                "1. Go to https://www.reddit.com/prefs/apps\n"
                "2. Click 'Create App' or 'Create Another App'\n"
                "3. Choose 'script' as the app type\n"
                "4. Set environment variables:\n"
                "   set REDDIT_CLIENT_ID=your_client_id\n"
                "   set REDDIT_CLIENT_SECRET=your_client_secret\n"
                "   set REDDIT_USER_AGENT=reddit_extractor/1.0 by YourUsername"
            )

        try:
            self.reddit = praw.Reddit(
                client_id=client_id, client_secret=client_secret, user_agent=user_agent
            )

            # Test the connection
            print("✅ Connected to Reddit as read-only user")
            print(f"🔧 User agent: {user_agent}")

        except Exception as e:
            raise Exception(f"Failed to connect to Reddit API: {e}") from e

    def rate_limit(self):
        """Simple rate limiting to be respectful to Reddit API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            sleep_time = self.request_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def extract_post_id_from_url(self, reddit_url: str) -> str | None:
        """Extract post ID from Reddit URL."""
        if not reddit_url:
            return None

        # Reddit URLs typically look like:
        # https://www.reddit.com/r/subreddit/comments/post_id/title/
        try:
            parts = reddit_url.strip("/").split("/")
            if "comments" in parts:
                comment_index = parts.index("comments")
                if comment_index + 1 < len(parts):
                    return parts[comment_index + 1]
        except (ValueError, IndexError):
            pass

        return None

    def normalize_reddit_url(self, url: str) -> str:
        """Normalize Reddit URL to standard format."""
        if not url:
            return url

        # Remove query parameters and fragments
        normalized = url.split("?")[0].split("#")[0]

        # Ensure https://www.reddit.com prefix
        if normalized.startswith(("/r/", "/u/")):
            normalized = f"https://www.reddit.com{normalized}"
        elif normalized.startswith("reddit.com"):
            normalized = f"https://www.{normalized}"
        elif normalized.startswith("www.reddit.com"):
            normalized = f"https://{normalized}"

        # Remove trailing slash
        normalized = normalized.rstrip("/")

        return normalized

    def is_crosspost(self, submission) -> bool:
        """
        Detect if a PRAW submission is a crosspost that needs resolution.

        Args:
            submission: PRAW Submission object

        Returns:
            True if the post is a crosspost needing resolution
        """
        # Check if selftext is empty/missing - main indicator we need to resolve
        selftext = getattr(submission, "selftext", "") or ""
        if selftext.strip() and selftext not in ("[deleted]", "[removed]"):
            # Has content, no need to resolve
            return False

        # Check explicit crosspost indicators
        if not submission.is_self:
            url = getattr(submission, "url", "") or ""
            # Match /r/subreddit/comments/ or /r/u_username/comments/
            if ("/r/" in url or "/u_" in url) and "/comments/" in url:
                return True

        # Check domain - crossposts often have domain "reddit.com"
        domain = getattr(submission, "domain", "") or ""
        if domain == "reddit.com":
            return True

        # User profile crossposts: domain is "self.username" but is_self is false
        if not submission.is_self and domain.startswith("self."):
            return True

        # Check if we have crosspost_parent_list
        crosspost_parent_list = getattr(submission, "crosspost_parent_list", None)
        return crosspost_parent_list and len(crosspost_parent_list) > 0

    def resolve_crosspost(self, submission) -> dict | None:
        """
        Resolve a crosspost to get the original post content.

        Args:
            submission: PRAW Submission object that is a crosspost

        Returns:
            Dict with resolved selftext and metadata, or None if resolution failed
        """
        # First, check crosspost_parent_list (fastest - no extra API call)
        crosspost_parent_list = getattr(submission, "crosspost_parent_list", None)
        if crosspost_parent_list and len(crosspost_parent_list) > 0:
            parent = crosspost_parent_list[0]
            parent_selftext = parent.get("selftext", "")
            if parent_selftext and parent_selftext not in ("[deleted]", "[removed]"):
                print("  📋 Using crosspost_parent_list data")
                return {
                    "selftext": parent_selftext,
                    "resolved_from": "crosspost_parent_list",
                    "original_post_id": parent.get("id"),
                    "original_author": parent.get("author"),
                    "original_subreddit": parent.get("subreddit"),
                }

        # Try to resolve via URL if it points to another Reddit post
        url = getattr(submission, "url", "") or ""
        if "/comments/" in url:
            target_url = self.normalize_reddit_url(url)
            target_post_id = self.extract_post_id_from_url(target_url)

            if target_post_id and target_post_id != submission.id:
                print(f"  🔗 Resolving crosspost: {target_url}")
                try:
                    self.rate_limit()
                    original = self.reddit.submission(id=target_post_id)
                    # Trigger lazy load
                    _ = original.title
                    original_selftext = getattr(original, "selftext", "") or ""

                    if original_selftext and original_selftext not in (
                        "[deleted]",
                        "[removed]",
                    ):
                        return {
                            "selftext": original_selftext,
                            "resolved_from": target_url,
                            "original_post_id": original.id,
                            "original_author": str(original.author)
                            if original.author
                            else "[deleted]",
                            "original_subreddit": str(original.subreddit),
                        }
                except Exception as e:
                    print(f"  ⚠️ Could not resolve crosspost: {e}")

        return None

    def get_post_data(self, post_id: str, resolve_crossposts: bool = True) -> dict | None:
        """
        Fetch detailed data for a single Reddit post.

        Args:
            post_id: Reddit post ID
            resolve_crossposts: If True, automatically resolve crossposts to get
                               the original post content

        Returns:
            Dictionary with post data or None if post not found/error
        """
        if not self.reddit:
            raise Exception("Reddit API not initialized. Call setup_reddit() first.")

        self.rate_limit()

        try:
            submission = self.reddit.submission(id=post_id)

            # Access submission attributes to trigger API call
            # This is necessary because PRAW uses lazy loading
            _ = submission.title

            # Check for crosspost and resolve if needed
            crosspost_info = None
            selftext = submission.selftext
            if resolve_crossposts and self.is_crosspost(submission):
                crosspost_info = self.resolve_crosspost(submission)
                if crosspost_info:
                    selftext = crosspost_info["selftext"]

            # Extract comments
            comments_data = []
            try:
                submission.comments.replace_more(limit=None)  # Load all comments
                for comment in submission.comments.list():
                    if hasattr(comment, "body"):  # Skip deleted comments
                        comment_data = {
                            "comment_id": comment.id,
                            "author": str(comment.author) if comment.author else "[deleted]",
                            "body": comment.body,
                            "score": comment.score,
                            "created_utc": comment.created_utc,
                            "created_date": datetime.fromtimestamp(
                                comment.created_utc
                            ).isoformat(),
                            "is_submitter": comment.is_submitter,
                            "distinguished": comment.distinguished,
                            "edited": comment.edited,
                            "parent_id": comment.parent_id,
                            "permalink": f"https://www.reddit.com{comment.permalink}",
                        }
                        comments_data.append(comment_data)
            except Exception as e:
                print(f"⚠️ Warning: Could not load comments for post {post_id}: {e}")
                comments_data = []

            post_data = {
                "post_id": submission.id,
                "title": submission.title,
                "selftext": selftext,
                "subreddit": str(submission.subreddit),
                "author": str(submission.author) if submission.author else "[deleted]",
                "created_utc": submission.created_utc,
                "created_date": datetime.fromtimestamp(
                    submission.created_utc
                ).isoformat(),
                "score": submission.score,
                "upvote_ratio": submission.upvote_ratio,
                "num_comments": submission.num_comments,
                "permalink": f"https://www.reddit.com{submission.permalink}",
                "url": submission.url,
                "is_self": submission.is_self,
                "is_video": submission.is_video,
                "over_18": submission.over_18,
                "spoiler": submission.spoiler,
                "stickied": submission.stickied,
                "locked": submission.locked,
                "archived": submission.archived,
                "link_flair_text": submission.link_flair_text,
                "link_flair_css_class": submission.link_flair_css_class,
                "author_flair_text": submission.author_flair_text,
                "distinguished": submission.distinguished,
                "edited": submission.edited,
                "gilded": submission.gilded,
                "total_awards_received": submission.total_awards_received,
                "all_awardings": (
                    [
                        {
                            "name": award.get("name"),
                            "count": award.get("count"),
                            "coin_price": award.get("coin_price"),
                            "description": award.get("description"),
                        }
                        for award in submission.all_awardings
                    ]
                    if hasattr(submission, "all_awardings")
                    else []
                ),
                "domain": submission.domain,
                "media": str(submission.media) if submission.media else None,
                "secure_media": (
                    str(submission.secure_media) if submission.secure_media else None
                ),
                "comments": comments_data,
            }

            # Add crosspost resolution info if applicable
            if crosspost_info:
                post_data["crosspost_resolved"] = crosspost_info

            return post_data

        except Exception as e:
            print(f"❌ Error fetching post {post_id}: {e}")
            return None

    def create_slug(self, title: str, max_length: int = 50) -> str:
        """
        Create a URL-friendly slug from a title.

        Args:
            title: The title to convert
            max_length: Maximum length of the slug

        Returns:
            A URL-friendly slug
        """
        if not title:
            return "untitled"

        # Convert to lowercase and replace spaces with hyphens
        slug = title.lower()

        # Remove special characters except hyphens and alphanumeric
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)

        # Replace multiple spaces/hyphens with single hyphen
        slug = re.sub(r"[\s-]+", "-", slug)

        # Remove leading/trailing hyphens
        slug = slug.strip("-")

        # Truncate to max length
        if len(slug) > max_length:
            slug = slug[:max_length].rstrip("-")

        return slug or "untitled"

    def load_gwasi_data(self, gwasi_file: str) -> list[dict]:
        """Load gwasi extractor output data."""
        gwasi_path = Path(gwasi_file)

        if not gwasi_path.exists():
            raise FileNotFoundError(f"Gwasi data file not found: {gwasi_file}")

        if gwasi_path.suffix.lower() == ".csv":
            return self.load_gwasi_csv(gwasi_path)
        if gwasi_path.suffix.lower() == ".json":
            return self.load_gwasi_json(gwasi_path)
        raise ValueError(f"Unsupported file format: {gwasi_path.suffix}")

    def load_gwasi_csv(self, csv_path: Path) -> list[dict]:
        """Load gwasi data from CSV file."""
        data = []
        try:
            with csv_path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            print(f"📂 Loaded {len(data)} entries from {csv_path}")
            return data
        except Exception as e:
            raise Exception(f"Error loading CSV file {csv_path}: {e}") from e

    def load_gwasi_json(self, json_path: Path) -> list[dict]:
        """Load gwasi data from JSON file."""
        try:
            with json_path.open(encoding="utf-8") as f:
                data = json.load(f)
            print(f"📂 Loaded {len(data)} entries from {json_path}")
            return data
        except Exception as e:
            raise Exception(f"Error loading JSON file {json_path}: {e}") from e

    def extract_reddit_data(
        self,
        gwasi_data: list[dict],
        max_posts: int | None = None,
        save_format: str = "both",
        filter_usernames: list[str] | None = None,
    ) -> list[dict]:
        """
        Extract detailed Reddit data for posts from gwasi data.

        Args:
            gwasi_data: List of gwasi entries
            max_posts: Maximum number of posts to process (for testing)
            save_format: 'csv', 'json', or 'both'
            filter_usernames: List of usernames to filter for (case-insensitive)

        Returns:
            List of enriched post data
        """
        if not self.reddit:
            raise Exception("Reddit API not initialized. Call setup_reddit() first.")

        # Pre-filter by username if requested
        if filter_usernames:
            print(f"🔍 Pre-filtering data for users: {filter_usernames}")
            filtered_data = []
            filter_usernames_lower = [u.lower() for u in filter_usernames]

            for entry in gwasi_data:
                username = entry.get("username", "").lower()
                if username in filter_usernames_lower:
                    filtered_data.append(entry)

            print(
                f"📊 After pre-filtering: {len(filtered_data)} posts (from {len(gwasi_data)} total)"
            )
            gwasi_data = filtered_data

        # Filter out existing posts and load them
        print("🔍 Checking for existing posts...")
        new_posts = []
        existing_posts = []

        for entry in gwasi_data:
            if self.post_exists(entry):
                existing_post = self.load_existing_post(entry)
                if existing_post:
                    existing_posts.append(existing_post)
            else:
                new_posts.append(entry)

        print(
            f"📊 Found {len(existing_posts)} existing posts, {len(new_posts)} new posts to process"
        )
        print("🚀 Starting Reddit data extraction for new posts...")

        enriched_data = existing_posts.copy()  # Start with existing posts
        failed_posts = []

        # Apply max_posts limit only to NEW posts
        posts_to_process = new_posts[:max_posts] if max_posts else new_posts

        if max_posts and len(new_posts) > max_posts:
            print(
                f"📊 Processing {len(posts_to_process)} new posts (limited by max-posts={max_posts})"
            )
        else:
            print(f"📊 Processing all {len(posts_to_process)} new posts")

        for i, gwasi_entry in enumerate(posts_to_process):
            print(
                f"📥 Processing post {i+1}/{len(posts_to_process)}: {gwasi_entry.get('post_id', 'unknown')}"
            )

            # Extract post ID from gwasi data
            post_id = gwasi_entry.get("post_id")
            if not post_id:
                # Try to extract from reddit_url if post_id is missing
                reddit_url = gwasi_entry.get("reddit_url")
                post_id = self.extract_post_id_from_url(reddit_url)
                if not post_id:
                    print(f"⚠️  No post ID found for entry {i+1}")
                    failed_posts.append(
                        {"gwasi_entry": gwasi_entry, "error": "No post ID found"}
                    )
                    continue

            # Get Reddit data
            reddit_data = self.get_post_data(post_id)
            if reddit_data:
                # Merge gwasi data with Reddit data
                enriched_entry = {
                    **gwasi_entry,  # Original gwasi data
                    "reddit_data": reddit_data,  # Detailed Reddit data
                }
                enriched_data.append(enriched_entry)

                # Save individual post as <username>/<post_id>.json
                self.save_individual_post(enriched_entry)

                print(f"✅ Successfully enriched post {post_id}")
            else:
                failed_posts.append(
                    {
                        "gwasi_entry": gwasi_entry,
                        "post_id": post_id,
                        "error": "Failed to fetch Reddit data",
                    }
                )
                print(f"❌ Failed to fetch data for post {post_id}")

        print("\n📊 Extraction Summary:")
        print(f"📂 Existing posts loaded: {len(existing_posts)}")
        print(
            f"🆕 New posts successfully processed: {len(enriched_data) - len(existing_posts)}"
        )
        print(f"✅ Total posts in dataset: {len(enriched_data)}")
        print(f"❌ Failed: {len(failed_posts)}")

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if save_format in ["csv", "both"]:
            self.save_to_csv(enriched_data, f"reddit_enriched_{timestamp}.csv")

        if save_format in ["json", "both"]:
            self.save_to_json(enriched_data, f"reddit_enriched_{timestamp}.json")

        # Save failed posts for debugging
        if failed_posts:
            self.save_to_json(failed_posts, f"failed_posts_{timestamp}.json")

        return enriched_data

    def save_to_csv(self, data: list[dict], filename: str):
        """Save enriched data to CSV file."""
        if not data:
            print("⚠️  No data to save")
            return

        filepath = self.output_dir / filename

        # Flatten the nested structure for CSV
        flattened_data = []
        for entry in data:
            flattened = {}

            # Add gwasi data (non-reddit_data fields)
            for key, value in entry.items():
                if key != "reddit_data":
                    flattened[f"gwasi_{key}"] = value

            # Add reddit data with prefix
            reddit_data = entry.get("reddit_data", {})
            for key, value in reddit_data.items():
                if key == "all_awardings":
                    # Convert awards to string representation
                    flattened[f"reddit_{key}"] = json.dumps(value) if value else ""
                else:
                    flattened[f"reddit_{key}"] = value

            flattened_data.append(flattened)

        try:
            # Get all possible columns
            all_columns = set()
            for entry in flattened_data:
                all_columns.update(entry.keys())

            columns = sorted(all_columns)

            with filepath.open("w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=columns)
                writer.writeheader()

                for entry in flattened_data:
                    # Ensure all columns are present
                    row = {col: entry.get(col, "") for col in columns}
                    writer.writerow(row)

            print(f"💾 Saved {len(data)} enriched entries to {filepath}")

        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")

    def save_to_json(self, data: list[dict], filename: str):
        """Save data to JSON file."""
        if not data:
            print("⚠️  No data to save")
            return

        filepath = self.output_dir / filename

        try:
            with filepath.open("w", encoding="utf-8") as jsonfile:
                json.dump(data, jsonfile, indent=2, ensure_ascii=False, default=str)

            print(f"💾 Saved {len(data)} entries to {filepath}")

        except Exception as e:
            print(f"❌ Error saving to JSON: {e}")

    def post_exists(self, gwasi_entry: dict) -> bool:
        """Check if individual post file already exists (checks both old and new filename formats)"""
        # Try to determine the expected author/username from the gwasi data
        username = gwasi_entry.get("username", "unknown")
        post_id = gwasi_entry.get("post_id")

        if not post_id:
            return False

        # Check in the original username directory
        if username and username not in ["[deleted]", "[suspended]", None]:
            user_dir = self.output_dir / username

            # Check for old format first
            old_filepath = user_dir / f"{post_id}.json"
            if old_filepath.exists():
                return True

            # Check for new format (any file starting with post_id_)
            if user_dir.exists():
                for _file in user_dir.glob(f"{post_id}_*.json"):
                    return True

        # Also check in deleted_users directory
        deleted_user_dir = self.output_dir / "deleted_users"

        # Check old format
        old_deleted_filepath = deleted_user_dir / f"{post_id}.json"
        if old_deleted_filepath.exists():
            return True

        # Check new format
        if deleted_user_dir.exists():
            for _file in deleted_user_dir.glob(f"{post_id}_*.json"):
                return True

        return False

    def load_existing_post(self, gwasi_entry: dict) -> dict | None:
        """Load existing individual post file if it exists (checks both old and new filename formats)"""
        username = gwasi_entry.get("username", "unknown")
        post_id = gwasi_entry.get("post_id")

        if not post_id:
            return None

        # Try original username directory first
        if username and username not in ["[deleted]", "[suspended]", None]:
            user_dir = self.output_dir / username

            # Try old format first
            old_filepath = user_dir / f"{post_id}.json"
            if old_filepath.exists():
                try:
                    with old_filepath.open(encoding="utf-8") as jsonfile:
                        return json.load(jsonfile)
                except Exception as e:
                    print(f"⚠️ Warning: Could not load existing post {old_filepath}: {e}")

            # Try new format (find any file starting with post_id_)
            if user_dir.exists():
                for filepath in user_dir.glob(f"{post_id}_*.json"):
                    try:
                        with filepath.open(encoding="utf-8") as jsonfile:
                            return json.load(jsonfile)
                    except Exception as e:
                        print(f"⚠️ Warning: Could not load existing post {filepath}: {e}")

        # Try deleted_users directory
        deleted_user_dir = self.output_dir / "deleted_users"

        # Try old format
        old_deleted_filepath = deleted_user_dir / f"{post_id}.json"
        if old_deleted_filepath.exists():
            try:
                with old_deleted_filepath.open(encoding="utf-8") as jsonfile:
                    return json.load(jsonfile)
            except Exception as e:
                print(
                    f"⚠️ Warning: Could not load existing post {old_deleted_filepath}: {e}"
                )

        # Try new format in deleted_users
        if deleted_user_dir.exists():
            for filepath in deleted_user_dir.glob(f"{post_id}_*.json"):
                try:
                    with filepath.open(encoding="utf-8") as jsonfile:
                        return json.load(jsonfile)
                except Exception as e:
                    print(
                        f"⚠️ Warning: Could not load existing post {filepath}: {e}"
                    )

        return None

    def save_individual_post(self, enriched_entry: dict):
        """Save individual post as <username>/<post_id>_<slug>.json"""
        reddit_data = enriched_entry.get("reddit_data", {})
        author = reddit_data.get("author", "unknown")
        post_id = reddit_data.get("post_id", "unknown")
        title = reddit_data.get("title", "")

        # Handle deleted/suspended users
        if author in ["[deleted]", "[suspended]", None]:
            author = "deleted_users"

        # Create username directory
        user_dir = self.output_dir / author
        user_dir.mkdir(exist_ok=True)

        # Create slug from title
        slug = self.create_slug(title)

        # Save post as JSON with new filename format
        filename = f"{post_id}_{slug}.json"
        filepath = user_dir / filename

        try:
            with filepath.open("w", encoding="utf-8") as jsonfile:
                json.dump(
                    enriched_entry, jsonfile, indent=2, ensure_ascii=False, default=str
                )
            print(f"💾 Saved individual post to {filepath}")
        except Exception as e:
            print(f"❌ Error saving individual post {post_id}: {e}")


def main():
    ensure_directories()
    parser = argparse.ArgumentParser(
        description="Extract detailed Reddit data using PRAW"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Reddit post URL/ID, or path to gwasi_extractor output file (CSV or JSON). "
             "If omitted, uses the latest gwasi_data_*.json file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(REDDIT_INDEX_DIR),
        help=f"Output directory (default: {REDDIT_INDEX_DIR})",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["csv", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--max-posts",
        "-m",
        type=int,
        help="Maximum number of posts to process (for testing)",
    )
    parser.add_argument(
        "--client-id", help="Reddit API client ID (or set REDDIT_CLIENT_ID env var)"
    )
    parser.add_argument(
        "--client-secret",
        help="Reddit API client secret (or set REDDIT_CLIENT_SECRET env var)",
    )
    parser.add_argument(
        "--user-agent", help="Reddit API user agent (or set REDDIT_USER_AGENT env var)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Delay between API requests in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--filter-users",
        help="Comma-separated list of usernames to filter for (case-insensitive)",
    )

    args = parser.parse_args()

    # Auto-detect latest gwasi data file if no input provided
    if args.input is None:
        latest_file = find_latest_gwasi_data()
        if latest_file is None:
            print("❌ No gwasi_data_*.json files found in index directory")
            print(f"   Expected location: {GWASI_INDEX_DIR}")
            return 1
        args.input = str(latest_file)
        print(f"📂 Using latest gwasi data: {latest_file.name}")

    try:
        # Initialize extractor
        extractor = RedditExtractor(args.output)
        extractor.request_delay = args.delay

        # Setup Reddit API
        print("🔧 Setting up Reddit API connection...")
        extractor.setup_reddit(
            client_id=args.client_id,
            client_secret=args.client_secret,
            user_agent=args.user_agent,
        )

        # Check if input is a Reddit URL/ID or a file
        input_path = Path(args.input)
        is_file = input_path.exists() and input_path.is_file()

        # Also check if it looks like a Reddit URL or post ID
        is_reddit_url = "reddit.com" in args.input or args.input.startswith("/r/")
        is_post_id = not is_file and not is_reddit_url and re.match(r"^[a-z0-9]+$", args.input, re.IGNORECASE)

        if is_reddit_url or is_post_id:
            # Single post mode
            if is_reddit_url:
                post_id = extractor.extract_post_id_from_url(args.input)
                if not post_id:
                    print(f"❌ Could not extract post ID from URL: {args.input}")
                    return 1
                print(f"🔗 Extracted post ID: {post_id} from URL")
            else:
                post_id = args.input
                print(f"📝 Using post ID: {post_id}")

            # Fetch the single post
            print(f"📥 Fetching Reddit post {post_id}...")
            reddit_data = extractor.get_post_data(post_id)

            if reddit_data:
                # Create enriched entry (minimal gwasi data for single post)
                enriched_entry = {
                    "post_id": post_id,
                    "reddit_url": f"https://www.reddit.com/comments/{post_id}",
                    "username": reddit_data.get("author", "unknown"),
                    "reddit_data": reddit_data,
                }

                # Save individual post
                extractor.save_individual_post(enriched_entry)

                print(f"\n✅ Successfully extracted post {post_id}")
                print(f"📁 Title: {reddit_data.get('title', 'N/A')}")
                print(f"👤 Author: {reddit_data.get('author', 'N/A')}")
                print(f"📊 Score: {reddit_data.get('score', 'N/A')}")
                print(f"💬 Comments: {reddit_data.get('num_comments', 'N/A')}")
            else:
                print(f"❌ Failed to fetch post {post_id}")
                return 1

            return 0

        # File mode - load gwasi data
        print(f"📂 Loading gwasi data from {args.input}...")
        gwasi_data = extractor.load_gwasi_data(args.input)

        # Parse filter usernames if provided
        filter_usernames = None
        if args.filter_users:
            filter_usernames = [u.strip() for u in args.filter_users.split(",")]
            print(f"🔍 Filtering for users: {filter_usernames}")

        # Extract Reddit data
        enriched_data = extractor.extract_reddit_data(
            gwasi_data,
            max_posts=args.max_posts,
            save_format=args.format,
            filter_usernames=filter_usernames,
        )

        print("\n🎉 Extraction complete!")
        print(f"📁 Results saved to: {extractor.output_dir}")
        print(f"📊 Processed {len(enriched_data)} posts successfully")

    except KeyboardInterrupt:
        print("\n⏹️  Extraction interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
