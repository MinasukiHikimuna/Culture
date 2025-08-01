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

import praw
import json
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import os
from urllib.parse import urlparse
from dotenv import load_dotenv


class RedditExtractor:
    def __init__(self, output_dir: str = "reddit_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize Reddit instance (will be set up in setup_reddit)
        self.reddit = None

        # Rate limiting
        self.request_delay = 1.0  # Seconds between requests
        self.last_request_time = 0

    def setup_reddit(
        self, client_id: str = None, client_secret: str = None, user_agent: str = None
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
            print(f"✅ Connected to Reddit as read-only user")
            print(f"🔧 User agent: {user_agent}")

        except Exception as e:
            raise Exception(f"Failed to connect to Reddit API: {e}")

    def rate_limit(self):
        """Simple rate limiting to be respectful to Reddit API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            sleep_time = self.request_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def extract_post_id_from_url(self, reddit_url: str) -> Optional[str]:
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

    def get_post_data(self, post_id: str) -> Optional[Dict]:
        """
        Fetch detailed data for a single Reddit post.

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

            post_data = {
                "post_id": submission.id,
                "title": submission.title,
                "selftext": submission.selftext,
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
            }

            return post_data

        except Exception as e:
            print(f"❌ Error fetching post {post_id}: {e}")
            return None

    def load_gwasi_data(self, gwasi_file: str) -> List[Dict]:
        """Load gwasi extractor output data."""
        gwasi_path = Path(gwasi_file)

        if not gwasi_path.exists():
            raise FileNotFoundError(f"Gwasi data file not found: {gwasi_file}")

        if gwasi_path.suffix.lower() == ".csv":
            return self.load_gwasi_csv(gwasi_path)
        elif gwasi_path.suffix.lower() == ".json":
            return self.load_gwasi_json(gwasi_path)
        else:
            raise ValueError(f"Unsupported file format: {gwasi_path.suffix}")

    def load_gwasi_csv(self, csv_path: Path) -> List[Dict]:
        """Load gwasi data from CSV file."""
        data = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            print(f"📂 Loaded {len(data)} entries from {csv_path}")
            return data
        except Exception as e:
            raise Exception(f"Error loading CSV file {csv_path}: {e}")

    def load_gwasi_json(self, json_path: Path) -> List[Dict]:
        """Load gwasi data from JSON file."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"📂 Loaded {len(data)} entries from {json_path}")
            return data
        except Exception as e:
            raise Exception(f"Error loading JSON file {json_path}: {e}")

    def extract_reddit_data(
        self,
        gwasi_data: List[Dict],
        max_posts: Optional[int] = None,
        save_format: str = "both",
        filter_usernames: Optional[List[str]] = None,
    ) -> List[Dict]:
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
            
            print(f"📊 After pre-filtering: {len(filtered_data)} posts (from {len(gwasi_data)} total)")
            gwasi_data = filtered_data

        print(f"🚀 Starting Reddit data extraction for {len(gwasi_data)} posts...")

        enriched_data = []
        failed_posts = []

        posts_to_process = gwasi_data[:max_posts] if max_posts else gwasi_data

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

        print(f"\n📊 Extraction Summary:")
        print(f"✅ Successfully processed: {len(enriched_data)}")
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

    def save_to_csv(self, data: List[Dict], filename: str):
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

            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=columns)
                writer.writeheader()

                for entry in flattened_data:
                    # Ensure all columns are present
                    row = {col: entry.get(col, "") for col in columns}
                    writer.writerow(row)

            print(f"💾 Saved {len(data)} enriched entries to {filepath}")

        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")

    def save_to_json(self, data: List[Dict], filename: str):
        """Save data to JSON file."""
        if not data:
            print("⚠️  No data to save")
            return

        filepath = self.output_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as jsonfile:
                json.dump(data, jsonfile, indent=2, ensure_ascii=False, default=str)

            print(f"💾 Saved {len(data)} entries to {filepath}")

        except Exception as e:
            print(f"❌ Error saving to JSON: {e}")

    def save_individual_post(self, enriched_entry: Dict):
        """Save individual post as <username>/<post_id>.json"""
        reddit_data = enriched_entry.get("reddit_data", {})
        author = reddit_data.get("author", "unknown")
        post_id = reddit_data.get("post_id", "unknown")
        
        # Handle deleted/suspended users
        if author in ["[deleted]", "[suspended]", None]:
            author = "deleted_users"
        
        # Create username directory
        user_dir = self.output_dir / author
        user_dir.mkdir(exist_ok=True)
        
        # Save post as JSON
        filename = f"{post_id}.json"
        filepath = user_dir / filename
        
        try:
            with open(filepath, "w", encoding="utf-8") as jsonfile:
                json.dump(enriched_entry, jsonfile, indent=2, ensure_ascii=False, default=str)
            print(f"💾 Saved individual post to {filepath}")
        except Exception as e:
            print(f"❌ Error saving individual post {post_id}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract detailed Reddit data using PRAW"
    )
    parser.add_argument(
        "gwasi_file", help="Path to gwasi_extractor output file (CSV or JSON)"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="reddit_data",
        help="Output directory (default: reddit_data)",
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
        default=1.0,
        help="Delay between API requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--filter-users",
        help="Comma-separated list of usernames to filter for (case-insensitive)",
    )

    args = parser.parse_args()

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

        # Load gwasi data
        print(f"📂 Loading gwasi data from {args.gwasi_file}...")
        gwasi_data = extractor.load_gwasi_data(args.gwasi_file)

        # Parse filter usernames if provided
        filter_usernames = None
        if args.filter_users:
            filter_usernames = [u.strip() for u in args.filter_users.split(",")]
            print(f"🔍 Filtering for users: {filter_usernames}")

        # Extract Reddit data
        enriched_data = extractor.extract_reddit_data(
            gwasi_data, max_posts=args.max_posts, save_format=args.format, filter_usernames=filter_usernames
        )

        print(f"\n🎉 Extraction complete!")
        print(f"📁 Results saved to: {extractor.output_dir}")
        print(f"📊 Processed {len(enriched_data)} posts successfully")

    except KeyboardInterrupt:
        print("\n⏹️  Extraction interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
