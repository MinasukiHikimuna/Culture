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
            
            # Log the video details
            self.logger.info(f"🎥 Found video: '{title}' ({duration or 'No duration'}) in '{category_name}'")
            if cast_members:
                self.logger.info(f"👥 Cast: {', '.join(cast_members)}")
            
            videos_processed += 1
            
            # TODO: Create video item and yield it
            # For now, just log the details
        
        self.logger.info(f"✅ Category '{category_name}' processing complete:")
        self.logger.info(f"   📈 Videos processed: {videos_processed}")
        self.logger.info(f"   ⏩ Videos skipped (Premiere): {videos_skipped}")
        self.logger.info(f"   📊 Total videos found: {len(video_cards)}")
        
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