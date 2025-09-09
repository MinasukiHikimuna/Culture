"""
Braless Forever Scraper

Scraping Strategy:
1. Start from /browse/categories to get all available categories
2. For each category, scrape the video listings to get releases per category
3. Skip "Premiere" videos (upcoming content) and only scrape available videos
4. Extract video metadata: title, cast, duration, cover image, video ID, release date
5. Categories provide the tagging/classification that isn't available on main video listings

Site Structure:
- Categories page: /browse/categories
- Category videos: /browse/videos?category=[category-name]
- Individual videos: /videos/[uuid]
- Video listings show: title, cast, duration, cover, view/like counts, release dates
"""

import os
import json
import newnewid
from datetime import datetime, timezone
from dotenv import load_dotenv
import scrapy
from cultureextractorscrapy.spiders.database import (
    get_site_item,
    get_or_create_performer,
    get_or_create_tag,
    get_existing_releases_with_status,
)
from cultureextractorscrapy.items import (
    AvailableImageFile,
    AvailableVideoFile,
    AvailableFileEncoder,
    ReleaseItem,
    DirectDownloadItem,
    FfmpegDownloadItem,
)
from cultureextractorscrapy.utils import (
    parse_resolution_height,
    parse_resolution_width,
    get_log_filename,
)
from itemadapter import ItemAdapter

load_dotenv()

# Load and format cookies properly
raw_cookies = json.loads(os.getenv("BRALESSFOREVER_COOKIES", "[]"))
cookies = {}
if isinstance(raw_cookies, list):
    for cookie in raw_cookies:
        if isinstance(cookie, dict) and "name" in cookie and "value" in cookie:
            cookies[cookie["name"]] = cookie["value"]

base_url = "https://app.bralessforever.com"


class BralessForeverSpider(scrapy.Spider):
    name = "bralessforever"
    allowed_domains = ["app.bralessforever.com", "private-blvideo.b-cdn.net", "cdn.realms.tv"]
    start_urls = [base_url]
    site_short_name = "bralessforever"
    
    # Add desired performer short names for filtering
    # Set to empty list to scrape all performers, or add specific performer short names
    desired_performers = []

    def __init__(self, *args, **kwargs):
        super(BralessForeverSpider, self).__init__(*args, **kwargs)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(BralessForeverSpider, cls).from_crawler(crawler, *args, **kwargs)

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
        return spider

    def parse(self, response):
        """Initial parse method - start with categories page."""
        self.logger.info("🚀 Starting Braless Forever scraper")
        
        # Go directly to categories page (our primary starting point)
        yield scrapy.Request(
            url=f"{base_url}/browse/categories",
            callback=self.parse_categories_page,
            cookies=cookies,
            dont_filter=True,
        )

    def parse_categories_page(self, response):
        """Parse the categories page and extract all available categories."""
        # Save the categories page DOM to a file for analysis
        self.save_dom_to_file(response, "categories.html")
        
        # Log some basic info
        self.logger.info(f"📋 Processing categories page: {response.url}")
        self.logger.info(f"📊 Response status: {response.status}")
        
        # Extract category links using CSS selectors
        category_links = response.css('a[href*="/categories/"]::attr(href)').getall()
        
        self.logger.info(f"🔍 Found {len(category_links)} category links")
        
        categories_found = []
        for link in category_links:
            # Extract category slug from URL
            if '/categories/' in link:
                category_slug = link.split('/categories/')[-1]
                # Get the category display name from the associated text
                category_element = response.css(f'a[href="{link}"]')
                if category_element:
                    category_name = category_element.css('h3::text').get()
                    if category_name:
                        categories_found.append({
                            'slug': category_slug,
                            'name': category_name.strip(),
                            'url': link
                        })
                        self.logger.info(f"📂 Found category: '{category_name}' -> {category_slug}")
        
        self.logger.info(f"✅ Successfully parsed {len(categories_found)} categories")
        
        # For now, let's scrape just one category for testing
        if categories_found:
            test_category = categories_found[0]  # Take first category for testing
            self.logger.info(f"🧪 Testing with category: '{test_category['name']}'")
            
            full_url = response.urljoin(test_category['url'])
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_category_videos,
                cookies=cookies,
                meta={'category': test_category},
                dont_filter=True,
            )
        else:
            self.logger.warning("⚠️ No categories found on the page")
        
        return []
    
    def parse_category_videos(self, response):
        """Parse videos from a specific category page."""
        category = response.meta.get('category', {})
        category_name = category.get('name', 'Unknown')
        category_slug = category.get('slug', 'unknown')
        
        # Save the category page DOM for analysis
        self.save_dom_to_file(response, f"category_{category_slug}.html")
        
        self.logger.info(f"🎬 Processing videos for category: '{category_name}'")
        self.logger.info(f"📊 Response status: {response.status} for {response.url}")
        
        # Extract video cards - same structure as main videos page
        video_cards = response.css('div.collection-card')
        self.logger.info(f"🔍 Found {len(video_cards)} video cards in '{category_name}'")
        
        videos_processed = 0
        videos_skipped = 0
        
        for card in video_cards:
            # Extract basic video information
            title_element = card.css('h3::text')
            video_link = card.css('a[href*="/videos/"]::attr(href)')
            duration_element = card.css('span:contains(":")::text, span:contains("Premiere")::text')
            
            if not title_element or not video_link:
                self.logger.debug("⏭️ Skipping card with missing title or link")
                continue
                
            title = title_element.get().strip()
            video_url = video_link.get()
            video_id = video_url.split('/')[-1] if video_url else None
            duration = duration_element.get() if duration_element else None
            
            # Skip "Premiere" videos (upcoming content)
            if duration and "Premiere" in duration:
                self.logger.info(f"⏩ Skipping upcoming video: '{title}' (Premiere)")
                videos_skipped += 1
                continue
            
            # Extract cast information with URLs  
            cast_links = card.css('a[href*="/users/"]')
            cast_members = []
            for cast_link in cast_links:
                cast_name = cast_link.css('::text').get()  # Text is directly inside the <a> tag
                cast_url = cast_link.css('::attr(href)').get()
                if cast_name and cast_url:
                    cast_members.append({
                        'name': cast_name.strip(),
                        'url': cast_url
                    })
            
            # Extract cover image
            cover_img = card.css('img::attr(src)').get()
            
            # Extract release date from time element
            release_date_element = card.css('time::attr(datetime)')
            release_date = None
            if release_date_element:
                release_date_str = release_date_element.get()
                if release_date_str:
                    try:
                        # Parse ISO datetime and convert to date
                        from datetime import datetime
                        release_dt = datetime.fromisoformat(release_date_str.replace('Z', '+00:00'))
                        release_date = release_dt.date().isoformat()
                    except (ValueError, AttributeError) as e:
                        self.logger.warning(f"Could not parse release date: {release_date_str} - {e}")
            
            # Log the video details in a single comprehensive line
            cast_names = [member['name'] for member in cast_members] if cast_members else []
            cast_info = f" | Cast: {', '.join(cast_names)}" if cast_names else ""
            self.logger.info(f"🎥 {category_name} → '{title}' ({duration or 'No duration'}){cast_info}")
            
            videos_processed += 1
            
            # For testing, only scrape the first video
            if videos_processed == 1:
                yield scrapy.Request(
                    url=response.urljoin(video_url),
                    callback=self.parse_video,
                    cookies=cookies,
                    meta={
                        'category': category,
                        'video_data': {
                            'title': title,
                            'video_id': video_id,
                            'duration': duration,
                            'cast_members': cast_members,
                            'cover_img': cover_img,
                            'release_date': release_date
                        }
                    },
                    dont_filter=True,
                )
                # Stop processing after first video for testing
                break
        
        self.logger.info(f"✅ Category '{category_name}' processing complete:")
        self.logger.info(f"   📈 Videos processed: {videos_processed}")
        self.logger.info(f"   ⏩ Videos skipped (Premiere): {videos_skipped}")
        self.logger.info(f"   📊 Total videos found: {len(video_cards)}")
    
    def parse_video(self, response):
        """Parse individual video page to extract scene details."""
        category = response.meta.get('category', {})
        video_data = response.meta.get('video_data', {})
        category_name = category.get('name', 'Unknown')
        category_slug = category.get('slug', 'unknown')
        
        # Save the video page DOM for analysis
        video_id = video_data.get('video_id', 'unknown')
        self.save_dom_to_file(response, f"video_{video_id}.html")
        
        self.logger.info(f"🎬 Processing individual video: '{video_data.get('title', 'Unknown')}'")
        self.logger.info(f"📊 Response status: {response.status} for {response.url}")
        
        # Extract video download links/streams
        video_elements = response.css('video source, video::attr(src), a[href*=".mp4"], a[href*=".m4v"]')
        self.logger.info(f"🎞️ Found {len(video_elements)} potential video elements")
        
        # Get the HLS stream URL
        hls_url = None
        for element in video_elements:
            src = element.css('::attr(src)').get() or element.css('::attr(href)').get()
            if src and '.m3u8' in src:
                hls_url = src
                self.logger.info(f"   📹 HLS stream: {src}")
                break
        
        # Extract high-resolution images
        image_elements = response.css('img')
        scene_images = []
        for img in image_elements:
            src = img.css('::attr(src)').get()
            if src and ('thumb' not in src.lower() and 'avatar' not in src.lower() and 'logo' not in src.lower()):
                scene_images.append(src)
        
        # Use the cover image from listing if available, otherwise first scene image
        cover_image = video_data.get('cover_img') or (scene_images[0] if scene_images else None)
        
        # Extract release date from video page (more reliable than category listing)
        video_release_date = None
        time_element = response.css('time::attr(datetime)').get()
        if time_element:
            try:
                # Parse ISO datetime and convert to date
                release_dt = datetime.fromisoformat(time_element.replace('Z', '+00:00'))
                video_release_date = release_dt.date().isoformat()
                self.logger.info(f"📅 Extracted release date: {video_release_date} from video page")
            except (ValueError, AttributeError) as e:
                self.logger.warning(f"Could not parse video page release date: {time_element} - {e}")
        
        # Use video page date if available, otherwise fall back to category listing date
        final_release_date = video_release_date or video_data.get('release_date') or '1900-01-01'
        
        # Extract description from JSON-LD structured data
        description = ''
        json_ld_data = None
        json_ld_script = response.css('script[type="application/ld+json"]::text').get()
        if json_ld_script:
            try:
                json_ld_data = json.loads(json_ld_script)
                if isinstance(json_ld_data, dict) and json_ld_data.get('@type') == 'VideoObject':
                    description = json_ld_data.get('description', '')
                    if description:
                        self.logger.info(f"📝 Extracted description: {description[:100]}{'...' if len(description) > 100 else ''}")
            except (json.JSONDecodeError, AttributeError) as e:
                self.logger.warning(f"Could not parse JSON-LD data: {e}")
                json_ld_data = None
        
        # Convert duration from MM:SS to seconds
        duration_seconds = 0
        duration_str = video_data.get('duration', '')
        if duration_str and ':' in duration_str:
            try:
                parts = duration_str.split(':')
                if len(parts) == 2:
                    minutes, seconds = map(int, parts)
                    duration_seconds = minutes * 60 + seconds
                elif len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    duration_seconds = hours * 3600 + minutes * 60 + seconds
            except ValueError:
                self.logger.warning(f"Could not parse duration: {duration_str}")
        
        # Create performers from cast members
        performers = []
        cast_members = video_data.get('cast_members', [])
        for cast_member in cast_members:
            if cast_member and isinstance(cast_member, dict):
                cast_name = cast_member.get('name')
                cast_url = cast_member.get('url')
                if cast_name and cast_url:
                    # Extract UUID from URL (e.g., /users/35bd8c49-d9ea-4489-8e37-4c363f3df293/preview)
                    url_parts = cast_url.split('/')
                    performer_uuid = None
                    for part in url_parts:
                        if len(part) == 36 and part.count('-') == 4:  # UUID format check
                            performer_uuid = part
                            break
                    
                    if performer_uuid:
                        performer = get_or_create_performer(
                            self.site.id,
                            performer_uuid,  # Use UUID as short_name
                            cast_name,
                            response.urljoin(cast_url),  # Use actual URL
                        )
                        performers.append(performer)
                    else:
                        self.logger.warning(f"Could not extract UUID from performer URL: {cast_url}")
        
        # Create tag from category
        tags = []
        if category_name and category_name != 'Unknown':
            tag = get_or_create_tag(
                self.site.id,
                category_slug,
                category_name,
                f"{base_url}/categories/{category_slug}",
            )
            tags.append(tag)
        
        # Create available files list
        available_files = []
        
        # Add HLS video stream
        if hls_url:
            video_file = AvailableVideoFile(
                file_type="video",
                content_type="scene",
                variant="hls_stream",
                url=hls_url,
            )
            available_files.append(video_file)
        
        # Add cover image
        if cover_image:
            image_file = AvailableImageFile(
                file_type="image",
                content_type="cover",
                variant="cover",
                url=cover_image,
                resolution_width=640,  # Standard thumbnail width from realms.tv
                resolution_height=360,  # Standard thumbnail height from realms.tv
            )
            available_files.append(image_file)
        
        # Check if this release already exists
        existing_release = self.existing_releases.get(video_id)
        release_id = existing_release.get('uuid') if existing_release else newnewid.uuid7()
        
        if existing_release:
            self.logger.info(f"Release ID={release_id} short_name={video_id} already exists. Updating existing release.")
        else:
            self.logger.info(f"Creating new release ID={release_id} short_name={video_id}.")
        
        # Create the release item
        release_item = ReleaseItem(
            id=release_id,
            release_date=final_release_date,
            short_name=video_id,
            name=video_data.get('title', ''),
            url=response.url,
            description=description,
            duration=duration_seconds,
            created=datetime.now(tz=timezone.utc).astimezone(),
            last_updated=datetime.now(tz=timezone.utc).astimezone(),
            performers=performers,
            tags=tags,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps({
                'video_id': video_id,
                'title': video_data.get('title'),
                'duration': duration_str,
                'cast_members': cast_members,  # Now includes name and url
                'category': {
                    'name': category_name,
                    'slug': category_slug
                },
                'hls_url': hls_url,
                'cover_image': cover_image,
                'scene_images': scene_images,
                'release_date': final_release_date,
                'original_datetime': time_element,  # Store original datetime for reference
                'description': description,
                'json_ld_data': json_ld_data if json_ld_script else None,  # Full structured data
            }),
            site_uuid=self.site.id,
            site=self.site,
        )
        
        self.logger.info(f"✅ Created ReleaseItem for '{video_data.get('title')}'")
        self.logger.info(f"   🎞️ Video files: {len([f for f in available_files if f.file_type == 'video'])}")
        self.logger.info(f"   🖼️ Image files: {len([f for f in available_files if f.file_type == 'image'])}")
        self.logger.info(f"   👥 Performers: {len(performers)}")
        self.logger.info(f"   🏷️ Tags: {len(tags)}")
        
        yield release_item
        
        # Check for duplicate downloads before yielding download items
        files_to_download = available_files
        if existing_release and not self.force_update:
            # Compare available files with downloaded files
            existing_available_files = existing_release['available_files']
            downloaded_files = existing_release['downloaded_files']
            
            needed_files = set(
                (f.file_type, f.content_type, f.variant) 
                for f in available_files
            )
            
            if not needed_files.issubset(downloaded_files):
                # We have missing files - filter to only missing ones
                missing_files = [f for f in available_files if 
                    (f.file_type, f.content_type, f.variant) not in downloaded_files]
                files_to_download = missing_files
                self.logger.info(f"Release {video_id} exists but missing {len(missing_files)} files. Downloading them.")
            else:
                self.logger.info(f"Release {video_id} already exists with all files downloaded. Skipping downloads.")
                files_to_download = []  # Skip all downloads
        
        # Now yield appropriate download items based on file type
        for file_info in files_to_download:
            # Check if this is an m3u8/HLS URL that needs ffmpeg processing
            if file_info.url.endswith('.m3u8') or '.m3u8' in file_info.url:
                self.logger.info(f"🎬 Yielding FfmpegDownloadItem for m3u8 URL: {file_info.url}")
                yield FfmpegDownloadItem(
                    release_id=str(release_id),
                    file_info=ItemAdapter(file_info).asdict(),
                    url=file_info.url,
                )
            else:
                self.logger.info(f"📁 Yielding DirectDownloadItem for regular URL: {file_info.url}")
                yield DirectDownloadItem(
                    release_id=str(release_id),
                    file_info=ItemAdapter(file_info).asdict(),
                    url=file_info.url,
                )
    
    def save_dom_to_file(self, response, filename):
        """Save the response HTML to a file for analysis."""
        import os
        
        # Create bralessforever-specific directory under dom_analysis
        output_dir = "/Users/thardas/Private/Code/CultureExtractor/scrapy/dom_analysis/bralessforever"
        os.makedirs(output_dir, exist_ok=True)
        
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        self.logger.info(f"Saved DOM to: {file_path}")
        print(f"DOM saved to: {file_path}")