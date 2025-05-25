#!/usr/bin/env python3
"""
Simple Patreon scraper using cookies from Copy Cookies plugin.
No HAR files needed - just cookies and creator name!
"""

import requests
import json
import time
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import hashlib
import os
from urllib.parse import urlparse, unquote

# Configuration
DATA_DIR = Path("data")
MEDIA_DIR = Path("media")
DATA_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

REQUEST_DELAY = 1.0  # seconds between requests


def cookies_json_to_string(cookies_json: str) -> str:
    """Convert cookies from Copy Cookies plugin JSON format to cookie string."""
    try:
        cookies_list = json.loads(cookies_json)
        cookie_pairs = []

        for cookie in cookies_list:
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            if name and value:
                cookie_pairs.append(f"{name}={value}")

        cookie_string = "; ".join(cookie_pairs)
        print(f"Converted {len(cookies_list)} cookies to cookie string")
        return cookie_string

    except json.JSONDecodeError as e:
        print(f"Error parsing cookies JSON: {e}")
        return ""


def create_headers(cookie_string: str) -> Dict[str, str]:
    """Create authenticated headers using cookie string."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/vnd.api+json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.patreon.com/",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie_string,
    }


def find_campaign_id(creator_name: str, headers: Dict[str, str]) -> str:
    """Find campaign ID for a creator."""
    print(f"Finding campaign ID for creator: {creator_name}")

    # Try to get campaign ID from creator page
    creator_url = f"https://www.patreon.com/{creator_name}"
    response = requests.get(creator_url, headers=headers)
    response.raise_for_status()

    # Debug: save a snippet of the page content
    page_snippet = (
        response.text[:2000] + "..." if len(response.text) > 2000 else response.text
    )
    print(f"Page content snippet (first 2000 chars): {page_snippet}")

    # Try multiple patterns to find campaign ID
    patterns = [
        r'"campaign_id":"(\d+)"',
        r'"campaign":{"id":"(\d+)"',
        r"campaign_id=(\d+)",
        r'"id":"(\d+)"[^}]*"type":"campaign"',
        r'"type":"campaign"[^}]*"id":"(\d+)"',
    ]

    for pattern in patterns:
        campaign_match = re.search(pattern, response.text)
        if campaign_match:
            campaign_id = campaign_match.group(1)
            print(f"Found campaign ID: {campaign_id} (using pattern: {pattern})")
            return campaign_id

    # If not found, try the API search approach
    print("Campaign ID not found in page, trying API search...")
    try:
        search_url = "https://www.patreon.com/api/campaigns"
        search_params = {
            "filter[query]": creator_name,
            "fields[campaign]": "name,url,patron_count,creation_name",
            "json-api-version": "1.0",
        }

        response = requests.get(search_url, headers=headers, params=search_params)
        response.raise_for_status()
        search_data = response.json()

        if "data" in search_data and search_data["data"]:
            for campaign in search_data["data"]:
                if campaign.get("type") == "campaign":
                    attrs = campaign.get("attributes", {})
                    campaign_url = attrs.get("url", "")
                    if creator_name.lower() in campaign_url.lower():
                        campaign_id = campaign.get("id")
                        print(f"Found campaign ID via API: {campaign_id}")
                        return campaign_id
    except Exception as e:
        print(f"API search failed: {e}")

    raise ValueError(f"Could not find campaign ID for creator: {creator_name}")


def get_posts_api_params(campaign_id: str) -> Dict[str, str]:
    """Get standard parameters for Patreon posts API."""
    return {
        "include": "campaign,access_rules,access_rules.tier.null,attachments_media,audio,audio_preview.null,custom_thumbnail_media.null,drop,images,media,native_video_insights,poll.choices,poll.current_user_responses.user,poll.current_user_responses.choice,poll.current_user_responses.poll,shows.null,user,user_defined_tags,video.null,content_unlock_options.product_variant.null,content_unlock_options.reward.null,content_unlock_options.product_variant.collection.null,livestream,livestream.state,livestream.display,rss_synced_feed",
        "fields[campaign]": "currency,show_audio_post_download_links,avatar_photo_url,avatar_photo_image_urls,earnings_visibility,is_nsfw,is_monthly,name,url,patron_count,primary_theme_color",
        "fields[post]": "change_visibility_at,comment_count,commenter_count,content,created_at,current_user_can_comment,current_user_can_delete,current_user_can_report,current_user_can_view,current_user_comment_disallowed_reason,current_user_has_liked,embed,image,insights_last_updated_at,is_paid,is_preview_blurred,has_custom_thumbnail,like_count,meta_image_url,min_cents_pledged_to_view,monetization_ineligibility_reason,post_file,post_metadata,published_at,patreon_url,post_type,pledge_url,preview_asset_type,thumbnail,thumbnail_url,teaser_text,content_teaser_text,title,upgrade_url,url,was_posted_by_campaign_owner,has_ti_violation,moderation_status,post_level_suspension_removal_date,pls_one_liners_by_category,video,video_preview,view_count,content_unlock_options,is_new_to_current_user,watch_state",
        "fields[post_tag]": "tag_type,value",
        "fields[user]": "image_url,full_name,url",
        "fields[access_rule]": "access_rule_type,amount_cents",
        "fields[livestream]": "display,state",
        "fields[media]": "id,image_urls,display,download_url,metadata,file_name,state",
        "fields[native_video_insights]": "average_view_duration,average_view_pct,has_preview,id,last_updated_at,num_views,preview_views,video_duration",
        "fields[content-unlock-option]": "content_unlock_type,is_current_user_eligible,reward_benefit_categories",
        "fields[product-variant]": "price_cents,currency_code,checkout_url,is_hidden,published_at_datetime,content_type,orders_count,access_metadata",
        "fields[shows]": "id,title,description,thumbnail",
        "filter[campaign_id]": campaign_id,
        "filter[contains_exclusive_posts]": "true",
        "filter[is_draft]": "false",
        "filter[include_lives]": "true",
        "filter[include_drops]": "true",
        "sort": "-published_at",
        "json-api-use-default-includes": "false",
        "json-api-version": "1.0",
    }


def save_page_data(
    page_data: Dict, creator_name: str, page_number: int, cursor: str = None
) -> str:
    """Save a page of data to JSON file."""
    if cursor:
        cursor_hash = hashlib.md5(cursor.encode("utf-8")).hexdigest()[:12]
        filename = f"{creator_name}_page_{cursor_hash}_{page_number:03d}.json"
    else:
        timestamp = int(time.time())
        filename = f"{creator_name}_page_{timestamp}_{page_number:03d}.json"

    filepath = DATA_DIR / filename

    # Add metadata
    enhanced_data = {
        "metadata": {
            "creator_name": creator_name,
            "page_number": page_number,
            "cursor": cursor,
            "scraped_at": time.time(),
            "total_posts": len(page_data.get("data", [])),
            "included_items": len(page_data.get("included", [])),
        },
        "api_response": page_data,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(enhanced_data, f, indent=2, ensure_ascii=False)

    posts_count = len(page_data.get("data", []))
    included_count = len(page_data.get("included", []))
    print(
        f"Saved page {page_number} with {posts_count} posts and {included_count} included items to {filepath}"
    )
    return str(filepath)


def extract_media_from_post(post: Dict, creator_name: str) -> List[Dict]:
    """Extract media URLs from a single post."""
    media_info = []

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
                if isinstance(published_at, str):
                    if "T" in published_at:
                        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    else:
                        dt = datetime.fromisoformat(published_at)
                    post_date = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                post_date = str(published_at)[:10] if published_at else "unknown"

        # Check for post_file (audio files, podcasts, etc.)
        if "post_file" in attrs and attrs["post_file"]:
            post_file_data = attrs["post_file"]
            if isinstance(post_file_data, dict) and "url" in post_file_data:
                url = post_file_data["url"]

                # Determine file extension
                file_extension = "wav"  # Default for audio
                url_lower = url.lower()

                for ext in [
                    "wav",
                    "mp3",
                    "m4a",
                    "ogg",
                    "flac",
                    "mp4",
                    "webm",
                    "mov",
                    "avi",
                    "pdf",
                    "zip",
                    "rar",
                    "txt",
                ]:
                    if f".{ext}" in url_lower:
                        file_extension = ext
                        break

                # Generate filename
                clean_creator = re.sub(r"[^\w\-_]", "_", creator_name)
                clean_title = re.sub(r"[^\w\s]", "", str(post_title)).strip()
                clean_title = re.sub(r"\s+", "_", clean_title)[:50] or "untitled"

                filename = f"{clean_creator} - {post_date} - {post_id} - {clean_title}.{file_extension}"

                media_info.append(
                    {
                        "url": url,
                        "filename": filename,
                        "post_id": post_id,
                        "post_title": post_title,
                        "media_type": "post_file",
                        "file_extension": file_extension,
                        "duration": post_file_data.get("duration"),
                    }
                )

        # Check for direct image URLs
        if "image" in attrs and attrs["image"]:
            image_data = attrs["image"]
            if isinstance(image_data, dict):
                url = None
                if "large_url" in image_data:
                    url = image_data["large_url"]
                elif "url" in image_data:
                    url = image_data["url"]

                if url:
                    # Determine file extension
                    file_extension = "jpg"  # Default
                    url_lower = url.lower()
                    for ext in ["png", "jpeg", "jpg", "gif", "webp"]:
                        if f".{ext}" in url_lower:
                            file_extension = ext
                            break

                    # Generate filename
                    clean_creator = re.sub(r"[^\w\-_]", "_", creator_name)
                    clean_title = re.sub(r"[^\w\s]", "", str(post_title)).strip()
                    clean_title = re.sub(r"\s+", "_", clean_title)[:50] or "untitled"

                    filename = f"{clean_creator} - {post_date} - {post_id} - {clean_title}.{file_extension}"

                    media_info.append(
                        {
                            "url": url,
                            "filename": filename,
                            "post_id": post_id,
                            "post_title": post_title,
                            "media_type": "image",
                            "file_extension": file_extension,
                            "width": image_data.get("width"),
                            "height": image_data.get("height"),
                        }
                    )

    return media_info


def download_media(media_info_list: List[Dict], headers: Dict[str, str]) -> List[Dict]:
    """Download media files."""
    download_results = []

    for i, media_info in enumerate(media_info_list):
        url = media_info["url"]
        filename = media_info["filename"]
        post_id = media_info["post_id"]

        print(f"Downloading {i+1}/{len(media_info_list)}: {filename}")

        try:
            time.sleep(REQUEST_DELAY)
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            filepath = MEDIA_DIR / filename

            with open(filepath, "wb") as f:
                f.write(response.content)

            download_results.append(
                {
                    **media_info,
                    "filepath": str(filepath),
                    "size_bytes": len(response.content),
                    "success": True,
                }
            )

            print(f"  ✅ Downloaded {len(response.content):,} bytes")

        except Exception as e:
            print(f"  ❌ Error downloading: {e}")
            download_results.append(
                {
                    **media_info,
                    "filepath": None,
                    "size_bytes": 0,
                    "success": False,
                    "error": str(e),
                }
            )

    return download_results


def scrape_creator(
    creator_name: str, cookies_json: str, download_media_files: bool = True
) -> Dict:
    """Scrape all posts from a creator using cookies."""

    # Convert cookies to string
    cookie_string = cookies_json_to_string(cookies_json)
    if not cookie_string:
        raise ValueError("Failed to create cookie string from provided cookies")

    # Create headers
    headers = create_headers(cookie_string)
    print(f"Using authenticated cookies (length: {len(cookie_string)} characters)")

    # Find campaign ID
    campaign_id = find_campaign_id(creator_name, headers)

    # Get API parameters
    base_url = "https://www.patreon.com/api/posts"
    params = get_posts_api_params(campaign_id)

    # Start scraping
    all_posts = []
    all_media_info = []
    page_files = []
    page_number = 1
    current_cursor = None

    print(f"Starting to scrape posts for {creator_name}...")

    while True:
        # Add cursor to params if we have one
        current_params = params.copy()
        if current_cursor:
            current_params["page[cursor]"] = current_cursor

        print(f"Scraping page {page_number}...")

        try:
            time.sleep(REQUEST_DELAY)
            response = requests.get(base_url, headers=headers, params=current_params)
            response.raise_for_status()

            page_data = response.json()

            if "data" in page_data and page_data["data"]:
                posts = page_data["data"]
                if not isinstance(posts, list):
                    posts = [posts]

                print(f"  Found {len(posts)} posts on page {page_number}")

                # Save page data
                page_file = save_page_data(
                    page_data, creator_name, page_number, current_cursor
                )
                page_files.append(page_file)

                # Extract media from posts
                for post in posts:
                    all_posts.append(post)
                    media_info = extract_media_from_post(post, creator_name)
                    all_media_info.extend(media_info)

                # Check for next page
                next_cursor = None
                if "meta" in page_data and "pagination" in page_data["meta"]:
                    pagination = page_data["meta"]["pagination"]
                    if "cursors" in pagination and "next" in pagination["cursors"]:
                        next_cursor = pagination["cursors"]["next"]
                elif "links" in page_data and "next" in page_data["links"]:
                    next_url = page_data["links"]["next"]
                    if "page[cursor]=" in next_url:
                        next_cursor = next_url.split("page[cursor]=")[1].split("&")[0]

                if next_cursor:
                    current_cursor = next_cursor
                    page_number += 1
                else:
                    print("No more pages found")
                    break
            else:
                print(f"No data found on page {page_number}")
                break

        except requests.RequestException as e:
            print(f"Error scraping page {page_number}: {e}")
            break

    # Save complete dataset
    complete_file = None
    if all_posts:
        complete_data = {
            "metadata": {
                "creator_name": creator_name,
                "campaign_id": campaign_id,
                "total_posts": len(all_posts),
                "total_pages": len(page_files),
                "scraped_at": time.time(),
            },
            "posts": all_posts,
        }

        complete_file = DATA_DIR / f"{creator_name}_complete.json"
        with open(complete_file, "w", encoding="utf-8") as f:
            json.dump(complete_data, f, indent=2, ensure_ascii=False)

        print(f"Saved complete dataset with {len(all_posts)} posts to {complete_file}")

    # Download media if requested
    download_results = []
    if download_media_files and all_media_info:
        print(f"\nFound {len(all_media_info)} media items to download")
        download_results = download_media(all_media_info, headers)

        # Save download results
        media_results_file = DATA_DIR / f"{creator_name}_media_downloads.json"
        with open(media_results_file, "w", encoding="utf-8") as f:
            json.dump(download_results, f, indent=2, ensure_ascii=False)

        successful_downloads = len(
            [r for r in download_results if r.get("success", False)]
        )
        print(f"Download results saved to {media_results_file}")
        print(
            f"Successfully downloaded: {successful_downloads}/{len(download_results)} files"
        )

    return {
        "creator_name": creator_name,
        "campaign_id": campaign_id,
        "total_posts": len(all_posts),
        "total_pages": len(page_files),
        "media_found": len(all_media_info),
        "media_downloaded": len(
            [r for r in download_results if r.get("success", False)]
        ),
        "page_files": page_files,
        "complete_file": str(complete_file) if complete_file else None,
    }


def get_user_memberships(headers: Dict[str, str]) -> Dict:
    """
    Get all campaigns the current user has memberships with.

    Args:
        headers: HTTP headers with authentication

    Returns:
        Dict containing user data and campaign memberships
    """
    url = "https://www.patreon.com/api/current_user"
    params = {
        "include": "active_memberships.campaign",
        "fields[campaign]": "avatar_photo_image_urls,name,published_at,url,vanity,is_nsfw,url_for_current_user",
        "fields[member]": "is_free_member,is_free_trial",
        "json-api-version": "1.0",
        "json-api-use-default-includes": "false",
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user memberships: {e}")
        return {}


def extract_campaigns_from_memberships(membership_data: Dict) -> List[Dict]:
    """
    Extract campaign information from user membership data.

    Args:
        membership_data: Response from current_user API

    Returns:
        List of campaign dictionaries with membership info
    """
    campaigns = []

    if not membership_data or "data" not in membership_data:
        return campaigns

    # Create lookup for included data
    included_lookup = {}
    for item in membership_data.get("included", []):
        included_lookup[f"{item['type']}_{item['id']}"] = item

    # Get membership data
    memberships = (
        membership_data["data"]
        .get("relationships", {})
        .get("active_memberships", {})
        .get("data", [])
    )

    for membership_ref in memberships:
        member_id = membership_ref["id"]
        member_data = included_lookup.get(f"member_{member_id}")

        if not member_data:
            continue

        # Get campaign reference from member
        campaign_ref = (
            member_data.get("relationships", {}).get("campaign", {}).get("data")
        )
        if not campaign_ref:
            continue

        campaign_id = campaign_ref["id"]
        campaign_data = included_lookup.get(f"campaign_{campaign_id}")

        if not campaign_data:
            continue

        # Extract campaign info
        attributes = campaign_data.get("attributes", {})
        member_attributes = member_data.get("attributes", {})

        campaign_info = {
            "campaign_id": campaign_id,
            "name": attributes.get("name", ""),
            "vanity": attributes.get("vanity", ""),
            "url": attributes.get("url", ""),
            "url_for_current_user": attributes.get("url_for_current_user", ""),
            "is_nsfw": attributes.get("is_nsfw", False),
            "published_at": attributes.get("published_at", ""),
            "is_free_member": member_attributes.get("is_free_member", True),
            "is_free_trial": member_attributes.get("is_free_trial", False),
            "avatar_urls": attributes.get("avatar_photo_image_urls", {}),
        }

        campaigns.append(campaign_info)

    return campaigns


def list_user_campaigns(cookies_json: str) -> List[Dict]:
    """
    List all campaigns the user has memberships with.

    Args:
        cookies_json: JSON string of cookies from Copy Cookies extension

    Returns:
        List of campaign dictionaries
    """
    cookie_string = cookies_json_to_string(cookies_json)
    headers = create_headers(cookie_string)

    print("Fetching user memberships...")
    membership_data = get_user_memberships(headers)

    if not membership_data:
        print("Failed to fetch membership data")
        return []

    campaigns = extract_campaigns_from_memberships(membership_data)

    print(f"\nFound {len(campaigns)} campaigns:")
    print("-" * 80)

    for i, campaign in enumerate(campaigns, 1):
        membership_type = "FREE" if campaign["is_free_member"] else "PAID"
        nsfw_flag = " [NSFW]" if campaign["is_nsfw"] else ""

        print(f"{i:2d}. {campaign['name']}{nsfw_flag}")
        print(f"    Vanity: {campaign['vanity']}")
        print(f"    Campaign ID: {campaign['campaign_id']}")
        print(f"    Membership: {membership_type}")
        print(f"    URL: {campaign['url']}")
        print()

    return campaigns


def scrape_multiple_creators(
    cookies_json: str,
    creator_names: List[str] = None,
    download_media_files: bool = True,
    paid_only: bool = False,
) -> Dict:
    """
    Scrape multiple creators based on user memberships.

    Args:
        cookies_json: JSON string of cookies from Copy Cookies extension
        creator_names: Optional list of specific creator names to scrape
        download_media_files: Whether to download media files
        paid_only: If True, only scrape paid memberships

    Returns:
        Dictionary with results for each creator
    """
    cookie_string = cookies_json_to_string(cookies_json)
    headers = create_headers(cookie_string)

    # Get all user campaigns
    membership_data = get_user_memberships(headers)
    campaigns = extract_campaigns_from_memberships(membership_data)

    if not campaigns:
        print("No campaigns found")
        return {}

    # Filter campaigns
    if paid_only:
        campaigns = [c for c in campaigns if not c["is_free_member"]]
        print(f"Filtering to {len(campaigns)} paid memberships")

    if creator_names:
        # Filter by creator names (match vanity or name)
        creator_names_lower = [name.lower() for name in creator_names]
        campaigns = [
            c
            for c in campaigns
            if c["vanity"].lower() in creator_names_lower
            or c["name"].lower() in creator_names_lower
        ]
        print(f"Filtering to {len(campaigns)} specified creators")

    results = {}

    for i, campaign in enumerate(campaigns, 1):
        creator_name = campaign["vanity"] or campaign["name"]
        print(f"\n{'='*60}")
        print(f"Scraping {i}/{len(campaigns)}: {creator_name}")
        print(f"Campaign ID: {campaign['campaign_id']}")
        print(f"Membership: {'FREE' if campaign['is_free_member'] else 'PAID'}")
        print(f"{'='*60}")

        try:
            # Use the campaign ID directly instead of searching for it
            result = scrape_creator_with_campaign_id(
                creator_name=creator_name,
                campaign_id=campaign["campaign_id"],
                cookies_json=cookies_json,
                download_media_files=download_media_files,
            )
            results[creator_name] = result

        except Exception as e:
            print(f"Error scraping {creator_name}: {e}")
            results[creator_name] = {"error": str(e)}

        # Add delay between creators to be respectful
        if i < len(campaigns):
            print(f"Waiting 2 seconds before next creator...")
            time.sleep(2)

    return results


def scrape_creator_with_campaign_id(
    creator_name: str,
    campaign_id: str,
    cookies_json: str,
    download_media_files: bool = True,
) -> Dict:
    """
    Scrape a creator using a known campaign ID.

    Args:
        creator_name: Name of the creator
        campaign_id: Known campaign ID
        cookies_json: JSON string of cookies
        download_media_files: Whether to download media files

    Returns:
        Dictionary with scraping results
    """
    cookie_string = cookies_json_to_string(cookies_json)
    headers = create_headers(cookie_string)

    print(f"Using campaign ID: {campaign_id}")

    # Get API parameters
    params = get_posts_api_params(campaign_id)

    # Build initial URL
    base_url = "https://www.patreon.com/api/posts"

    all_posts = []
    all_media = []
    page_number = 1
    cursor = None

    while True:
        print(f"Fetching page {page_number}...")

        # Add cursor to params if we have one
        current_params = params.copy()
        if cursor:
            current_params["page[cursor]"] = cursor

        try:
            response = requests.get(base_url, headers=headers, params=current_params)
            response.raise_for_status()
            page_data = response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {page_number}: {e}")
            break

        # Save page data
        filename = save_page_data(page_data, creator_name, page_number, cursor)
        print(f"Saved page data to: {filename}")

        # Extract posts from this page
        posts = page_data.get("data", [])
        if not posts:
            print("No posts found on this page")
            break

        all_posts.extend(posts)
        print(f"Found {len(posts)} posts on page {page_number}")

        # Extract media from posts
        for post in posts:
            media_items = extract_media_from_post(post, creator_name)
            all_media.extend(media_items)

        # Check for next page
        next_cursor = (
            page_data.get("meta", {})
            .get("pagination", {})
            .get("cursors", {})
            .get("next")
        )
        if not next_cursor:
            print("No more pages")
            break

        cursor = next_cursor
        page_number += 1

        # Add delay between requests
        time.sleep(1)

    print(f"\nScraping complete!")
    print(f"Total posts: {len(all_posts)}")
    print(f"Total media items: {len(all_media)}")

    # Download media if requested
    download_results = []
    if download_media_files and all_media:
        print(f"\nDownloading {len(all_media)} media files...")
        download_results = download_media(all_media, headers)

    return {
        "creator_name": creator_name,
        "campaign_id": campaign_id,
        "total_posts": len(all_posts),
        "total_media": len(all_media),
        "downloaded_files": len([r for r in download_results if r.get("success")]),
        "failed_downloads": len([r for r in download_results if not r.get("success")]),
        "download_results": download_results,
    }


def main():
    """Main function for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Patreon scraper using cookies")

    # Create subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Single creator scraping
    single_parser = subparsers.add_parser("single", help="Scrape a single creator")
    single_parser.add_argument("creator_name", help="Creator name (vanity URL)")
    single_parser.add_argument(
        "--cookies-file",
        required=True,
        help="Path to JSON file with cookies from Copy Cookies extension",
    )
    single_parser.add_argument(
        "--no-download",
        action="store_true",
        help="Don't download media files, just extract URLs",
    )

    # List campaigns
    list_parser = subparsers.add_parser(
        "list", help="List all campaigns you have memberships with"
    )
    list_parser.add_argument(
        "--cookies-file",
        required=True,
        help="Path to JSON file with cookies from Copy Cookies extension",
    )

    # Multiple creator scraping
    multi_parser = subparsers.add_parser("multi", help="Scrape multiple creators")
    multi_parser.add_argument(
        "--cookies-file",
        required=True,
        help="Path to JSON file with cookies from Copy Cookies extension",
    )
    multi_parser.add_argument(
        "--creators", nargs="+", help="Specific creator names to scrape (optional)"
    )
    multi_parser.add_argument(
        "--paid-only", action="store_true", help="Only scrape paid memberships"
    )
    multi_parser.add_argument(
        "--no-download",
        action="store_true",
        help="Don't download media files, just extract URLs",
    )

    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return

    # Read cookies file
    try:
        with open(args.cookies_file, "r", encoding="utf-8") as f:
            cookies_json = f.read()
    except FileNotFoundError:
        print(f"Error: Cookies file not found: {args.cookies_file}")
        return
    except Exception as e:
        print(f"Error reading cookies file: {e}")
        return

    # Execute command
    if args.command == "single":
        # Single creator scraping
        download_media_files = not args.no_download
        result = scrape_creator(args.creator_name, cookies_json, download_media_files)

        # Print summary
        print(f"\n{'='*60}")
        print("SCRAPING SUMMARY")
        print(f"{'='*60}")
        print(f"Creator: {result['creator_name']}")
        print(f"Campaign ID: {result['campaign_id']}")
        print(f"Total posts: {result['total_posts']}")
        print(f"Total pages: {result['total_pages']}")
        print(f"Media found: {result['media_found']}")
        print(f"Media downloaded: {result['media_downloaded']}")

        if result.get("complete_file"):
            print(f"Complete dataset: {result['complete_file']}")

        print(f"Page files: {len(result.get('page_files', []))}")
        print(f"{'='*60}")

    elif args.command == "list":
        # List campaigns
        campaigns = list_user_campaigns(cookies_json)

        if campaigns:
            print(f"\nSummary:")
            total_campaigns = len(campaigns)
            paid_campaigns = len([c for c in campaigns if not c["is_free_member"]])
            free_campaigns = total_campaigns - paid_campaigns
            nsfw_campaigns = len([c for c in campaigns if c["is_nsfw"]])

            print(f"Total campaigns: {total_campaigns}")
            print(f"Paid memberships: {paid_campaigns}")
            print(f"Free memberships: {free_campaigns}")
            print(f"NSFW campaigns: {nsfw_campaigns}")

    elif args.command == "multi":
        # Multiple creator scraping
        download_media_files = not args.no_download
        results = scrape_multiple_creators(
            cookies_json=cookies_json,
            creator_names=args.creators,
            download_media_files=download_media_files,
            paid_only=args.paid_only,
        )

        # Print summary
        print(f"\n{'='*80}")
        print("MULTI-CREATOR SCRAPING SUMMARY")
        print(f"{'='*80}")

        total_posts = 0
        total_media = 0
        total_downloaded = 0
        total_failed = 0
        successful_creators = 0

        for creator_name, result in results.items():
            if "error" in result:
                print(f"❌ {creator_name}: {result['error']}")
            else:
                print(f"✅ {creator_name}:")
                print(f"   Posts: {result['total_posts']}")
                print(f"   Media: {result['total_media']}")
                if download_media_files:
                    print(f"   Downloaded: {result['downloaded_files']}")
                    print(f"   Failed: {result['failed_downloads']}")

                total_posts += result["total_posts"]
                total_media += result["total_media"]
                total_downloaded += result.get("downloaded_files", 0)
                total_failed += result.get("failed_downloads", 0)
                successful_creators += 1

        print(f"\n{'='*80}")
        print(f"TOTALS:")
        print(f"Successful creators: {successful_creators}/{len(results)}")
        print(f"Total posts: {total_posts}")
        print(f"Total media items: {total_media}")
        if download_media_files:
            print(f"Total downloaded: {total_downloaded}")
            print(f"Total failed: {total_failed}")
        print(f"{'='*80}")


if __name__ == "__main__":
    main()
