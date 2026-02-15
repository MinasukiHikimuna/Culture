import json
import os
import re
from datetime import UTC, datetime
from urllib.parse import urlencode

import newnewid
from dotenv import load_dotenv
from itemadapter import ItemAdapter

import scrapy
from cultureextractorscrapy.items import (
    AvailableAudioFile,
    AvailableFileEncoder,
    AvailableImageFile,
    AvailableVideoFile,
    DirectDownloadItem,
    ReleaseItem,
)
from cultureextractorscrapy.spiders.database import (
    get_existing_releases_with_status,
    get_or_create_sub_site,
    get_site_item,
)
from cultureextractorscrapy.utils import get_log_filename

load_dotenv()

# Patreon configuration from environment
patreon_cookies_json = os.getenv("PATREON_COOKIES", "[]")
base_url = "https://www.patreon.com"


class PatreonSpider(scrapy.Spider):
    name = "patreon"
    allowed_domains = ["patreon.com", "www.patreon.com"]
    start_urls = [base_url]
    site_short_name = "patreon"

    # Custom settings to handle long Patreon API URLs
    custom_settings = {
        "URLLENGTH_LIMIT": 4000,  # Override default 2083 limit for Patreon API
    }

    # Hardcoded list of target campaigns (vanity names or campaign names)
    # Add the campaigns you want to scrape here
    target_campaigns = ["alekirser"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_delay = 1.0  # seconds between requests
        self.campaigns = []  # Store discovered campaigns

        # Test mode: only process first 10 posts for testing
        self.test_mode = False
        self.test_max_posts = 10
        if self.test_mode:
            self.logger.info(
                f"🧪 TEST MODE ENABLED: Will only process {self.test_max_posts} posts from 1 page"
            )

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)

        # Set the log file using the spider name
        crawler.settings.set("LOG_FILE", get_log_filename(spider.name))

        # Get force_update from crawler settings or default to False
        spider.force_update = crawler.settings.getbool("FORCE_UPDATE", False)

        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(
                f"Site with short_name '{spider.site_short_name}' not found in the database."
            )
        spider.site = site_item

        # Get existing releases with their download status
        spider.existing_releases = get_existing_releases_with_status(site_item.id)

        # Convert cookies from JSON format to Scrapy format
        spider.cookies = spider._convert_cookies_from_json(patreon_cookies_json)

        return spider

    def _convert_cookies_from_json(self, cookies_json_str):
        """Convert cookies from Copy Cookies plugin JSON format to Scrapy cookie dict."""
        try:
            cookies_list = json.loads(cookies_json_str)
            cookies_dict = {}

            for cookie in cookies_list:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    cookies_dict[name] = value

            self.logger.info(
                f"Converted {len(cookies_list)} cookies for authentication"
            )
            return cookies_dict

        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing cookies JSON: {e}")
            return {}

    def _create_authenticated_headers(self):
        """Create headers for authenticated requests."""
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
        }

    async def start(self):
        """Begin with campaign discovery."""
        headers = self._create_authenticated_headers()

        # Parameters for the current_user API call
        params = {
            "include": "active_memberships.campaign",
            "fields[campaign]": "avatar_photo_image_urls,name,published_at,url,vanity,is_nsfw,url_for_current_user",
            "fields[member]": "is_free_member,is_free_trial",
            "json-api-version": "1.0",
            "json-api-use-default-includes": "false",
        }

        # Construct URL with query parameters
        query_string = urlencode(params)
        api_url = f"{base_url}/api/current_user?{query_string}"

        # First, get user memberships to discover available campaigns
        yield scrapy.Request(
            url=api_url,
            callback=self.parse_user_memberships,
            headers=headers,
            cookies=self.cookies,
            dont_filter=True,
        )

    def parse_user_memberships(self, response):
        """Parse user memberships to discover available campaigns."""
        try:
            data = response.json()
            all_campaigns = self._extract_campaigns_from_memberships(data)

            self.logger.info(
                f"Found {len(all_campaigns)} total campaigns with memberships"
            )

            # Filter campaigns based on target list
            if self.target_campaigns:
                target_campaigns_lower = [
                    name.lower() for name in self.target_campaigns
                ]
                filtered_campaigns = []

                for campaign in all_campaigns:
                    vanity = campaign["vanity"].lower()
                    name = campaign["name"].lower()

                    if (
                        vanity in target_campaigns_lower
                        or name in target_campaigns_lower
                    ):
                        filtered_campaigns.append(campaign)
                        self.logger.info(
                            f"✅ Target campaign found: {campaign['name']} ({campaign['vanity']})"
                        )
                    else:
                        self.logger.debug(
                            f"⏭️  Skipping campaign: {campaign['name']} ({campaign['vanity']}) - not in target list"
                        )

                campaigns = filtered_campaigns
                self.logger.info(f"Filtered to {len(campaigns)} target campaigns")

                # Log any target campaigns that weren't found
                found_vanities = [c["vanity"].lower() for c in campaigns]
                found_names = [c["name"].lower() for c in campaigns]

                for target in self.target_campaigns:
                    target_lower = target.lower()
                    if (
                        target_lower not in found_vanities
                        and target_lower not in found_names
                    ):
                        self.logger.warning(
                            f"⚠️  Target campaign '{target}' not found in your memberships"
                        )
            else:
                campaigns = []
                self.logger.info(
                    "No target campaigns specified - not processing any campaigns"
                )

            # Log campaign details for campaigns we'll process
            if campaigns:
                self.logger.info("Campaigns to be processed:")
                for i, campaign in enumerate(campaigns, 1):
                    membership_type = "FREE" if campaign["is_free_member"] else "PAID"
                    nsfw_flag = " [NSFW]" if campaign["is_nsfw"] else ""

                    self.logger.info(f"{i:2d}. {campaign['name']}{nsfw_flag}")
                    self.logger.info(f"    Vanity: {campaign['vanity']}")
                    self.logger.info(f"    Campaign ID: {campaign['campaign_id']}")
                    self.logger.info(f"    Membership: {membership_type}")
                    self.logger.info(f"    URL: {campaign['url']}")
            else:
                self.logger.warning("No campaigns to process!")
                return

            # Store campaigns for later use
            self.campaigns = campaigns

            # Start scraping posts for each campaign
            for campaign in campaigns:
                self.logger.info(
                    f"Starting post scraping for campaign: {campaign['name']} (will create subsite: {campaign.get('vanity', campaign['campaign_id'])})"
                )
                yield from self._start_campaign_scraping(campaign)

                # In test mode, only process the first campaign
                if self.test_mode:
                    self.logger.info("🧪 TEST MODE: Processing only the first campaign")
                    break

        except Exception as e:
            self.logger.error(f"Error parsing user memberships: {e}")

    def _extract_campaigns_from_memberships(self, membership_data):
        """Extract campaign information from user membership data."""
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

    def _start_campaign_scraping(self, campaign):
        """Start scraping posts for a specific campaign."""
        campaign_id = campaign["campaign_id"]
        campaign_name = campaign["name"]

        # Get API parameters for posts (using the actual comprehensive API)
        params = self._get_posts_api_params(campaign_id)

        # Use the original API endpoint with comprehensive parameters
        base_url = "https://www.patreon.com/api/posts"
        query_string = urlencode(params)
        full_url = f"{base_url}?{query_string}"
        headers = self._create_authenticated_headers()

        self.logger.info(
            f"Requesting posts for campaign {campaign_name} (ID: {campaign_id})"
        )

        # Make initial request
        yield scrapy.Request(
            url=full_url,
            headers=headers,
            cookies=self.cookies,
            callback=self.parse_posts_page,
            meta={
                "campaign": campaign,
                "page_number": 1,
                "cursor": None,
                "base_url": base_url,
                "headers": headers,
                "params": params,
            },
            dont_filter=True,
        )

    def _get_posts_api_params(self, campaign_id):
        """Get comprehensive parameters for Patreon posts API (actual working version)."""
        return {
            "include": "campaign,access_rules,access_rules.tier.null,attachments_media,audio,audio_preview.null,custom_thumbnail_media.null,drop,images,media,native_video_insights,poll.choices,poll.current_user_responses.user,poll.current_user_responses.choice,poll.current_user_responses.poll,shows.null,user,user_defined_tags,video.null,content_unlock_options.product_variant.null,content_unlock_options.reward.null,content_unlock_options.product_variant.collection.null,livestream,livestream.state,livestream.display,rss_synced_feed",
            "fields[campaign]": "currency,show_audio_post_download_links,avatar_photo_url,avatar_photo_image_urls,earnings_visibility,is_nsfw,is_monthly,name,url,patron_count,primary_theme_color",
            "fields[post]": "change_visibility_at,comment_count,commenter_count,content,created_at,current_user_can_comment,current_user_can_delete,current_user_can_report,current_user_can_view,current_user_comment_disallowed_reason,current_user_has_liked,embed,image,insights_last_updated_at,is_paid,is_preview_blurred,has_custom_thumbnail,like_count,meta_image_url,min_cents_pledged_to_view,monetization_ineligibility_reason,post_file,post_metadata,published_at,patreon_url,post_type,pledge_url,preview_asset_type,thumbnail,thumbnail_url,teaser_text,content_teaser_text,cleaned_teaser_text,title,upgrade_url,url,was_posted_by_campaign_owner,has_ti_violation,moderation_status,post_level_suspension_removal_date,pls_one_liners_by_category,video,video_preview,view_count,content_unlock_options,is_new_to_current_user,watch_state",
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

    def parse_posts_page(self, response):
        """Parse a page of posts from the Patreon API."""
        try:
            data = response.json()
            campaign = response.meta["campaign"]
            page_number = response.meta["page_number"]

            posts = data.get("data", [])
            self.logger.info(
                f"Processing page {page_number} with {len(posts)} posts for campaign {campaign['name']}"
            )

            if not posts:
                self.logger.info(
                    f"No posts found on page {page_number} for campaign {campaign['name']}"
                )
                return

            # In test mode, only process the first posts
            if self.test_mode:
                posts = posts[: self.test_max_posts]
                self.logger.info(
                    f"🧪 TEST MODE: Processing only the first {len(posts)} posts"
                )

            # Process each post
            for post in posts:
                yield from self._process_post(post, campaign, data.get("included", []))

            # Skip pagination in test mode
            if self.test_mode:
                self.logger.info("🧪 TEST MODE: Skipping pagination - test complete!")
                return

            # Check for next page
            next_cursor = self._get_next_page_cursor(data)
            if next_cursor:
                self.logger.info(
                    f"Found next page cursor for campaign {campaign['name']}"
                )

                # Add cursor to params for next request
                params = response.meta["params"].copy()
                params["page[cursor]"] = (
                    next_cursor  # Use the actual cursor value, not "null"
                )

                # Build URL with cursor
                query_string = urlencode(params)
                full_url = f"{response.meta['base_url']}?{query_string}"

                yield scrapy.Request(
                    url=full_url,
                    headers=response.meta["headers"],
                    cookies=self.cookies,
                    callback=self.parse_posts_page,
                    meta={
                        **response.meta,
                        "page_number": page_number + 1,
                        "cursor": next_cursor,
                        "params": params,
                    },
                    dont_filter=True,
                )
            else:
                self.logger.info(f"No more pages found for campaign {campaign['name']}")

        except Exception as e:
            self.logger.error(f"Error parsing posts page: {e}")

    def _get_next_page_cursor(self, data):
        """Extract next page cursor from API response."""
        try:
            return (
                data.get("meta", {})
                .get("pagination", {})
                .get("cursors", {})
                .get("next")
            )
        except (KeyError, TypeError):
            return None

    def _process_post(self, post, campaign, included_data):
        """Process a single post and extract media information."""
        try:
            post_id = post.get("id")
            post_type = post.get("type")

            if post_type != "post":
                return

            attributes = post.get("attributes", {})

            # Extract basic post information
            title = attributes.get("title", "")
            content = attributes.get("content", "")
            published_at = attributes.get("published_at", "")
            post_url = attributes.get("patreon_url", "")

            # Generate external ID and release ID
            external_id = f"post-{post_id}"
            release_id = newnewid.uuid7()

            # Create or get subsite for this campaign
            campaign_vanity = campaign.get("vanity", "").strip()

            sub_site_short_name = f"campaign-{campaign['campaign_id']}"
            sub_site_name = campaign_vanity

            sub_site = get_or_create_sub_site(
                site_uuid=str(self.site.id),
                short_name=sub_site_short_name,
                name=sub_site_name,
            )

            self.logger.debug(f"Using subsite: {sub_site.name} ({sub_site.short_name})")

            # Check if we already have this release
            existing_release = self.existing_releases.get(external_id)
            if existing_release and not self.force_update:
                # Compare available files with downloaded files
                available_files = existing_release["available_files"]
                downloaded_files = existing_release["downloaded_files"]

                needed_files = {
                    (f["file_type"], f["content_type"], f["variant"])
                    for f in available_files
                }

                if not needed_files.issubset(downloaded_files):
                    # We have missing files - yield DirectDownloadItems
                    missing_files = [
                        f
                        for f in available_files
                        if (f["file_type"], f["content_type"], f["variant"])
                        not in downloaded_files
                    ]

                    for file in missing_files:
                        yield DirectDownloadItem(
                            release_id=existing_release["uuid"],
                            file_info=file,
                            url=file["url"],
                        )
                    self.logger.info(
                        f"Release {external_id} exists but missing {len(missing_files)} files. Downloading them."
                    )
                else:
                    self.logger.info(
                        f"Release {external_id} already exists with all files downloaded. Skipping."
                    )
                return

            # Parse publication date
            release_date = self._parse_post_date(published_at)

            # Extract media from post
            available_files = []
            download_items = []

            # Extract media files from the post
            media_files = self._extract_media_from_post(post, campaign, included_data)
            for media_info in media_files:
                if media_info["file_type"] == "image":
                    file_obj = AvailableImageFile(
                        file_type=media_info["file_type"],
                        content_type=media_info["content_type"],
                        variant=media_info["variant"],
                        url=media_info["url"],
                        resolution_width=media_info.get("width"),
                        resolution_height=media_info.get("height"),
                    )
                elif media_info["file_type"] == "video":
                    file_obj = AvailableVideoFile(
                        file_type=media_info["file_type"],
                        content_type=media_info["content_type"],
                        variant=media_info["variant"],
                        url=media_info["url"],
                        resolution_width=media_info.get("width"),
                        resolution_height=media_info.get("height"),
                    )
                elif media_info["file_type"] == "audio":
                    file_obj = AvailableAudioFile(
                        file_type=media_info["file_type"],
                        content_type=media_info["content_type"],
                        variant=media_info["variant"],
                        url=media_info["url"],
                        duration=media_info.get("duration"),
                        # Additional audio metadata could be populated later via ffprobe
                        bitrate=media_info.get("bitrate"),
                        sample_rate=media_info.get("sample_rate"),
                        channels=media_info.get("channels"),
                        codec=media_info.get("codec"),
                    )
                else:
                    # Skip unknown file types and log them
                    self.logger.info(
                        f"Skipping file with unknown type '{media_info['file_type']}': {media_info['url']}"
                    )
                    continue

                available_files.append(file_obj)
                download_items.append(
                    DirectDownloadItem(
                        release_id=str(release_id),
                        file_info=ItemAdapter(file_obj).asdict(),
                        url=file_obj.url,
                    )
                )

            # Create JSON document with post metadata
            json_document = {
                "external_id": external_id,
                "post_id": post_id,
                "title": title,
                "content": content,
                "published_at": published_at,
                "post_url": post_url,
                "campaign_id": campaign["campaign_id"],
                "campaign_name": campaign["name"],
                "raw_post_data": post,
            }

            # Create ReleaseItem
            release_item = ReleaseItem(
                id=release_id,
                release_date=release_date,
                short_name=external_id,
                name=title or f"Post {post_id}",
                url=post_url,
                description=content[:500] if content else "",  # Truncate description
                duration=0,  # Posts don't have duration
                created=datetime.now(tz=UTC).astimezone(),
                last_updated=datetime.now(tz=UTC).astimezone(),
                performers=[],  # Patreon posts don't have performers in the traditional sense
                tags=[],  # We could extract tags from content later
                available_files=json.dumps(available_files, cls=AvailableFileEncoder),
                json_document=json.dumps(json_document),
                site_uuid=self.site.id,
                site=self.site,
                sub_site_uuid=sub_site.id,
                sub_site=sub_site,
            )

            # First yield the ReleaseItem
            yield release_item

            # Then yield all DirectDownloadItems
            yield from download_items

            self.logger.info(
                f"Processed post {external_id} with {len(available_files)} media files for subsite '{sub_site.name}'"
            )

        except Exception as e:
            self.logger.error(f"Error processing post {post.get('id', 'unknown')}: {e}")

    def _parse_post_date(self, published_at):
        """Parse post publication date to YYYY-MM-DD format."""
        if not published_at:
            return datetime.now().strftime("%Y-%m-%d")

        try:
            if isinstance(published_at, str):
                if "T" in published_at:
                    dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(published_at)
                return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            self.logger.warning(f"Could not parse date: {published_at}")
            return datetime.now().strftime("%Y-%m-%d")

        return datetime.now().strftime("%Y-%m-%d")

    def _extract_media_from_post(self, post, campaign, included_data):
        """Extract media URLs from a single post."""
        media_info = []
        seen_urls = set()  # Track URLs to avoid duplicates
        url_to_hash = {}  # Map URLs to their unique hashes

        attributes = post.get("attributes", {})

        def extract_unique_hash_from_url(url):
            """Extract unique hash from Patreon media URL."""

            # Look for the hash pattern in Patreon URLs: /post/POST_ID/HASH/
            match = re.search(r"/post/\d+/([a-f0-9]{32})/", url)
            if match:
                return match.group(1)
            # Fallback: try to extract any 32-character hex string
            match = re.search(r"([a-f0-9]{32})", url)
            if match:
                return match.group(1)
            return None

        def add_media_if_unique(media_item):
            """Add media item only if URL hasn't been seen before."""
            url = media_item["url"]

            # Extract unique hash from URL
            unique_hash = extract_unique_hash_from_url(url)
            if unique_hash:
                # Check if we've already processed this hash
                existing_url = url_to_hash.get(unique_hash)
                if existing_url:
                    # Same hash = same image, skip duplicate
                    return False
                else:
                    # New hash, add to tracking
                    url_to_hash[unique_hash] = url
                    # Update variant to include hash for unique filenames
                    media_item["variant"] = f"{media_item['variant']}-{unique_hash[:8]}"
            else:
                # No hash found, use URL as fallback
                if url in seen_urls:
                    return False
                seen_urls.add(url)

            media_info.append(media_item)
            return True

        # Check for post_file (audio files, podcasts, etc.)
        if "post_file" in attributes and attributes["post_file"]:
            post_file_data = attributes["post_file"]
            if isinstance(post_file_data, dict) and "url" in post_file_data:
                url = post_file_data["url"]

                # Determine file extension
                file_extension = "unknown"
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
                    "jpg",
                    "png",
                    "gif",
                    "webp",
                    "jpeg",
                ]:
                    if f".{ext}" in url_lower:
                        file_extension = ext
                        break

                # Determine file type category
                file_type = "unknown"
                if file_extension in ["wav", "mp3", "m4a", "ogg", "flac"]:
                    file_type = "audio"
                elif file_extension in ["mp4", "webm", "mov", "avi"]:
                    file_type = "video"
                elif file_extension in ["jpg", "png", "gif", "webp", "jpeg"]:
                    file_type = "image"
                elif file_extension in ["pdf", "zip", "rar", "txt"]:
                    file_type = "document"

                # Extract codec from file extension for audio files
                codec = None
                if file_type == "audio":
                    codec_mapping = {
                        "mp3": "mp3",
                        "m4a": "aac",
                        "ogg": "vorbis",
                        "flac": "flac",
                        "wav": "pcm",
                    }
                    codec = codec_mapping.get(file_extension, file_extension)

                # Get dimensions from post_file if available (for images)
                width = post_file_data.get("width")
                height = post_file_data.get("height")

                add_media_if_unique(
                    {
                        "url": url,
                        "file_type": file_type,
                        "content_type": "post_file",
                        "variant": file_extension,
                        "file_extension": file_extension,
                        "duration": post_file_data.get("duration"),
                        "codec": codec,
                        "width": width,
                        "height": height,
                    }
                )

        # Check for direct image URLs
        if "image" in attributes and attributes["image"]:
            image_data = attributes["image"]
            if isinstance(image_data, dict):
                url = None
                width = None
                height = None

                if "large_url" in image_data:
                    url = image_data["large_url"]
                elif "url" in image_data:
                    url = image_data["url"]

                if url:
                    width = image_data.get("width")
                    height = image_data.get("height")

                    # Determine file extension
                    file_extension = "jpg"  # Default
                    url_lower = url.lower()
                    for ext in ["png", "jpeg", "jpg", "gif", "webp"]:
                        if f".{ext}" in url_lower:
                            file_extension = ext
                            break

                    add_media_if_unique(
                        {
                            "url": url,
                            "file_type": "image",
                            "content_type": "post_image",
                            "variant": file_extension,
                            "file_extension": file_extension,
                            "width": width,
                            "height": height,
                        }
                    )

        # Check for media relationships (attachments, images, etc.)
        relationships = post.get("relationships", {})

        # Process media from relationships (prioritize this over images to avoid duplicates)
        if "media" in relationships:
            media_refs = relationships["media"].get("data", [])
            for media_ref in media_refs:
                media_item = self._find_included_item(
                    included_data, media_ref["type"], media_ref["id"]
                )
                if media_item:
                    attrs = media_item.get("attributes", {})

                    # Check for image_urls first (for images)
                    image_urls = attrs.get("image_urls", {})
                    if image_urls:
                        # Try to get the best quality image
                        for quality in [
                            "original",
                            "default",
                            "large",
                            "medium",
                            "small",
                        ]:
                            if quality in image_urls:
                                url = image_urls[quality]

                                # Get dimensions from metadata if available
                                metadata = attrs.get("metadata", {})
                                dimensions = (
                                    metadata.get("dimensions", {}) if metadata else {}
                                )
                                width = dimensions.get("w") if dimensions else None
                                height = dimensions.get("h") if dimensions else None

                                # Determine file extension from URL
                                file_extension = "jpg"  # Default
                                url_lower = url.lower()
                                for ext in ["png", "jpeg", "jpg", "gif", "webp"]:
                                    if f".{ext}" in url_lower:
                                        file_extension = ext
                                        break

                                add_media_if_unique(
                                    {
                                        "url": url,
                                        "file_type": "image",
                                        "content_type": "media",
                                        "variant": quality,
                                        "file_extension": file_extension,
                                        "width": width,
                                        "height": height,
                                    }
                                )
                                break

                    # Check for download_url (for other file types)
                    elif "download_url" in attrs:
                        download_url = attrs.get("download_url")
                        file_name = attrs.get("file_name", "")

                        if download_url:
                            # Determine file type from filename or URL
                            file_extension = "unknown"
                            if file_name:
                                if "." in file_name:
                                    file_extension = file_name.split(".")[-1].lower()
                            else:
                                # Try to extract from URL
                                url_lower = download_url.lower()
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
                                    "jpg",
                                    "png",
                                    "gif",
                                    "webp",
                                    "jpeg",
                                ]:
                                    if f".{ext}" in url_lower:
                                        file_extension = ext
                                        break

                            # Determine file type category
                            file_type = "unknown"
                            if file_extension in ["wav", "mp3", "m4a", "ogg", "flac"]:
                                file_type = "audio"
                            elif file_extension in ["mp4", "webm", "mov", "avi"]:
                                file_type = "video"
                            elif file_extension in [
                                "jpg",
                                "png",
                                "gif",
                                "webp",
                                "jpeg",
                            ]:
                                file_type = "image"
                            elif file_extension in ["pdf", "zip", "rar", "txt"]:
                                file_type = "document"

                            # Extract codec from file extension for audio files
                            codec = None
                            if file_type == "audio":
                                codec_mapping = {
                                    "mp3": "mp3",
                                    "m4a": "aac",
                                    "ogg": "vorbis",
                                    "flac": "flac",
                                    "wav": "pcm",
                                }
                                codec = codec_mapping.get(
                                    file_extension, file_extension
                                )

                            # Get dimensions from metadata if available
                            metadata = attrs.get("metadata", {})
                            dimensions = (
                                metadata.get("dimensions", {}) if metadata else {}
                            )
                            width = dimensions.get("w") if dimensions else None
                            height = dimensions.get("h") if dimensions else None

                            add_media_if_unique(
                                {
                                    "url": download_url,
                                    "file_type": file_type,
                                    "content_type": "media",
                                    "variant": file_extension,
                                    "file_extension": file_extension,
                                    "file_name": file_name,
                                    "codec": codec,
                                    "width": width,
                                    "height": height,
                                }
                            )

        # Process images from relationships only if not already processed via media
        # (this is for backwards compatibility with older posts that might not use media relationship)
        if "images" in relationships and "media" not in relationships:
            image_refs = relationships["images"].get("data", [])
            for image_ref in image_refs:
                media_item = self._find_included_item(
                    included_data, image_ref["type"], image_ref["id"]
                )
                if media_item:
                    image_urls = media_item.get("attributes", {}).get("image_urls", {})
                    if image_urls:
                        # Try to get the best quality image
                        for quality in ["original", "large", "medium", "small"]:
                            if quality in image_urls:
                                url = image_urls[quality]
                                add_media_if_unique(
                                    {
                                        "url": url,
                                        "file_type": "image",
                                        "content_type": "attachment",
                                        "variant": quality,
                                        "file_extension": "jpg",  # Default assumption
                                    }
                                )
                                break

        # Process attachments_media from relationships
        if "attachments_media" in relationships:
            attachment_refs = relationships["attachments_media"].get("data", [])
            for attachment_ref in attachment_refs:
                media_item = self._find_included_item(
                    included_data, attachment_ref["type"], attachment_ref["id"]
                )
                if media_item:
                    attrs = media_item.get("attributes", {})
                    download_url = attrs.get("download_url")
                    file_name = attrs.get("file_name", "")

                    if download_url:
                        # Determine file type from filename or URL
                        file_extension = "unknown"
                        if file_name:
                            if "." in file_name:
                                file_extension = file_name.split(".")[-1].lower()
                        else:
                            # Try to extract from URL
                            url_lower = download_url.lower()
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
                                "jpg",
                                "png",
                                "gif",
                                "webp",
                                "jpeg",
                            ]:
                                if f".{ext}" in url_lower:
                                    file_extension = ext
                                    break

                        # Determine file type category
                        file_type = "unknown"
                        if file_extension in ["wav", "mp3", "m4a", "ogg", "flac"]:
                            file_type = "audio"
                        elif file_extension in ["mp4", "webm", "mov", "avi"]:
                            file_type = "video"
                        elif file_extension in ["jpg", "png", "gif", "webp", "jpeg"]:
                            file_type = "image"
                        elif file_extension in ["pdf", "zip", "rar", "txt"]:
                            file_type = "document"

                        # Extract codec from file extension for audio files
                        codec = None
                        if file_type == "audio":
                            codec_mapping = {
                                "mp3": "mp3",
                                "m4a": "aac",
                                "ogg": "vorbis",
                                "flac": "flac",
                                "wav": "pcm",
                            }
                            codec = codec_mapping.get(file_extension, file_extension)

                        add_media_if_unique(
                            {
                                "url": download_url,
                                "file_type": file_type,
                                "content_type": "attachment",
                                "variant": file_extension,
                                "file_extension": file_extension,
                                "file_name": file_name,
                                "codec": codec,
                            }
                        )

        return media_info

    def _find_included_item(self, included_data, item_type, item_id):
        """Find an item in the included data section by type and ID."""
        for item in included_data:
            if item.get("type") == item_type and item.get("id") == item_id:
                return item
        return None

    def _extract_audio_metadata_with_ffprobe(self, file_path):
        """
        Extract audio metadata using ffprobe.
        This method can be called after a file is downloaded to get detailed metadata.

        NOTE: Audio metadata extraction is now integrated into the AvailableFilesPipeline
        in pipelines.py via the process_audio_metadata() method. This method is kept
        here as a reference implementation that could be used for pre-download analysis.

        Args:
            file_path: Path to the downloaded audio file

        Returns:
            Dict with audio metadata (duration, bitrate, sample_rate, channels, codec)
        """
        try:
            import json
            import subprocess

            # Run ffprobe to get audio metadata
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "a:0",  # Select first audio stream
                file_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])

                if streams:
                    audio_stream = streams[0]

                    # Extract metadata
                    duration = float(audio_stream.get("duration", 0))
                    bit_rate = (
                        int(audio_stream.get("bit_rate", 0))
                        if audio_stream.get("bit_rate")
                        else None
                    )
                    sample_rate = (
                        int(audio_stream.get("sample_rate", 0))
                        if audio_stream.get("sample_rate")
                        else None
                    )
                    channels = (
                        int(audio_stream.get("channels", 0))
                        if audio_stream.get("channels")
                        else None
                    )
                    codec = audio_stream.get("codec_name", "")

                    return {
                        "duration": duration,
                        "bitrate": (
                            bit_rate // 1000 if bit_rate else None
                        ),  # Convert to kbps
                        "sample_rate": sample_rate,
                        "channels": channels,
                        "codec": codec,
                    }

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            ImportError,
        ) as e:
            self.logger.warning(
                f"Could not extract audio metadata from {file_path}: {e}"
            )

        return {}

    def _calculate_file_hash(self, file_path):
        """
        Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            SHA-256 hash as hexadecimal string, or None if error
        """
        try:
            import hashlib

            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)

            return hash_sha256.hexdigest()

        except OSError as e:
            self.logger.warning(f"Could not calculate hash for {file_path}: {e}")
            return None

    def parse(self, response):
        """Main parse method - this spider uses start_requests for initial discovery."""
        # This spider uses start_requests() to begin with campaign discovery
        # The actual parsing logic is in parse_user_memberships() and parse_posts_page()
        pass
