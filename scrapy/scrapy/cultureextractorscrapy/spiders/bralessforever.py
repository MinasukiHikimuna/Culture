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
        """Initial parse method - start with the main page."""
        # Save the main page DOM to a file for analysis
        self.save_dom_to_file(response, "braless_forever_main.html")
        
        # Also try the browse page
        yield scrapy.Request(
            url=f"{base_url}/browse",
            callback=self.parse_browse_page,
            cookies=cookies,
            meta={"page": 1},
            dont_filter=True,
        )
        
        # Try the specific videos page with all channels visible
        yield scrapy.Request(
            url=f"{base_url}/browse/videos?channel_visibility=%22ALL%22",
            callback=self.parse_videos_page,
            cookies=cookies,
            meta={"page": 1},
            dont_filter=True,
        )

    def parse_browse_page(self, response):
        """Parse the browse page and save DOM."""
        # Save the browse page DOM to a file for analysis
        self.save_dom_to_file(response, "braless_forever_browse.html")
        
        # Log some basic info
        self.logger.info(f"Browse page URL: {response.url}")
        self.logger.info(f"Response status: {response.status}")
        
        return []
    
    def parse_videos_page(self, response):
        """Parse the videos page and save DOM."""
        # Save the videos page DOM to a file for analysis
        self.save_dom_to_file(response, "braless_forever_videos.html")
        
        # Log some basic info
        self.logger.info(f"Videos page URL: {response.url}")
        self.logger.info(f"Response status: {response.status}")
        
        return []
    
    def save_dom_to_file(self, response, filename):
        """Save the response HTML to a file for analysis."""
        import os
        
        # Create output directory if it doesn't exist
        output_dir = "/Users/thardas/Private/Code/CultureExtractor/scrapy/dom_analysis"
        os.makedirs(output_dir, exist_ok=True)
        
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        self.logger.info(f"Saved DOM to: {file_path}")
        print(f"DOM saved to: {file_path}")