#!/usr/bin/env python3
"""
SnakeySmut Website Extractor

Extracts audio post metadata from snakeysmut.com including titles, tags,
script credits, and platform availability links.

Two-phase extraction:
1. Scrape listing pages to get all post URLs
2. Scrape each post page for full metadata

Usage:
    uv run python snakeysmut_extractor.py              # Extract all posts
    uv run python snakeysmut_extractor.py --limit 10   # Test with 10 posts
    uv run python snakeysmut_extractor.py --page 5     # Start from specific page
"""

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from config import SNAKEYSMUT_DIR


class SnakeySmutExtractor:
    BASE_URL = "https://www.snakeysmut.com"
    LISTING_URL = "https://www.snakeysmut.com/audiossnakeysmut"

    def __init__(self, request_delay: float = 1.0):
        self.request_delay = request_delay
        self.last_request_time = 0
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            follow_redirects=True,
            timeout=30.0,
        )
        self.posts_dir = SNAKEYSMUT_DIR / "posts"
        self.posts_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def ensure_rate_limit(self):
        """Ensure rate limiting between requests."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_delay:
            sleep_time = self.request_delay - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def fetch_page(self, url: str) -> str:
        """Fetch a page with rate limiting."""
        self.ensure_rate_limit()
        print(f"  Fetching: {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def resolve_bitly(self, url: str) -> str:
        """Resolve bit.ly or other shortened URLs to their destination."""
        if not url:
            return url

        parsed = urlparse(url)
        shortener_domains = ["bit.ly", "bitly.com", "t.co", "tinyurl.com", "goo.gl"]

        if parsed.netloc not in shortener_domains:
            return url

        try:
            self.ensure_rate_limit()
            response = self.client.head(url, follow_redirects=True)
            return str(response.url)
        except Exception as e:
            print(f"    Warning: Could not resolve {url}: {e}")
            return url

    def get_listing_page_count(self) -> int:
        """Determine the total number of listing pages."""
        html = self.fetch_page(self.LISTING_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Look for pagination links
        pagination_links = soup.select('a[href*="/audiossnakeysmut/page/"]')
        max_page = 1

        for link in pagination_links:
            href = link.get("href", "")
            match = re.search(r"/page/(\d+)", href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)

        return max_page

    def extract_post_urls_from_listing(self, page_num: int) -> list[dict]:
        """Extract post URLs and categories from a listing page."""
        url = self.LISTING_URL if page_num == 1 else f"{self.LISTING_URL}/page/{page_num}"
        html = self.fetch_page(url)
        soup = BeautifulSoup(html, "html.parser")

        posts = []
        # Find post links - look for links to /post/ URLs
        post_links = soup.select('a[href*="/post/"]')
        seen_urls = set()

        for link in post_links:
            href = link.get("href", "")
            if "/post/" not in href:
                continue

            # Make absolute URL
            full_url = urljoin(self.BASE_URL, href)

            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Try to determine category from surrounding context
            category = self.extract_category_from_context(link)

            posts.append({"url": full_url, "category": category})

        return posts

    def extract_category_from_context(self, element) -> str | None:
        """Try to determine post category from surrounding HTML context."""
        # Look for category indicators in parent elements
        current = element
        for _ in range(5):  # Check up to 5 parent levels
            parent = current.parent
            if parent is None:
                break

            text = parent.get_text(strip=True).lower()
            if "premium nsfw" in text:
                return "premium nsfw"
            if "free nsfw" in text:
                return "free nsfw"

            current = parent

        return None

    def extract_post(self, url: str, category: str | None = None) -> dict:
        """Extract full metadata from a post page."""
        html = self.fetch_page(url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract slug from URL
        slug = url.rstrip("/").split("/")[-1]

        # Extract title from h1
        title_elem = soup.select_one("h1")
        title = title_elem.get_text(strip=True) if title_elem else slug

        # Extract script credit
        script_credit = self.extract_script_credit(soup)

        # Extract raw description text (preserve original for reference)
        description = self.extract_description(soup)

        # Extract platform links from "Listen Here" section
        platforms = self.extract_platforms(soup)

        # Extract inline tags from description [tag] format
        inline_tags = self.extract_inline_tags(soup)

        # Extract Wix structured tags
        wix_tags = self.extract_wix_tags(soup)

        # Try to determine category from page if not provided
        if not category:
            category = self.extract_category_from_page(soup)

        return {
            "url": url,
            "slug": slug,
            "title": title,
            "description": description,
            "script_credit": script_credit,
            "platforms": platforms,
            "inline_tags": inline_tags,
            "wix_tags": wix_tags,
            "category": category,
            "scraped_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    def extract_script_credit(self, soup: BeautifulSoup) -> dict | None:
        """Extract script credit information."""
        # Look for script credit section - typically contains author and type
        text = soup.get_text()

        # Match author in format u/username
        author_match = re.search(r"(?:Script\s*(?:by|Credit)?:?\s*)?u/(\w+)", text, re.I)
        author = f"u/{author_match.group(1)}" if author_match else None

        # Look for script type
        script_type = None
        if "private script" in text.lower():
            script_type = "Private Script"
        elif "public script" in text.lower():
            script_type = "Public Script"

        if author or script_type:
            return {"author": author, "type": script_type}
        return None

    def extract_description(self, soup: BeautifulSoup) -> str:
        """Extract the main description/body text from the post."""
        # Try to find the main content area - Wix sites often use specific containers
        # Look for common content containers
        content_selectors = [
            '[data-testid="richTextElement"]',
            ".font_8",  # Common Wix text class
            "article",
            ".post-content",
            '[class*="content"]',
        ]

        for selector in content_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(separator="\n", strip=True)
                # Look for text that contains tags in brackets - likely the description
                if "[" in text and "]" in text and len(text) > 50:
                    return text

        # Fallback: get all text but try to exclude navigation/headers
        main_text = soup.get_text(separator="\n", strip=True)
        return main_text

    def extract_platforms(self, soup: BeautifulSoup) -> list[dict]:
        """Extract platform links from Listen Here section."""
        platforms = []
        platform_names = [
            "pornhub",
            "newgrounds",
            "soundgasm",
            "xhamster",
            "erocast",
            "youtube",
            "spotify",
            "patreon",
            "reddit",
        ]

        # Find all links in the page
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            link_text = link.get_text(strip=True).lower()

            # Skip internal site links (tag pages, category pages)
            if "/tags/" in href or "/audiossnakeysmut" in href:
                continue

            # Check if this looks like a platform link
            for platform in platform_names:
                if platform in href.lower() or platform in link_text:
                    # Resolve shortened URLs
                    resolved_url = self.resolve_bitly(href)
                    platforms.append(
                        {"name": platform.capitalize(), "url": resolved_url}
                    )
                    break
            else:
                # Check for bit.ly links that might be platform links
                if "bit.ly" in href or "bitly" in href:
                    resolved_url = self.resolve_bitly(href)
                    # Try to determine platform from resolved URL
                    platform_name = self.identify_platform(resolved_url)
                    if platform_name:
                        platforms.append({"name": platform_name, "url": resolved_url})

        # Deduplicate by URL
        seen = set()
        unique_platforms = []
        for p in platforms:
            if p["url"] not in seen:
                seen.add(p["url"])
                unique_platforms.append(p)

        return unique_platforms

    def identify_platform(self, url: str) -> str | None:
        """Identify platform from URL."""
        platform_domains = {
            "pornhub.com": "Pornhub",
            "newgrounds.com": "Newgrounds",
            "soundgasm.net": "Soundgasm",
            "xhamster.com": "xHamster",
            "erocast.me": "Erocast",
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "spotify.com": "Spotify",
            "patreon.com": "Patreon",
        }

        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")

        for domain_pattern, name in platform_domains.items():
            if domain_pattern in domain:
                return name

        return None

    def extract_inline_tags(self, soup: BeautifulSoup) -> list[str]:
        """Extract tags in [tag] format from description text."""
        text = soup.get_text()
        tag_pattern = re.compile(r"\[([^\]]+)\]")
        tags = tag_pattern.findall(text)

        # Filter and deduplicate while preserving order
        skip_patterns = ["script fill", "listen here", "click here"]
        seen = set()
        filtered_tags = []
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower not in skip_patterns and len(tag) < 50 and tag_lower not in seen:
                seen.add(tag_lower)
                filtered_tags.append(tag)

        return filtered_tags

    def extract_wix_tags(self, soup: BeautifulSoup) -> list[str]:
        """Extract structured tags from Wix navigation/tag elements."""
        tags = []

        # Find links to tag pages (format: /audiossnakeysmut/tags/*)
        tag_links = soup.select('a[href*="/tags/"]')
        for link in tag_links:
            href = link.get("href", "")
            # Only include actual tag page links, not category or other pages
            if "/audiossnakeysmut/tags/" in href:
                tag_text = link.get_text(strip=True)
                if tag_text and len(tag_text) < 50:
                    tags.append(tag_text)

        # Also look for hashtag-style links
        hashtag_links = soup.select('a[href*="/hashtag/"]')
        for link in hashtag_links:
            tag_text = link.get_text(strip=True).lstrip("#")
            if tag_text:
                tags.append(tag_text)

        # Deduplicate while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique_tags.append(tag)

        return unique_tags

    def extract_category_from_page(self, soup: BeautifulSoup) -> str | None:
        """Try to determine category from the post page itself."""
        text = soup.get_text().lower()
        if "premium nsfw" in text:
            return "premium nsfw"
        if "free nsfw" in text:
            return "free nsfw"
        return None

    def is_already_scraped(self, slug: str) -> bool:
        """Check if a post has already been scraped."""
        json_path = self.posts_dir / f"{slug}.json"
        return json_path.exists()

    def save_post(self, post_data: dict):
        """Save post data to JSON file."""
        slug = post_data["slug"]
        json_path = self.posts_dir / f"{slug}.json"
        json_path.write_text(
            json.dumps(post_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def save_index(self, posts: list[dict]):
        """Save index of all posts."""
        index_path = SNAKEYSMUT_DIR / "index.json"
        index_data = {
            "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "total_posts": len(posts),
            "posts": [
                {"url": p["url"], "slug": p["slug"], "title": p.get("title", "")}
                for p in posts
            ],
        }
        index_path.write_text(
            json.dumps(index_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def discover_posts(self, start_page: int, limit: int | None) -> list[dict]:
        """Phase 1: Discover all post URLs from listing pages."""
        print("\nPhase 1: Discovering posts from listing pages...")
        total_pages = self.get_listing_page_count()
        print(f"  Found {total_pages} pages of posts")

        all_post_refs = []
        for page_num in range(start_page, total_pages + 1):
            print(f"\n  Scanning page {page_num}/{total_pages}...")
            posts = self.extract_post_urls_from_listing(page_num)
            all_post_refs.extend(posts)
            print(f"    Found {len(posts)} posts on this page")

            if limit and len(all_post_refs) >= limit:
                return all_post_refs[:limit]

        return all_post_refs

    def extract_all_posts(self, post_refs: list[dict], skip_existing: bool) -> tuple[list[dict], int, int]:
        """Phase 2: Extract full metadata from each post."""
        print("\nPhase 2: Extracting post metadata...")
        extracted_posts = []
        skipped = 0
        failed = 0

        for i, post_ref in enumerate(post_refs, 1):
            url = post_ref["url"]
            slug = url.rstrip("/").split("/")[-1]
            print(f"\n[{i}/{len(post_refs)}] {slug}")

            if skip_existing and self.is_already_scraped(slug):
                print("  Skipped (already scraped)")
                skipped += 1
                existing = self.load_existing_post(slug)
                if existing:
                    extracted_posts.append(existing)
                continue

            try:
                post_data = self.extract_post(url, post_ref.get("category"))
                self.save_post(post_data)
                extracted_posts.append(post_data)
                self.print_post_summary(post_data)
            except Exception as e:
                print(f"  ERROR: {e}")
                failed += 1

        return extracted_posts, skipped, failed

    def load_existing_post(self, slug: str) -> dict | None:
        """Load existing post data from cache."""
        json_path = self.posts_dir / f"{slug}.json"
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def print_post_summary(self, post_data: dict):
        """Print summary of extracted post."""
        print(f"  Title: {post_data['title']}")
        print(f"  Platforms: {len(post_data['platforms'])}")
        print(f"  Tags: {len(post_data['inline_tags'])} inline, {len(post_data['wix_tags'])} wix")

    def run(self, limit: int | None = None, start_page: int = 1, skip_existing: bool = True):
        """
        Run the full extraction process.

        Args:
            limit: Maximum number of posts to extract (None for all)
            start_page: Page number to start from
            skip_existing: Skip posts that have already been scraped
        """
        print("SnakeySmut Extractor")
        print("=" * 50)

        all_post_refs = self.discover_posts(start_page, limit)
        print(f"\nDiscovered {len(all_post_refs)} total post URLs")

        extracted_posts, skipped, failed = self.extract_all_posts(all_post_refs, skip_existing)

        print("\nSaving index...")
        self.save_index(extracted_posts)

        # Summary
        print("\n" + "=" * 50)
        print("Extraction Complete")
        print(f"  Total discovered: {len(all_post_refs)}")
        print(f"  Extracted: {len(extracted_posts) - skipped}")
        print(f"  Skipped (existing): {skipped}")
        print(f"  Failed: {failed}")
        print(f"  Output directory: {SNAKEYSMUT_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio post metadata from snakeysmut.com"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Maximum number of posts to extract",
    )
    parser.add_argument(
        "--page",
        "-p",
        type=int,
        default=1,
        help="Start from specific listing page (default: 1)",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-extract posts even if already scraped",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    extractor = SnakeySmutExtractor(request_delay=args.delay)
    try:
        extractor.run(
            limit=args.limit,
            start_page=args.page,
            skip_existing=not args.no_skip,
        )
        return 0
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        return 1
    finally:
        extractor.close()


if __name__ == "__main__":
    sys.exit(main())
