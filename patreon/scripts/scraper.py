#!/usr/bin/env python3
"""
Example Patreon scraper script demonstrating magic cells usage with requests and polars.
"""

# %% [markdown]
# # Patreon Content Scraper Example
#
# This script demonstrates how to scrape content from Patreon using:
# - requests for HTTP requests
# - polars for data manipulation
# - magic cells for interactive development
# - Developer Tools captured data analysis

# %% Import required libraries
import requests
import polars as pl
from pathlib import Path
import json
import time
import re
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse
import hashlib
from datetime import datetime

# %% Configuration
BASE_URL = "https://www.patreon.com/api"
DATA_DIR = Path("data")
MEDIA_DIR = Path("media")
CAPTURED_DIR = Path("captured")

# Create directories
for dir_path in [DATA_DIR, MEDIA_DIR, CAPTURED_DIR]:
    dir_path.mkdir(exist_ok=True)

# Rate limiting configuration
REQUEST_DELAY = 1.0  # seconds between requests

# %% [markdown]
# ## Developer Tools Data Analysis


# %% HAR file support
def load_har_file(filepath: Union[str, Path]) -> List[Dict]:
    """
    Load and parse a HAR (HTTP Archive) file to extract Patreon API requests.

    Args:
        filepath: Path to the HAR file

    Returns:
        List of extracted request/response pairs for Patreon API calls
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"HAR file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        har_data = json.load(f)

    if "log" not in har_data or "entries" not in har_data["log"]:
        raise ValueError("Invalid HAR file format")

    patreon_requests = []

    for entry in har_data["log"]["entries"]:
        request = entry.get("request", {})
        response = entry.get("response", {})

        url = request.get("url", "")

        # Filter for Patreon API requests
        if (
            "patreon.com/api" in url
            and response.get("status") == 200
            and "content" in response
            and response["content"].get("mimeType")
            in ["application/json", "application/vnd.api+json"]
        ):

            # Extract headers as dict
            headers = {}
            for header in request.get("headers", []):
                headers[header["name"]] = header["value"]

            # Extract response content
            content_text = response["content"].get("text", "")
            if content_text:
                try:
                    content_json = json.loads(content_text)

                    patreon_requests.append(
                        {
                            "url": url,
                            "method": request.get("method", "GET"),
                            "headers": headers,
                            "response_data": content_json,
                            "status": response.get("status"),
                            "timestamp": entry.get("startedDateTime"),
                        }
                    )
                except json.JSONDecodeError:
                    continue

    print(f"Found {len(patreon_requests)} Patreon API requests in HAR file")
    return patreon_requests


# %% Find posts requests in HAR
def find_posts_request(har_requests: List[Dict]) -> Optional[Dict]:
    """
    Find the best posts request from HAR data.

    Args:
        har_requests: List of HAR request/response pairs

    Returns:
        The best posts request data or None
    """
    posts_requests = []

    for req in har_requests:
        url = req["url"]
        data = req["response_data"]

        # Look for posts endpoints
        if (
            "posts" in url
            and isinstance(data, dict)
            and "data" in data
            and data["data"]
        ):

            # Count posts in response
            data_items = (
                data["data"] if isinstance(data["data"], list) else [data["data"]]
            )
            posts_requests.append(
                {
                    "request": req,
                    "post_count": len(data_items),
                    "has_pagination": "meta" in data or "links" in data,
                }
            )

    if not posts_requests:
        print("No posts requests found in HAR file")
        return None

    # Sort by post count and pagination presence
    posts_requests.sort(
        key=lambda x: (x["post_count"], x["has_pagination"]), reverse=True
    )

    best_request = posts_requests[0]
    print(f"Selected posts request with {best_request['post_count']} posts")
    print(f"URL: {best_request['request']['url']}")

    return best_request["request"]


# %% Analyze captured data (updated for HAR support)
def analyze_captured_data(filepath: Union[str, Path]) -> Dict:
    """
    Analyze captured data from Developer Tools to understand API structure.
    Supports both JSON and HAR formats.

    Args:
        filepath: Path to the captured JSON or HAR file

    Returns:
        Dict containing analysis results including pagination info
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"Captured data file not found: {filepath}")

    # Determine file type and load data
    if filepath.suffix.lower() == ".har":
        print("Loading HAR file...")
        har_requests = load_har_file(filepath)

        if not har_requests:
            raise ValueError("No Patreon API requests found in HAR file")

        # Find the best posts request
        posts_request = find_posts_request(har_requests)
        if not posts_request:
            raise ValueError("No posts data found in HAR file")

        data = posts_request["response_data"]
        headers = posts_request["headers"]

        print(f"Using request: {posts_request['url']}")

    else:
        print("Loading JSON file...")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        headers = {}

    analysis = {
        "total_items": 0,
        "pagination_info": {},
        "media_urls": [],
        "post_structure": {},
        "api_endpoints": [],
        "headers_required": headers,
        "base_url": "",
    }

    # Analyze structure based on common Patreon API patterns
    if isinstance(data, dict):
        # Extract pagination information
        if "meta" in data and "pagination" in data["meta"]:
            analysis["pagination_info"] = data["meta"]["pagination"]
        elif "links" in data:
            analysis["pagination_info"] = data["links"]

        # Extract data items
        if "data" in data:
            items = data["data"] if isinstance(data["data"], list) else [data["data"]]
            analysis["total_items"] = len(items)

            # Analyze first item structure for posts
            if items:
                first_item = items[0]
                analysis["post_structure"] = {
                    "type": first_item.get("type"),
                    "attributes_keys": (
                        list(first_item.get("attributes", {}).keys())
                        if "attributes" in first_item
                        else []
                    ),
                    "relationships_keys": (
                        list(first_item.get("relationships", {}).keys())
                        if "relationships" in first_item
                        else []
                    ),
                }

                # Extract media URLs from attributes
                for item in items:
                    if "attributes" in item:
                        attrs = item["attributes"]
                        # Look for media in various fields
                        for field in [
                            "image",
                            "thumbnail",
                            "video",
                            "audio",
                            "attachment",
                        ]:
                            if field in attrs and attrs[field]:
                                if (
                                    isinstance(attrs[field], dict)
                                    and "url" in attrs[field]
                                ):
                                    analysis["media_urls"].append(attrs[field]["url"])
                                elif isinstance(attrs[field], str) and attrs[
                                    field
                                ].startswith("http"):
                                    analysis["media_urls"].append(attrs[field])

        # Look for included media in relationships
        if "included" in data:
            for included_item in data["included"]:
                if (
                    included_item.get("type") in ["media", "attachment"]
                    and "attributes" in included_item
                ):
                    attrs = included_item["attributes"]
                    if "download_url" in attrs:
                        analysis["media_urls"].append(attrs["download_url"])
                    elif "file_name" in attrs and "url" in attrs:
                        analysis["media_urls"].append(attrs["url"])

    print(f"Analysis Results:")
    print(f"- Total items found: {analysis['total_items']}")
    print(f"- Media URLs found: {len(analysis['media_urls'])}")
    print(f"- Pagination info: {analysis['pagination_info']}")
    print(f"- Post structure: {analysis['post_structure']}")
    print(f"- Headers captured: {len(analysis['headers_required'])} headers")

    return analysis


# %% Extract pagination URLs
def extract_pagination_urls(captured_data: Dict) -> List[str]:
    """Extract all page URLs for complete data collection."""

    urls = []
    pagination_info = captured_data.get("pagination_info", {})

    # Handle different pagination patterns
    if "cursors" in pagination_info:
        # Cursor-based pagination
        next_cursor = pagination_info["cursors"].get("after")
        if next_cursor:
            # You'll need to construct the full URL based on the original request
            # This is a template - adjust based on actual API structure
            base_url = "https://www.patreon.com/api/posts"  # Adjust this
            urls.append(f"{base_url}?page[cursor]={next_cursor}")

    elif "next" in pagination_info:
        # Direct next URL
        next_url = pagination_info["next"]
        if next_url:
            urls.append(next_url)

    elif "links" in pagination_info:
        # Links-based pagination
        if "next" in pagination_info["links"]:
            urls.append(pagination_info["links"]["next"])

    return urls


# %% [markdown]
# ## Enhanced Scraping Functions


# %% Helper functions


def get_existing_post_ids(creator_name: str) -> set:
    """Get all post IDs from existing scraped files to detect duplicates."""
    existing_ids = set()

    if not DATA_DIR.exists():
        return existing_ids

    # Look for complete page files (new format)
    patterns = [
        f"{creator_name}_complete_cursor_*.json",
        f"{creator_name}_complete_page_*.json",
        f"{creator_name}_complete.json",
    ]

    for pattern in patterns:
        for filepath in DATA_DIR.glob(pattern):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    file_data = json.load(f)

                # Handle complete page format
                if "api_response" in file_data:
                    api_response = file_data["api_response"]
                    if "data" in api_response:
                        posts = api_response["data"]
                        if not isinstance(posts, list):
                            posts = [posts]

                        # Extract post IDs
                        for post in posts:
                            if isinstance(post, dict) and "id" in post:
                                existing_ids.add(post["id"])

                # Handle complete dataset format
                elif "data" in file_data and isinstance(file_data["data"], list):
                    posts = file_data["data"]
                    for post in posts:
                        if isinstance(post, dict) and "id" in post:
                            existing_ids.add(post["id"])

            except (json.JSONDecodeError, KeyError):
                continue

    print(f"Found {len(existing_ids)} existing post IDs")
    return existing_ids


def check_for_duplicate_posts(new_posts: List[Dict], existing_ids: set) -> tuple:
    """
    Check if any new posts already exist in our scraped data.

    Returns:
        (new_posts_only, duplicate_count, should_stop)
    """
    new_posts_only = []
    duplicate_count = 0

    for post in new_posts:
        if isinstance(post, dict) and "id" in post:
            if post["id"] in existing_ids:
                duplicate_count += 1
            else:
                new_posts_only.append(post)
        else:
            # If no ID, assume it's new
            new_posts_only.append(post)

    # Stop if more than 50% of posts are duplicates (indicates overlap)
    should_stop = duplicate_count > 0 and duplicate_count >= len(new_posts) * 0.5

    return new_posts_only, duplicate_count, should_stop


def get_latest_cursor_from_existing_files(creator_name: str) -> Optional[str]:
    """Get the latest cursor from existing files to resume scraping."""
    latest_cursor = None
    latest_timestamp = 0

    if not DATA_DIR.exists():
        return None

    # Look for complete cursor-based files
    pattern = f"{creator_name}_complete_cursor_*.json"
    for filepath in DATA_DIR.glob(pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                file_data = json.load(f)

            if "metadata" in file_data:
                scraped_at = file_data["metadata"].get("scraped_at", 0)
                cursor = file_data["metadata"].get("cursor")

                if scraped_at > latest_timestamp and cursor:
                    latest_timestamp = scraped_at
                    latest_cursor = cursor

        except (json.JSONDecodeError, KeyError):
            continue

    return latest_cursor


def save_complete_data(all_items: List[Dict], creator_name: str = "creator") -> str:
    """Save all scraped data as a single JSON file with metadata."""
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)

    filename = f"{creator_name}_complete.json"
    filepath = DATA_DIR / filename

    # Add metadata
    complete_data = {
        "metadata": {
            "total_items": len(all_items),
            "scraped_at": time.time(),
            "creator_name": creator_name,
            "format_version": "2.0",
        },
        "data": all_items,
    }

    # Save as JSON
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(complete_data, f, indent=2, ensure_ascii=False)

    print(f"Saved complete dataset with {len(all_items)} items to {filepath}")
    return str(filepath)


def get_creator_name_from_data(data: Dict) -> str:
    """Extract creator name from API response data."""
    # Try to find creator name in included data
    if "included" in data:
        for item in data["included"]:
            if item.get("type") == "campaign":
                attrs = item.get("attributes", {})
                name = attrs.get("name", "")
                if name:
                    # Clean name for filename
                    clean_name = re.sub(r"[^\w\-_]", "_", name.lower())
                    return clean_name

    # Try to find in data items
    if "data" in data and data["data"]:
        first_item = data["data"][0] if isinstance(data["data"], list) else data["data"]
        if "relationships" in first_item and "campaign" in first_item["relationships"]:
            # Would need to look up campaign in included data
            pass

    return "creator"


# %% Extract base URL and pagination logic from HAR
def extract_api_template_from_har(filepath: Union[str, Path]) -> Dict:
    """
    Extract API URL template and pagination logic from HAR file.

    Args:
        filepath: Path to HAR file

    Returns:
        Dict with base_url, headers, and pagination info
    """
    filepath = Path(filepath)

    if filepath.suffix.lower() == ".har":
        har_requests = load_har_file(filepath)
        posts_request = find_posts_request(har_requests)

        if posts_request:
            base_url = posts_request["url"]
            headers = posts_request["headers"]
            response_data = posts_request["response_data"]

            # Extract creator name from response
            creator_name = get_creator_name_from_data(response_data)

            # Extract pagination info
            pagination_info = {}
            if "meta" in response_data and "pagination" in response_data["meta"]:
                pagination_info = response_data["meta"]["pagination"]
            elif "links" in response_data:
                pagination_info = response_data["links"]

            return {
                "base_url": base_url,
                "headers": headers,
                "creator_name": creator_name,
                "pagination_info": pagination_info,
                "total_posts": pagination_info.get("total", 0),
            }

    raise ValueError("Could not extract API template from HAR file")


def build_page_url(base_url: str, page_cursor: str = None) -> str:
    """
    Build a page URL from base URL and cursor.

    Args:
        base_url: Base API URL from HAR
        page_cursor: Pagination cursor (if any)

    Returns:
        Complete URL for the page
    """
    if page_cursor:
        # Add cursor to URL
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}page[cursor]={page_cursor}"
    else:
        # First page - remove any existing cursor parameters
        import urllib.parse as urlparse

        parsed = urlparse.urlparse(base_url)
        query_params = urlparse.parse_qs(parsed.query)

        # Remove cursor parameters for first page
        query_params.pop("page[cursor]", None)

        # Rebuild URL
        new_query = urlparse.urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        return urlparse.urlunparse(new_parsed)


def save_complete_page_data(
    complete_api_response: Dict,
    cursor: str = None,
    creator_name: str = "creator",
    page_number: int = 1,
) -> str:
    """
    Save a complete API response including posts and included data.
    This preserves the 'included' section needed for media extraction.
    """
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)

    # Create filename based on cursor or fallback to timestamp
    if cursor:
        # Clean cursor for filename (remove special characters)
        clean_cursor = re.sub(r"[^\w\-_]", "_", cursor)[:20]  # Limit length
        filename = f"{creator_name}_complete_cursor_{clean_cursor}.json"
    else:
        # Fallback to timestamp-based naming for first page
        timestamp = int(time.time())
        filename = f"{creator_name}_complete_page_{timestamp}_{page_number:03d}.json"

    filepath = DATA_DIR / filename

    # Extract just the data items for counting
    data_items = complete_api_response.get("data", [])
    if not isinstance(data_items, list):
        data_items = [data_items]

    # Add metadata to the saved data while preserving original structure
    enhanced_response = {
        "metadata": {
            "cursor": cursor,
            "page_number": page_number,
            "scraped_at": time.time(),
            "creator_name": creator_name,
            "total_items": len(data_items),
            "has_included_data": "included" in complete_api_response,
            "included_items": len(complete_api_response.get("included", [])),
        },
        "api_response": complete_api_response,  # Preserve complete structure
    }

    # Save as JSON
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(enhanced_response, f, indent=2, ensure_ascii=False)

    included_count = len(complete_api_response.get("included", []))
    print(
        f"Saved complete page {page_number} (cursor: {cursor or 'none'}) with {len(data_items)} posts and {included_count} included items to {filepath}"
    )
    return str(filepath)


# %% Enhanced scraping with cursor-based incremental storage
def scrape_all_pages(
    initial_captured_file: Union[str, Path],
    headers: Dict[str, str] = None,
    incremental: bool = True,
) -> Dict:
    """
    Scrape all pages using HAR file as template for API calls.
    Saves each page individually as JSON using cursor-based naming for incremental scraping.

    Args:
        initial_captured_file: Path to the initial captured JSON or HAR file
        headers: HTTP headers to use for requests (auto-extracted from HAR if available)
        incremental: If True, detect and skip already scraped content

    Returns:
        Dict with scraping results and file paths
    """

    # Extract API template from HAR file
    api_template = extract_api_template_from_har(initial_captured_file)

    base_url = api_template["base_url"]
    creator_name = api_template["creator_name"]

    print(f"Creator name: {creator_name}")
    print(f"Total posts available: {api_template['total_posts']}")

    # Use headers from HAR file or provided headers
    if headers is None:
        headers = api_template["headers"].copy()
        print(f"Using headers from HAR file: {len(headers)} headers")

    # Get existing post IDs for duplicate detection
    existing_post_ids = get_existing_post_ids(creator_name) if incremental else set()

    all_items = []
    page_files = []
    page_number = 1
    current_cursor = None
    new_posts_found = 0
    duplicate_posts_found = 0

    print(f"Incremental mode: {'ON' if incremental else 'OFF'}")
    if incremental and existing_post_ids:
        print(f"Will skip {len(existing_post_ids)} already scraped posts")

    # Start scraping from page 1 (latest posts first)
    while True:
        # Build URL for this page
        page_url = build_page_url(base_url, current_cursor)
        print(f"Scraping page {page_number}: {page_url}")

        try:
            time.sleep(REQUEST_DELAY)
            response = requests.get(page_url, headers=headers)
            response.raise_for_status()

            page_data = response.json()

            if "data" in page_data and page_data["data"]:
                page_items = (
                    page_data["data"]
                    if isinstance(page_data["data"], list)
                    else [page_data["data"]]
                )

                # Check for duplicates if in incremental mode
                if incremental:
                    new_posts_only, duplicate_count, should_stop = (
                        check_for_duplicate_posts(page_items, existing_post_ids)
                    )

                    duplicate_posts_found += duplicate_count

                    if should_stop:
                        print(
                            f"Found {duplicate_count}/{len(page_items)} duplicate posts - stopping incremental scrape"
                        )
                        print(f"Total new posts found: {new_posts_found}")
                        break

                    if new_posts_only:
                        # Only save and count new posts
                        all_items.extend(new_posts_only)
                        new_posts_found += len(new_posts_only)

                        # Save complete API response with included data
                        complete_page_file = save_complete_page_data(
                            page_data, current_cursor, creator_name, page_number
                        )
                        page_files.append(complete_page_file)

                        print(
                            f"Page {page_number}: {len(new_posts_only)} new items ({duplicate_count} duplicates)"
                        )
                    else:
                        print(
                            f"Page {page_number}: No new items ({duplicate_count} duplicates)"
                        )

                    if duplicate_count > 0:
                        print(f"Reached previously scraped content - stopping")
                        break

                else:
                    # Non-incremental mode - save everything
                    all_items.extend(page_items)

                    # Save complete API response with included data
                    complete_page_file = save_complete_page_data(
                        page_data, current_cursor, creator_name, page_number
                    )
                    page_files.append(complete_page_file)

                    print(f"Page {page_number}: {len(page_items)} items")

            else:
                print(f"Page {page_number}: No data found, stopping")
                break

            # Check for next page cursor
            next_cursor = None
            if "meta" in page_data and "pagination" in page_data["meta"]:
                pagination = page_data["meta"]["pagination"]
                if "cursors" in pagination and "next" in pagination["cursors"]:
                    next_cursor = pagination["cursors"]["next"]
            elif "links" in page_data and "next" in page_data["links"]:
                # Extract cursor from next URL
                next_url = page_data["links"]["next"]
                if "page[cursor]=" in next_url:
                    next_cursor = next_url.split("page[cursor]=")[1].split("&")[0]

            if next_cursor:
                current_cursor = next_cursor
                page_number += 1
            else:
                print("No more pages found")
                break

        except requests.RequestException as e:
            print(f"Error scraping page {page_url}: {e}")
            break

    # Save complete dataset (only new items if incremental)
    if all_items:
        complete_file = save_complete_data(all_items, creator_name)
    else:
        complete_file = None
        print("No new items to save")

    total_items = len(all_items)
    print(f"Total items collected: {total_items} across {len(page_files)} pages")

    if incremental:
        print(
            f"New posts: {new_posts_found}, Duplicates found: {duplicate_posts_found}"
        )

    return {
        "total_items": total_items,
        "new_items": new_posts_found if incremental else total_items,
        "duplicate_items": duplicate_posts_found if incremental else 0,
        "pages_scraped": len(page_files),
        "creator_name": creator_name,
        "page_files": page_files,
        "complete_file": complete_file,
        "incremental_mode": incremental,
        "total_available": api_template["total_posts"],
    }


# %% [markdown]
# ## Media Download Functions


# %% Enhanced media URL extraction
def generate_media_filename(
    creator_name: str,
    post_date: str,
    post_id: str,
    post_title: str,
    image_number: int = None,
    total_images: int = 1,
    file_extension: str = "jpg",
) -> str:
    """
    Generate a standardized filename for media files.
    Format: <account> - <date> - <id> - <title> - <optional index for posts with multiple files>

    Args:
        creator_name: Name of the creator/account
        post_date: Publication date (YYYY-MM-DD format)
        post_id: Post ID
        post_title: Post title (will be cleaned)
        image_number: Image number (1-based) for posts with multiple images
        total_images: Total number of images in the post
        file_extension: File extension (without dot)

    Returns:
        Generated filename
    """
    # Clean creator name for filename
    clean_creator = re.sub(r"[^\w\-_]", "_", creator_name)

    # Handle None or empty title
    if not post_title:
        clean_title = "untitled"
    else:
        # Clean post title for filename (remove special chars, limit length)
        # Only keep word characters, underscores, and spaces (remove hyphens and other special chars)
        clean_title = re.sub(r"[^\w\s]", "", str(post_title)).strip()
        clean_title = re.sub(
            r"\s+", "_", clean_title
        )  # Replace spaces with underscores
        clean_title = clean_title[:50]  # Limit length

        # If cleaning resulted in empty string, use placeholder
        if not clean_title:
            clean_title = "untitled"

    # Build filename components
    components = [clean_creator, post_date, post_id, clean_title]

    # Add index for multiple images
    if total_images > 1 and image_number is not None:
        components.append(f"{image_number:02d}")

    # Join components and add extension
    filename = " - ".join(components) + f".{file_extension}"

    return filename


def extract_media_urls_from_complete_data(complete_data: Dict) -> List[Dict]:
    """
    Extract all media URLs from complete API response data, including high-resolution download URLs.

    Args:
        complete_data: Complete API response data with posts and included media

    Returns:
        List of media info dicts with URLs, filenames, and metadata
    """
    media_info = []

    # Create a lookup for included media items by ID
    included_media = {}
    if "included" in complete_data:
        for item in complete_data["included"]:
            if item.get("type") == "media":
                media_id = item.get("id")
                if media_id:
                    included_media[media_id] = item

    # Extract creator name from included data (campaign info)
    creator_name = "creator"  # Default fallback
    if "included" in complete_data:
        for item in complete_data["included"]:
            if item.get("type") == "campaign":
                attrs = item.get("attributes", {})
                name = attrs.get("name", "")
                if name:
                    creator_name = re.sub(r"[^\w\-_]", "_", name.lower())
                    break

    # Process each post
    data_items = complete_data.get("data", [])
    if not isinstance(data_items, list):
        data_items = [data_items]

    for post in data_items:
        post_id = post.get("id", "unknown")
        post_title = ""
        post_date = "unknown"

        # Get post attributes
        if "attributes" in post:
            attrs = post["attributes"]
            post_title = attrs.get("title", "")

            # Extract and format publication date
            published_at = attrs.get("published_at")
            if published_at:
                try:
                    # Parse ISO date and format as YYYY-MM-DD
                    if isinstance(published_at, str):
                        # Handle different date formats
                        if "T" in published_at:
                            # ISO format: 2023-12-01T15:30:00.000Z
                            dt = datetime.fromisoformat(
                                published_at.replace("Z", "+00:00")
                            )
                        else:
                            # Simple date format
                            dt = datetime.fromisoformat(published_at)
                        post_date = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    # Fallback to using the raw string or unknown
                    post_date = str(published_at)[:10] if published_at else "unknown"

        # Extract media IDs from post relationships
        media_ids = []

        if "relationships" in post:
            # Check for images relationship
            if (
                "images" in post["relationships"]
                and "data" in post["relationships"]["images"]
            ):
                images_data = post["relationships"]["images"]["data"]
                if isinstance(images_data, list):
                    media_ids.extend(
                        [item.get("id") for item in images_data if item.get("id")]
                    )
                elif isinstance(images_data, dict) and images_data.get("id"):
                    media_ids.append(images_data["id"])

            # Check for media relationship (fallback)
            if (
                "media" in post["relationships"]
                and "data" in post["relationships"]["media"]
            ):
                media_data = post["relationships"]["media"]["data"]
                if isinstance(media_data, list):
                    media_ids.extend(
                        [item.get("id") for item in media_data if item.get("id")]
                    )
                elif isinstance(media_data, dict) and media_data.get("id"):
                    media_ids.append(media_data["id"])

        # Also check post_metadata for image_order (more reliable for ordering)
        if "attributes" in post and "post_metadata" in post["attributes"]:
            metadata = post["attributes"]["post_metadata"]
            if (
                metadata
                and "image_order" in metadata
                and isinstance(metadata["image_order"], list)
            ):
                # Use image_order for proper ordering, but still validate against relationships
                ordered_ids = [str(mid) for mid in metadata["image_order"]]
                # Only include IDs that are also in relationships (for safety)
                media_ids = [
                    mid for mid in ordered_ids if mid in [str(x) for x in media_ids]
                ] or media_ids

        # Process each media ID
        for i, media_id in enumerate(media_ids):
            media_id = str(media_id)  # Ensure string for lookup

            if media_id in included_media:
                media_item = included_media[media_id]

                # Extract download URL (highest quality)
                download_url = media_item.get("download_url")

                # Extract filename
                filename = media_item.get("file_name", "")

                # Extract image URLs for different qualities
                image_urls = media_item.get("image_urls", {})

                # Get original/highest quality URL if download_url not available
                if not download_url:
                    if "original" in image_urls:
                        download_url = image_urls["original"]
                    elif "default_large" in image_urls:
                        download_url = image_urls["default_large"]
                    elif "default" in image_urls:
                        download_url = image_urls["default"]
                    elif "url" in image_urls:
                        download_url = image_urls["url"]

                # Get display info for metadata
                display_info = media_item.get("display", {})

                if download_url:
                    # Determine file extension from URL or content type
                    file_extension = "jpg"  # Default
                    if filename and "." in filename:
                        file_extension = filename.split(".")[-1].lower()
                    elif download_url:
                        # Try to determine from URL
                        url_lower = download_url.lower()
                        if any(
                            ext in url_lower
                            for ext in [".png", ".jpeg", ".jpg", ".gif", ".webp"]
                        ):
                            for ext in ["png", "jpeg", "jpg", "gif", "webp"]:
                                if f".{ext}" in url_lower:
                                    file_extension = ext
                                    break

                    # Generate standardized filename
                    filename = generate_media_filename(
                        creator_name=creator_name,
                        post_date=post_date,
                        post_id=post_id,
                        post_title=post_title,
                        image_number=i + 1,
                        total_images=len(media_ids),
                        file_extension=file_extension,
                    )

                    media_info.append(
                        {
                            "url": download_url,
                            "filename": filename,
                            "post_id": post_id,
                            "post_title": post_title,
                            "media_id": media_id,
                            "image_number": i + 1,
                            "total_images": len(media_ids),
                            "width": display_info.get("width"),
                            "height": display_info.get("height"),
                            "all_image_urls": image_urls,  # Keep all quality options
                            "metadata": {
                                "dimensions": media_item.get("metadata", {}).get(
                                    "dimensions", {}
                                ),
                                "state": media_item.get("state", "unknown"),
                            },
                        }
                    )
            else:
                print(
                    f"Warning: Media ID {media_id} not found in included data for post {post_id}"
                )

        # Fallback: extract from post attributes if no media found in relationships
        if not media_ids and "attributes" in post:
            attrs = post["attributes"]

            # Check for direct image URLs in post attributes
            for field in ["image", "post_file"]:
                if field in attrs and attrs[field]:
                    field_data = attrs[field]
                    if isinstance(field_data, dict):
                        # Try to get the highest quality URL
                        url = None
                        if "large_url" in field_data:
                            url = field_data["large_url"]
                        elif "url" in field_data:
                            url = field_data["url"]

                        if url:
                            # Determine file extension from URL
                            file_extension = "jpg"  # Default
                            url_lower = url.lower()
                            if any(
                                ext in url_lower
                                for ext in [".png", ".jpeg", ".jpg", ".gif", ".webp"]
                            ):
                                for ext in ["png", "jpeg", "jpg", "gif", "webp"]:
                                    if f".{ext}" in url_lower:
                                        file_extension = ext
                                        break

                            # Generate standardized filename for direct images
                            filename = generate_media_filename(
                                creator_name=creator_name,
                                post_date=post_date,
                                post_id=post_id,
                                post_title=post_title,
                                image_number=1,
                                total_images=1,
                                file_extension=file_extension,
                            )

                            media_info.append(
                                {
                                    "url": url,
                                    "filename": filename,
                                    "post_id": post_id,
                                    "post_title": post_title,
                                    "media_id": f"direct_{field}",
                                    "image_number": 1,
                                    "total_images": 1,
                                    "width": field_data.get("width"),
                                    "height": field_data.get("height"),
                                    "all_image_urls": {},
                                    "metadata": {
                                        "source": f"post_attributes_{field}",
                                        "state": "direct",
                                    },
                                }
                            )

    return media_info


def extract_media_urls_from_scraped_files(creator_name: str) -> List[Dict]:
    """
    Extract media URLs from all scraped files for a creator.

    Args:
        creator_name: Name of the creator

    Returns:
        List of media info dicts
    """
    all_media_info = []

    # Process complete file if it exists
    complete_file = DATA_DIR / f"{creator_name}_complete.json"
    if complete_file.exists():
        print(f"Extracting media from complete file: {complete_file}")
        with open(complete_file, "r", encoding="utf-8") as f:
            file_data = json.load(f)

        # Handle different file formats
        if "data" in file_data:
            # New format with metadata
            posts_data = file_data["data"]
        else:
            # Old format - direct list
            posts_data = file_data

        # Create a mock complete data structure for extraction
        complete_data = {"data": posts_data}
        media_info = extract_media_urls_from_complete_data(complete_data)
        all_media_info.extend(media_info)

    # Also process individual page files to get included data
    page_files = list(DATA_DIR.glob(f"{creator_name}_cursor_*.json")) + list(
        DATA_DIR.glob(f"{creator_name}_page_*.json")
    )

    for page_file in page_files:
        print(f"Extracting media from page file: {page_file}")
        try:
            with open(page_file, "r", encoding="utf-8") as f:
                page_data = json.load(f)

            # Handle different file formats
            if "data" in page_data:
                posts_data = page_data["data"]
            else:
                posts_data = page_data

            # Create a mock complete data structure for extraction
            complete_data = {"data": posts_data}
            media_info = extract_media_urls_from_complete_data(complete_data)
            all_media_info.extend(media_info)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing page file {page_file}: {e}")
            continue

    # Remove duplicates based on media_id and URL
    seen = set()
    unique_media_info = []
    for item in all_media_info:
        key = (item.get("media_id", ""), item.get("url", ""))
        if key not in seen:
            seen.add(key)
            unique_media_info.append(item)

    print(
        f"Found {len(unique_media_info)} unique media items (removed {len(all_media_info) - len(unique_media_info)} duplicates)"
    )
    return unique_media_info


# %% Enhanced download function with better filename handling
def download_media_enhanced(
    media_info_list: List[Dict], headers: Dict[str, str] = None
) -> List[Dict]:
    """
    Download media files using enhanced media info with proper filenames.

    Args:
        media_info_list: List of media info dicts from extract_media_urls_from_complete_data
        headers: HTTP headers for requests

    Returns:
        List of download results
    """
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.patreon.com/",
        }

    download_results = []

    for i, media_info in enumerate(media_info_list):
        url = media_info["url"]
        filename = media_info["filename"]
        post_id = media_info.get("post_id", "unknown")
        image_num = media_info.get("image_number", 1)
        total_images = media_info.get("total_images", 1)

        print(
            f"Downloading media {i+1}/{len(media_info_list)}: Post {post_id} Image {image_num}/{total_images}"
        )
        print(f"  URL: {url}")
        print(f"  Filename: {filename}")

        try:
            time.sleep(REQUEST_DELAY)
            response = requests.get(
                url, headers=headers, timeout=60
            )  # Longer timeout for large files
            response.raise_for_status()

            # The filename should already have the correct extension from generate_media_filename
            # But double-check and add if missing
            if not any(
                filename.lower().endswith(ext)
                for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
            ):
                # Detect from content type or URL as fallback
                content_type = response.headers.get("content-type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    filename += ".jpg"
                elif "png" in content_type:
                    filename += ".png"
                elif "gif" in content_type:
                    filename += ".gif"
                elif "webp" in content_type:
                    filename += ".webp"
                else:
                    filename += ".jpg"  # Default

            # Save directly to media directory (no subdirectories needed with new naming scheme)
            filepath = MEDIA_DIR / filename

            # Save file
            with open(filepath, "wb") as f:
                f.write(response.content)

            # Add media info to result
            result = {
                "url": url,
                "filepath": str(filepath),
                "filename": filename,
                "size_bytes": len(response.content),
                "content_type": response.headers.get("content-type"),
                "success": True,
                "post_id": post_id,
                "media_id": media_info.get("media_id"),
                "image_number": image_num,
                "total_images": total_images,
                "dimensions": {
                    "width": media_info.get("width"),
                    "height": media_info.get("height"),
                },
            }

            download_results.append(result)
            print(f"  ✅ Downloaded {len(response.content):,} bytes")

        except Exception as e:
            print(f"  ❌ Error downloading: {e}")
            download_results.append(
                {
                    "url": url,
                    "filepath": None,
                    "filename": filename,
                    "size_bytes": 0,
                    "content_type": None,
                    "success": False,
                    "error": str(e),
                    "post_id": post_id,
                    "media_id": media_info.get("media_id"),
                    "image_number": image_num,
                    "total_images": total_images,
                }
            )

    return download_results


# %% Extract media URLs from complete files
def extract_media_urls_from_complete_files(creator_name: str) -> List[Dict]:
    """
    Extract media URLs from complete API response files that include the 'included' section.

    Args:
        creator_name: Name of the creator

    Returns:
        List of media info dicts
    """
    all_media_info = []

    # Look for complete page files (new format with included data)
    complete_page_files = list(
        DATA_DIR.glob(f"{creator_name}_complete_cursor_*.json")
    ) + list(DATA_DIR.glob(f"{creator_name}_complete_page_*.json"))

    for page_file in complete_page_files:
        print(f"Extracting media from complete page file: {page_file}")
        try:
            with open(page_file, "r", encoding="utf-8") as f:
                file_data = json.load(f)

            # Extract the complete API response
            if "api_response" in file_data:
                complete_api_response = file_data["api_response"]
                media_info = extract_media_urls_from_complete_data(
                    complete_api_response
                )
                all_media_info.extend(media_info)

                print(f"  Found {len(media_info)} media items in this page")
            else:
                print(f"  Warning: No api_response found in {page_file}")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing complete page file {page_file}: {e}")
            continue

    if not complete_page_files:
        print(f"No complete page files found for {creator_name}")
        print("No scraped data found. Please run the scraper first.")
        return []

    # Remove duplicates based on media_id and URL
    seen = set()
    unique_media_info = []
    for item in all_media_info:
        key = (item.get("media_id", ""), item.get("url", ""))
        if key not in seen:
            seen.add(key)
            unique_media_info.append(item)

    print(
        f"Found {len(unique_media_info)} unique media items (removed {len(all_media_info) - len(unique_media_info)} duplicates)"
    )
    return unique_media_info


# %% Complete workflow function
def run_complete_scraping_workflow(
    captured_file: Union[str, Path],
    headers: Dict[str, str] = None,
    download_media_files: bool = True,
    incremental: bool = True,
) -> Dict:
    """
    Run the complete scraping workflow with per-page JSON storage.

    Args:
        captured_file: Path to captured data from Developer Tools
        headers: HTTP headers for requests
        download_media_files: Whether to download media files

    Returns:
        Dict with workflow results
    """

    print("Starting complete scraping workflow...")

    # Step 1: Extract API template from HAR
    print("\n1. Extracting API template from HAR file...")
    api_template = extract_api_template_from_har(captured_file)
    print(f"Found API template for creator: {api_template['creator_name']}")
    print(f"Total posts available: {api_template['total_posts']}")

    # Step 2: Scrape all pages (saves each page individually with incremental detection)
    print("\n2. Scraping all pages...")
    scraping_results = scrape_all_pages(captured_file, headers, incremental=incremental)

    # Step 3: Download media (if requested)
    media_results = []
    if download_media_files:
        print(f"\n3. Extracting media URLs from scraped data...")

        # Use enhanced media extraction that handles included data properly
        media_info_list = extract_media_urls_from_complete_files(
            scraping_results["creator_name"]
        )

        if media_info_list:
            print(f"Found {len(media_info_list)} media items to download")

            # Show summary of what we found
            posts_with_media = len(set(item["post_id"] for item in media_info_list))
            total_images = len(media_info_list)
            print(f"  - {posts_with_media} posts with media")
            print(f"  - {total_images} total images")

            # Download all media
            media_results = download_media_enhanced(media_info_list, headers)

            # Save media download results
            media_file = save_complete_data(
                media_results, f"{scraping_results['creator_name']}_media_downloads"
            )
            print(f"Media download results saved to: {media_file}")
        else:
            print("No media URLs found in scraped data")
            print("This might happen if:")
            print("  - Posts don't contain images")
            print("  - The 'included' section is missing from API responses")
            print("  - Media relationships are not properly captured")

    # Return summary
    return {
        "total_posts": scraping_results["total_items"],
        "new_items": scraping_results["new_items"],
        "duplicate_items": scraping_results["duplicate_items"],
        "pages_scraped": scraping_results["pages_scraped"],
        "creator_name": scraping_results["creator_name"],
        "page_files": scraping_results["page_files"],
        "complete_file": scraping_results["complete_file"],
        "incremental_mode": scraping_results["incremental_mode"],
        "total_available": scraping_results.get("total_available", 0),
        "media_urls_found": len([r for r in media_results if "url" in r]),
        "media_downloaded": len([r for r in media_results if r.get("success", False)]),
        "api_template": api_template,
    }


# %% [markdown]
# ## Data Analysis with Polars


# %% Analyze scraped data
def analyze_creator_data(filename: str) -> None:
    """Analyze creator data using Polars."""

    filepath = DATA_DIR / f"{filename}.parquet"
    if not filepath.exists():
        print(f"No data found at {filepath}")
        return

    # Load data with Polars
    df = pl.read_parquet(filepath)

    print("Data Summary:")
    print(f"Total creators: {len(df)}")
    if "followers" in df.columns:
        print(f"Average followers: {df['followers'].mean():.0f}")
    if "posts_count" in df.columns:
        print(f"Total posts: {df['posts_count'].sum()}")

    # Show data types and schema
    print("\nData Schema:")
    print(df.schema)

    # Display first few rows
    print("\nFirst 5 rows:")
    print(df.head())


# %% Standalone media extraction and download
def extract_and_download_media_standalone(
    creator_name: str, headers: Dict[str, str] = None, force_redownload: bool = False
) -> Dict:
    """
    Standalone function to extract and download media from existing scraped data.

    Args:
        creator_name: Name of the creator
        headers: HTTP headers for requests
        force_redownload: If True, re-download files that already exist

    Returns:
        Dict with download results
    """
    print(f"Extracting and downloading media for creator: {creator_name}")

    # Extract media URLs from scraped data
    media_info_list = extract_media_urls_from_complete_files(creator_name)

    if not media_info_list:
        print("No media found in scraped data")
        return {
            "creator_name": creator_name,
            "media_found": 0,
            "media_downloaded": 0,
            "media_skipped": 0,
            "media_failed": 0,
            "download_results": [],
        }

    print(f"Found {len(media_info_list)} media items to download")

    # Show summary
    posts_with_media = len(set(item["post_id"] for item in media_info_list))
    print(f"  - {posts_with_media} posts with media")
    print(f"  - {len(media_info_list)} total images")

    # Filter out already downloaded files if not forcing redownload
    if not force_redownload:
        filtered_media_info = []
        skipped_count = 0

        for media_info in media_info_list:
            filename = media_info["filename"]

            # With the new naming scheme, all files go directly in MEDIA_DIR
            expected_path = MEDIA_DIR / filename

            # Check various possible extensions (in case the extension detection changed)
            possible_paths = [expected_path]
            if not any(
                filename.lower().endswith(ext)
                for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
            ):
                for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                    possible_paths.append(expected_path.with_suffix(ext))

            # Check if any version exists
            if any(path.exists() for path in possible_paths):
                skipped_count += 1
                print(f"  Skipping {filename} (already exists)")
            else:
                filtered_media_info.append(media_info)

        if skipped_count > 0:
            print(f"Skipped {skipped_count} already downloaded files")
            print(f"Downloading {len(filtered_media_info)} new files")

        media_info_list = filtered_media_info

    if not media_info_list:
        print("All media files already downloaded")
        return {
            "creator_name": creator_name,
            "media_found": len(media_info_list)
            + (skipped_count if not force_redownload else 0),
            "media_downloaded": 0,
            "media_skipped": skipped_count if not force_redownload else 0,
            "media_failed": 0,
            "download_results": [],
        }

    # Download media
    download_results = download_media_enhanced(media_info_list, headers)

    # Count results
    successful_downloads = len([r for r in download_results if r.get("success", False)])
    failed_downloads = len([r for r in download_results if not r.get("success", False)])

    # Save download results
    media_file = save_complete_data(download_results, f"{creator_name}_media_downloads")
    print(f"Media download results saved to: {media_file}")

    print(f"\nDownload Summary:")
    print(f"  - Successfully downloaded: {successful_downloads}")
    print(f"  - Failed downloads: {failed_downloads}")
    if not force_redownload:
        print(f"  - Skipped (already existed): {skipped_count}")

    return {
        "creator_name": creator_name,
        "media_found": len(media_info_list)
        + (skipped_count if not force_redownload else 0),
        "media_downloaded": successful_downloads,
        "media_skipped": skipped_count if not force_redownload else 0,
        "media_failed": failed_downloads,
        "download_results": download_results,
        "results_file": media_file,
    }


# %% [markdown]
# ## Main Execution

# %% Main execution block - Updated for Developer Tools workflow
if __name__ == "__main__":
    import sys
    import argparse

    print("Patreon Scraper - Developer Tools Edition")
    print("=" * 50)

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Scrape Patreon content from HAR/JSON files"
    )
    parser.add_argument(
        "captured_file", nargs="?", help="Path to captured HAR or JSON file"
    )
    parser.add_argument("--no-media", action="store_true", help="Skip media downloads")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--full-rescrape",
        action="store_true",
        help="Disable incremental mode and scrape everything",
    )
    parser.add_argument(
        "--media-only",
        action="store_true",
        help="Only extract and download media from existing scraped data (no scraping)",
    )
    parser.add_argument(
        "--creator-name",
        type=str,
        help="Creator name for media-only mode (if not provided, will try to detect)",
    )
    parser.add_argument(
        "--force-redownload",
        action="store_true",
        help="Re-download media files even if they already exist",
    )

    args = parser.parse_args()

    # Handle media-only mode
    if args.media_only:
        print("Media-only mode: Extracting and downloading media from existing data")

        # Determine creator name
        if args.creator_name:
            creator_name = args.creator_name
        else:
            # Try to detect creator name from existing files
            if DATA_DIR.exists():
                # Look for any complete files and extract creator name
                complete_files = list(DATA_DIR.glob("*_complete.json"))
                if complete_files:
                    # Extract creator name from filename
                    creator_name = complete_files[0].stem.replace("_complete", "")
                else:
                    # Look for any complete cursor files
                    cursor_files = list(DATA_DIR.glob("*_complete_cursor_*.json"))
                    if cursor_files:
                        # Extract creator name from filename
                        filename = cursor_files[0].stem
                        creator_name = filename.split("_complete_cursor_")[0]
                    else:
                        print(
                            "Could not detect creator name. Please specify with --creator-name"
                        )
                        sys.exit(1)
            else:
                print(
                    "No data directory found. Please specify creator name with --creator-name"
                )
                sys.exit(1)

        print(f"Using creator name: {creator_name}")

        # Set up headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.api+json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.patreon.com/",
        }

        # Run standalone media extraction
        try:
            results = extract_and_download_media_standalone(
                creator_name=creator_name,
                headers=headers,
                force_redownload=args.force_redownload,
            )

            print("\n" + "=" * 50)
            print("MEDIA EXTRACTION COMPLETE!")
            print(f"Creator: {results['creator_name']}")
            print(f"Media found: {results['media_found']}")
            print(f"Successfully downloaded: {results['media_downloaded']}")
            print(f"Skipped (already existed): {results['media_skipped']}")
            print(f"Failed downloads: {results['media_failed']}")

            if results.get("results_file"):
                print(f"Results saved to: {results['results_file']}")

        except Exception as e:
            print(f"Error during media extraction: {e}")
            import traceback

            traceback.print_exc()

        sys.exit(0)

    # Check if captured file is provided
    if args.captured_file:
        captured_file = args.captured_file
    else:
        # Default captured file locations (try HAR first)
        har_file = CAPTURED_DIR / "patreon_capture.har"
        json_file = CAPTURED_DIR / "patreon_posts.json"

        if har_file.exists():
            captured_file = har_file
        elif json_file.exists():
            captured_file = json_file
        else:
            print(
                f"""
No captured data file found. Looking for:
- {har_file} (preferred - contains headers automatically)
- {json_file} (requires manual header setup)

To use this scraper:

=== RECOMMENDED: HAR Method (Microsoft Edge) ===
1. Open Microsoft Edge and go to target Patreon page
2. Open Developer Tools (F12) > Network tab
3. Check 'Preserve log' and filter by 'Fetch/XHR'
4. Navigate through posts (scroll or load more)
5. Right-click in Network requests list
6. Select 'Save all as HAR with content'
7. Save as '{har_file}'

=== Alternative: JSON Method ===
1. Follow steps 1-4 above
2. Find a posts API request and copy response
3. Save as '{json_file}'
4. Manually update headers in script

Then run:
python scraper.py [file_path]

=== MEDIA-ONLY MODE ===
To extract and download media from existing scraped data:
python scraper.py --media-only --creator-name [creator_name]

Options:
--force-redownload    Re-download files even if they exist
--no-media           Skip media downloads during scraping
            """
            )
            sys.exit(1)

    # Example headers - you should copy these from Developer Tools
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/vnd.api+json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.patreon.com/",
        # Add your session cookies and authorization here:
        # 'Cookie': 'session_id=your_session; patreon_device_id=your_device_id;',
        # 'Authorization': 'Bearer your_bearer_token',
    }

    print(f"Using captured data file: {captured_file}")

    # Determine if media should be downloaded
    download_media = not args.no_media
    if args.no_media:
        print("Media downloads disabled (--no-media flag)")

    # Determine incremental mode
    incremental_mode = not args.full_rescrape
    if args.full_rescrape:
        print("Full re-scrape mode enabled (--full-rescrape flag)")

    if args.verbose:
        print("Verbose logging enabled")

    try:
        # Run the complete workflow
        results = run_complete_scraping_workflow(
            captured_file=captured_file,
            headers=headers,
            download_media_files=download_media,
            incremental=incremental_mode,
        )

        print("\n" + "=" * 50)
        print("SCRAPING COMPLETE!")
        print(f"Creator: {results['creator_name']}")
        print(f"Total posts scraped: {results['total_posts']}")
        print(f"New posts found: {results['new_items']}")
        print(f"Duplicate posts skipped: {results['duplicate_items']}")
        print(f"Total posts available: {results['total_available']}")
        print(f"Pages scraped: {results['pages_scraped']}")
        print(f"Incremental mode: {'ON' if results['incremental_mode'] else 'OFF'}")
        print(f"Media URLs found: {results['media_urls_found']}")
        print(f"Media files downloaded: {results['media_downloaded']}")

        print(f"\nFiles created:")
        if results["complete_file"]:
            print(f"- Complete dataset: {results['complete_file']}")
        for i, page_file in enumerate(results["page_files"], 1):
            print(f"- Page {i}: {page_file}")

        # Show data directory contents
        if DATA_DIR.exists():
            print(f"\nData directory contents ({DATA_DIR}):")
            for file in sorted(DATA_DIR.glob("*.json")):
                size_kb = file.stat().st_size / 1024
                print(f"  {file.name} ({size_kb:.1f} KB)")

    except Exception as e:
        print(f"Error during scraping: {e}")
        import traceback

        traceback.print_exc()


# %% [markdown]
# ## Data Export Example


# %% Export data to different formats
def export_data(filename: str) -> None:
    """Export data to various formats for further analysis."""

    filepath = DATA_DIR / f"{filename}.parquet"
    if not filepath.exists():
        return

    df = pl.read_parquet(filepath)

    # Export to CSV
    df.write_csv(DATA_DIR / f"{filename}.csv")

    # Export to JSON
    df.write_json(DATA_DIR / f"{filename}_export.json")

    print(f"Data exported to multiple formats in {DATA_DIR}")


# %% Utility function to validate captured data
def validate_captured_data(filepath: Union[str, Path]) -> None:
    """Validate and preview captured data structure."""

    print("Testing captured data...")

    try:
        analysis = analyze_captured_data(filepath)

        print("\nStructure Analysis:")
        print(f"- Post type: {analysis['post_structure'].get('type', 'Unknown')}")
        print(
            f"- Available attributes: {', '.join(analysis['post_structure'].get('attributes_keys', []))}"
        )
        print(
            f"- Available relationships: {', '.join(analysis['post_structure'].get('relationships_keys', []))}"
        )

        if analysis["media_urls"]:
            print(f"\nFound {len(analysis['media_urls'])} media URLs:")
            for i, url in enumerate(analysis["media_urls"][:5]):  # Show first 5
                print(f"  {i+1}. {url}")
            if len(analysis["media_urls"]) > 5:
                print(f"  ... and {len(analysis['media_urls']) - 5} more")

        # Test pagination
        pagination_urls = extract_pagination_urls(analysis)
        if pagination_urls:
            print(f"\nPagination URLs found: {len(pagination_urls)}")
            for url in pagination_urls[:3]:  # Show first 3
                print(f"  - {url}")
        else:
            print("\nNo pagination URLs found in this page")

    except Exception as e:
        print(f"Error testing captured data: {e}")


# %% Run export if needed
# export_data("complete_scrape")
