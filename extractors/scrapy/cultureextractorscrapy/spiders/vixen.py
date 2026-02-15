import json

import scrapy

from cultureextractorscrapy.items import PerformerItem
from cultureextractorscrapy.spiders.database import (
    get_or_create_performer,
    get_site_item,
)
from cultureextractorscrapy.utils import get_log_filename

# Next.js build ID - this changes with each deployment
# Update this value when the API returns 404 errors
NEXTJS_BUILD_ID = "Loafm2eg1LvQf1LIyYl7Z"

# Site configurations for the Vixen network sites
SITE_CONFIGS = {
    "blacked": {
        "base_url": "https://www.blacked.com",
        "site_short_name": "blacked",
    },
    "blackedraw": {
        "base_url": "https://www.blackedraw.com",
        "site_short_name": "blackedraw",
    },
    "deeper": {
        "base_url": "https://www.deeper.com",
        "site_short_name": "deeper",
    },
    "milfy": {
        "base_url": "https://www.milfy.com",
        "site_short_name": "milfy",
    },
    "slayed": {
        "base_url": "https://www.slayed.com",
        "site_short_name": "slayed",
    },
    "tushy": {
        "base_url": "https://www.tushy.com",
        "site_short_name": "tushy",
    },
    "tushyraw": {
        "base_url": "https://www.tushyraw.com",
        "site_short_name": "tushyraw",
    },
    "vixen": {
        "base_url": "https://www.vixen.com",
        "site_short_name": "vixen",
    },
}


class VixenSpider(scrapy.Spider):
    name = "vixen"

    def __init__(self, mode="performers", site="blacked", *args, **kwargs):
        """Initialize spider with mode and site parameters.

        Args:
            mode: 'performers' (default) - only mode supported for now
            site: 'blacked' (default) - site to scrape from Vixen network
        """
        super().__init__(*args, **kwargs)
        self.mode = mode

        if mode != "performers":
            raise ValueError(f"Invalid mode: {mode}. Only 'performers' is supported.")

        if site not in SITE_CONFIGS:
            raise ValueError(
                f"Invalid site: {site}. Must be one of: {', '.join(SITE_CONFIGS.keys())}"
            )

        self.site_key = site
        self.site_config = SITE_CONFIGS[site]
        self.base_url = self.site_config["base_url"]
        self.site_short_name = self.site_config["site_short_name"]

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)

        # Set the log file using the spider name
        crawler.settings.set("LOG_FILE", get_log_filename(spider.name))

        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(
                f"Site with short_name '{spider.site_short_name}' not found in the database."
            )
        spider.site = site_item

        return spider

    async def start(self):
        """Start requests by fetching the first page of performers."""
        if self.mode == "performers":
            yield scrapy.Request(
                url=f"{self.base_url}/_next/data/{NEXTJS_BUILD_ID}/performers.json?order=name&page=1",
                callback=self.parse_performers_page,
                meta={"page": 1},
            )

    def parse_performers_page(self, response):
        """Parse a page of performers from the Next.js API."""
        page_num = response.meta["page"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON response for page {page_num}")
            return

        page_props = data.get("pageProps", {})
        # API returns "models" not "performers"
        models = page_props.get("models", [])
        total_count = page_props.get("totalCount", 0)
        previous_count = response.meta.get("count", 0)

        self.logger.info(f"Page {page_num}: Found {len(models)} performers (total: {total_count})")

        for performer_data in models:
            slug = performer_data.get("slug", "")
            name = performer_data.get("name", "")

            if not slug:
                self.logger.warning(f"No slug for performer: {name}")
                continue

            # Get the listing image (headshot) from the listing page
            images = performer_data.get("images", {})
            listing_images = images.get("listing", [])

            # Get the highest resolution listing image (last one is highest quality)
            listing_image_url = None
            if listing_images:
                best_listing = max(
                    listing_images, key=lambda x: x.get("width", 0) * x.get("height", 0)
                )
                listing_image_url = best_listing.get("src", "")

            # Request the performer detail page to get aside and hero images
            yield scrapy.Request(
                url=f"{self.base_url}/_next/data/{NEXTJS_BUILD_ID}/performers/{slug}.json?slug={slug}",
                callback=self.parse_performer_detail,
                meta={
                    "slug": slug,
                    "name": name,
                    "listing_image_url": listing_image_url,
                },
            )

        # Handle pagination using totalCount
        current_count = previous_count + len(models)
        if current_count < total_count:
            next_page = page_num + 1
            self.logger.info(f"Requesting page {next_page} ({current_count}/{total_count})")
            yield scrapy.Request(
                url=f"{self.base_url}/_next/data/{NEXTJS_BUILD_ID}/performers.json?order=name&page={next_page}",
                callback=self.parse_performers_page,
                meta={"page": next_page, "count": current_count},
            )
        else:
            self.logger.info(f"Finished processing all {current_count} performers")

    def parse_performer_detail(self, response):
        """Parse performer detail page to get aside and hero images."""
        slug = response.meta["slug"]
        name = response.meta["name"]
        listing_image_url = response.meta["listing_image_url"]
        performer_url = f"{self.base_url}/performers/{slug}"

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON response for performer: {name} ({slug})")
            return

        page_props = data.get("pageProps", {})

        # Get aside image (profile image from detail page)
        aside = page_props.get("aside", {})
        aside_image_url = aside.get("src", "") if isinstance(aside, dict) else None

        # Get hero image (banner image)
        hero = page_props.get("hero", {})
        hero_image_url = hero.get("src", "") if isinstance(hero, dict) else None

        # Build image URLs list
        image_urls = []

        # Listing image is the main headshot/profile image
        if listing_image_url:
            image_urls.append({"url": listing_image_url, "type": "profile"})

        # Aside image is a secondary profile image
        if aside_image_url:
            image_urls.append({"url": aside_image_url, "type": "aside"})

        # Hero image is a banner image
        if hero_image_url:
            image_urls.append({"url": hero_image_url, "type": "hero"})

        if not image_urls:
            self.logger.warning(f"No images found for performer: {name} ({slug})")
            return

        # Get or create performer in database
        performer = get_or_create_performer(
            self.site.id,
            slug,
            name,
            performer_url,
        )

        self.logger.info(f"Found performer: {name} ({slug}) with {len(image_urls)} images")

        yield PerformerItem(
            performer=performer,
            image_urls=image_urls,
        )
