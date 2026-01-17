#!/usr/bin/env python3
"""
Script URL Extractor

This utility extracts script URLs from Reddit posts when they're referenced
indirectly (e.g., through Reddit shortlinks or in post content).
"""

import json
import os
import re
from pathlib import Path
import praw
from dotenv import load_dotenv


class ScriptUrlExtractor:
    def __init__(self):
        # Load environment variables
        load_dotenv()

        # Initialize Reddit instance
        self.reddit = None
        self.setup_reddit()

        # Common script hosting platforms
        self.script_platforms = [
            "scriptbin.works",
            "archiveofourown.org",
            "pastebin.com",
            "github.com",
            "gitlab.com",
            "docs.google.com",
            "drive.google.com",
            "rentry.co",
            "paste.ee"
        ]

        # Patterns for finding script links
        self.script_patterns = [
            r"\[Script\s*(?:Here|Link)?\]\s*\((https?://[^\)]+)\)",  # [Script Here](url)
            r"Script:\s*(https?://\S+)",  # Script: url
            r"Script\s*(?:link|url)?:\s*(https?://\S+)",  # Script link: url
            r"(?:Original\s+)?Script\s+by\s+.+?:\s*(https?://\S+)",  # Script by author: url
        ]

    def setup_reddit(self):
        """Setup Reddit API connection"""
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "ScriptUrlExtractor/1.0")

        if not client_id or not client_secret:
            print("Warning: Reddit API credentials not found. Script extraction from Reddit URLs will not work.")
            return

        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            print("Connected to Reddit API successfully")
        except Exception as e:
            print(f"Error: Failed to connect to Reddit API: {e}")

    def extract_reddit_post_id(self, url: str) -> str | None:
        """Extract post ID from various Reddit URL formats"""
        # Handle reddit.com/r/.../comments/ID/...
        match = re.search(r"/comments/([a-z0-9]+)/", url)
        if match:
            return match.group(1)

        # Handle redd.it/ID
        match = re.search(r"redd\.it/([a-z0-9]+)", url)
        if match:
            return match.group(1)

        # Handle reddit.com/s/ID (shortlinks)
        match = re.search(r"/s/([a-zA-Z0-9]+)", url)
        if match:
            # This is a shortlink, need to resolve it
            return self.resolve_reddit_shortlink(url)

        return None

    def resolve_reddit_shortlink(self, shortlink: str) -> str | None:
        """Resolve Reddit shortlink to get actual post ID"""
        if not self.reddit:
            print("Error: Cannot resolve shortlink without Reddit API connection")
            return None

        try:
            # Try to access the shortlink
            submission = self.reddit.submission(url=shortlink)
            return submission.id
        except Exception as e:
            print(f"Error: Failed to resolve shortlink {shortlink}: {e}")
            return None

    def extract_script_urls_from_text(self, text: str) -> list[tuple[str, str]]:
        """Extract script URLs from text content

        Returns list of tuples: (url, context)
        """
        script_urls = []

        # Check each pattern
        for pattern in self.script_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.group(1)
                context = match.group(0)
                script_urls.append((url, context))

        # Also look for any URL that contains known script platforms
        url_pattern = r"https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        all_urls = re.findall(url_pattern, text)

        for url in all_urls:
            # Clean up malformed URLs (remove trailing ](url) pattern)
            cleaned_url = re.sub(r"\]\([^)]*\)$", "", url)

            for platform in self.script_platforms:
                if platform in cleaned_url and cleaned_url not in [u[0] for u in script_urls]:
                    script_urls.append((cleaned_url, f"Platform URL: {cleaned_url}"))
                    break

        return script_urls

    def extract_script_info_from_reddit_post(self, post_id: str) -> dict | None:
        """Extract script information from a Reddit post"""
        if not self.reddit:
            print("Error: Cannot fetch Reddit post without API connection")
            return None

        try:
            submission = self.reddit.submission(id=post_id)

            # Get post content
            post_text = submission.selftext

            # Extract script URLs from post content
            script_urls = self.extract_script_urls_from_text(post_text)

            # Look for script author mentions
            script_author = None
            author_patterns = [
                r"(?:script\s+)?(?:by|written\s+by|author:?)\s+/?u/([a-zA-Z0-9_-]+)",
                r"(?:wonderful|amazing|great)\s+/?u/([a-zA-Z0-9_-]+)",
            ]

            for pattern in author_patterns:
                match = re.search(pattern, post_text, re.IGNORECASE)
                if match:
                    script_author = match.group(1)
                    break

            # Check if any found URLs are Reddit posts (potential script posts)
            resolved_urls = []
            for url, context in script_urls:
                if "reddit.com" in url or "redd.it" in url:
                    # This might be a link to the script post
                    script_post_id = self.extract_reddit_post_id(url)
                    if script_post_id:
                        # Fetch the linked post
                        try:
                            script_submission = self.reddit.submission(id=script_post_id)

                            # Extract script URLs from the linked post
                            linked_script_urls = self.extract_script_urls_from_text(script_submission.selftext)

                            resolved_urls.append({
                                "original_url": url,
                                "resolved_post_id": script_post_id,
                                "resolved_title": script_submission.title,
                                "resolved_author": str(script_submission.author) if script_submission.author else None,
                                "script_urls": linked_script_urls
                            })
                        except Exception as e:
                            print(f"Warning: Failed to fetch linked post {script_post_id}: {e}")
                else:
                    resolved_urls.append({
                        "url": url,
                        "context": context,
                        "is_direct_script_url": True
                    })

            return {
                "post_id": post_id,
                "direct_script_urls": script_urls,
                "resolved_urls": resolved_urls,
                "script_author": script_author,
                "post_title": submission.title,
                "post_author": str(submission.author) if submission.author else None
            }

        except Exception as e:
            print(f"Error: Failed to extract script info from post {post_id}: {e}")
            return None

    def update_analysis_with_script_url(self, analysis_file: Path, script_info: dict):
        """Update an existing analysis file with script URL information"""
        try:
            # Load existing analysis
            with open(analysis_file, encoding="utf-8") as f:
                analysis = json.load(f)

            # Update script section
            if "script" not in analysis:
                analysis["script"] = {}

            # Add extracted URLs
            if script_info["direct_script_urls"]:
                analysis["script"]["extracted_urls"] = script_info["direct_script_urls"]

            if script_info["resolved_urls"]:
                analysis["script"]["resolved_urls"] = script_info["resolved_urls"]

            if script_info["script_author"]:
                analysis["script"]["author"] = script_info["script_author"]

            # Determine the primary script URL
            primary_url = None

            # First check direct script platform URLs
            for url_info in script_info["resolved_urls"]:
                if url_info.get("is_direct_script_url"):
                    primary_url = url_info["url"]
                    break

            # Then check resolved Reddit posts for script URLs
            if not primary_url:
                for url_info in script_info["resolved_urls"]:
                    if "script_urls" in url_info and url_info["script_urls"]:
                        primary_url = url_info["script_urls"][0][0]
                        break

            if primary_url:
                analysis["script"]["url"] = primary_url

            # Save updated analysis
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)

            print(f"Success: Updated {analysis_file} with script information")

        except Exception as e:
            print(f"Error: Failed to update analysis file: {e}")


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Extract script URLs from Reddit posts")
    parser.add_argument("post_id", help="Reddit post ID to analyze")
    parser.add_argument("--update-analysis", help="Path to analysis file to update")

    args = parser.parse_args()

    extractor = ScriptUrlExtractor()

    print(f"Extracting script info from post {args.post_id}...")
    script_info = extractor.extract_script_info_from_reddit_post(args.post_id)

    if script_info:
        print("\nScript Information:")
        print("Post Title:", script_info["post_title"].encode("ascii", "ignore").decode("ascii"))
        print(f"Post Author: {script_info['post_author']}")

        if script_info["script_author"]:
            print(f"Script Author: u/{script_info['script_author']}")

        if script_info["direct_script_urls"]:
            print("\nDirect Script URLs found:")
            for url, context in script_info["direct_script_urls"]:
                print(f"  - {url}")
                print(f"    Context: {context}")

        if script_info["resolved_urls"]:
            print("\nResolved URLs:")
            for url_info in script_info["resolved_urls"]:
                if url_info.get("is_direct_script_url"):
                    print(f"  - {url_info['url']} (Direct script URL)")
                else:
                    print(f"  - {url_info['original_url']} -> Reddit post {url_info['resolved_post_id']}")
                    print(f"    Title: {url_info['resolved_title']}")
                    if url_info["script_urls"]:
                        print("    Script URLs in linked post:")
                        for script_url, context in url_info["script_urls"]:
                            print(f"      - {script_url}")

        # Update analysis file if requested
        if args.update_analysis:
            analysis_path = Path(args.update_analysis)
            if analysis_path.exists():
                extractor.update_analysis_with_script_url(analysis_path, script_info)
            else:
                print(f"Error: Analysis file not found: {args.update_analysis}")
    else:
        print("Error: Failed to extract script information")


if __name__ == "__main__":
    main()
