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
    allowed_domains = ["app.bralessforever.com"]
    start_urls = [base_url]
    site_short_name = "bralessforever"

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
            
            # Extract cast information
            cast_links = card.css('a[href*="/users/"]')
            cast_members = []
            for cast_link in cast_links:
                cast_name = cast_link.css('::text').get()
                if cast_name:
                    cast_members.append(cast_name.strip())
            
            # Extract cover image
            cover_img = card.css('img::attr(src)').get()
            
            # Log the video details in a single comprehensive line
            cast_info = f" | Cast: {', '.join(cast_members)}" if cast_members else ""
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
                            'cover_img': cover_img
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
        
        # Save the video page DOM for analysis
        video_id = video_data.get('video_id', 'unknown')
        self.save_dom_to_file(response, f"video_{video_id}.html")
        
        self.logger.info(f"🎬 Processing individual video: '{video_data.get('title', 'Unknown')}'")
        self.logger.info(f"📊 Response status: {response.status} for {response.url}")
        
        # Extract video download links/streams
        video_elements = response.css('video source, video::attr(src), a[href*=".mp4"], a[href*=".m4v"]')
        self.logger.info(f"🎞️ Found {len(video_elements)} potential video elements")
        
        # Log video sources
        for i, element in enumerate(video_elements):
            src = element.css('::attr(src)').get() or element.css('::attr(href)').get()
            if src:
                self.logger.info(f"   📹 Video source {i+1}: {src}")
        
        # Extract high-resolution images
        image_elements = response.css('img')
        scene_images = []
        for img in image_elements:
            src = img.css('::attr(src)').get()
            if src and ('thumb' not in src.lower() and 'avatar' not in src.lower()):
                scene_images.append(src)
        
        self.logger.info(f"🖼️ Found {len(scene_images)} scene images:")
        for i, img_src in enumerate(scene_images[:5]):  # Log first 5 images
            self.logger.info(f"   🖼️ Scene image {i+1}: {img_src}")
        
        # Extract any additional metadata available on the video page
        description_element = response.css('div.description, p.description, div.video-description')
        description = description_element.css('::text').get() if description_element else ''
        
        # Extract view count, likes, etc.
        stats_elements = response.css('span:contains("views"), span:contains("likes"), div.stats')
        stats = []
        for stat in stats_elements:
            stat_text = stat.css('::text').get()
            if stat_text:
                stats.append(stat_text.strip())
        
        self.logger.info(f"📊 Video stats: {', '.join(stats) if stats else 'None found'}")
        self.logger.info(f"📝 Description: {description[:100] if description else 'None found'}")
        
        # Log summary
        self.logger.info(f"✅ Video parsing complete for '{video_data.get('title')}'")
        self.logger.info(f"   🎞️ Video sources found: {len(video_elements)}")
        self.logger.info(f"   🖼️ Scene images found: {len(scene_images)}")
        
        return []
    
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