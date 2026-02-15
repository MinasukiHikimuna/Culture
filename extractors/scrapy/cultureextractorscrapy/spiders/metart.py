import json

import scrapy

from cultureextractorscrapy.items import PerformerItem
from cultureextractorscrapy.spiders.database import (
    get_or_create_performer,
    get_site_item,
)
from cultureextractorscrapy.utils import get_log_filename

# Site configurations for the MetArt network sites
SITE_CONFIGS = {
    "sexart": {
        "base_url": "https://www.sexart.com",
        "site_short_name": "sexart",
    },
    "metart": {
        "base_url": "https://www.metart.com",
        "site_short_name": "metart",
    },
    "vivthomas": {
        "base_url": "https://www.vivthomas.com",
        "site_short_name": "vivthomas",
    },
    "alsscan": {
        "base_url": "https://www.alsscan.com",
        "site_short_name": "alsscan",
    },
    "thelifeerotic": {
        "base_url": "https://www.thelifeerotic.com",
        "site_short_name": "thelifeerotic",
    },
    "eternaldesire": {
        "base_url": "https://www.eternaldesire.com",
        "site_short_name": "eternaldesire",
    },
    "straplez": {
        "base_url": "https://www.straplez.com",
        "site_short_name": "straplez",
    },
    "metartx": {
        "base_url": "https://www.metartx.com",
        "site_short_name": "metartx",
    },
    "lovehairy": {
        "base_url": "https://www.lovehairy.com",
        "site_short_name": "lovehairy",
    },
    "erroticaarchives": {
        "base_url": "https://www.errotica-archives.com",
        "site_short_name": "erroticaarchives",
    },
    "goddessnudes": {
        "base_url": "https://www.goddessnudes.com",
        "site_short_name": "goddessnudes",
    },
    "rylskyart": {
        "base_url": "https://www.rylskyart.com",
        "site_short_name": "rylskyart",
    },
    "domai": {
        "base_url": "https://www.domai.com",
        "site_short_name": "domai",
    },
}

# CDN base URL for MetArt network
CDN_BASE_URL = "https://cdn.metartnetwork.com"


class MetArtSpider(scrapy.Spider):
    name = "metart"

    def __init__(self, mode="performers", site="sexart", *args, **kwargs):
        """Initialize spider with mode and site parameters.

        Args:
            mode: 'performers' (default) - only mode supported for now
            site: 'sexart' (default) - site to scrape from MetArt network
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
        """Start requests by iterating through A-Z for performer listing."""
        if self.mode == "performers":
            # Iterate through all letters A-Z
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                yield scrapy.Request(
                    url=f"{self.base_url}/api/models?page=1&firstNameLetter={letter}&order=NAME&direction=ASC&first=100",
                    callback=self.parse_models_page,
                    meta={"letter": letter, "page": 1, "count": 0},
                )

    def parse_models_page(self, response):
        """Parse a page of models/performers from the API."""
        letter = response.meta["letter"]
        page_num = response.meta["page"]
        previous_count = response.meta["count"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON response for letter {letter}, page {page_num}")
            return

        models = data.get("models", [])
        total = data.get("total", 0)

        self.logger.info(
            f"Letter {letter}, Page {page_num}: Found {len(models)} performers (total: {total})"
        )

        for model in models:
            # Extract performer data
            short_name = model["path"].split("/")[-1]
            name = model["name"]
            site_uuid = model["siteUUID"]
            performer_url = f"{self.base_url}{model['path']}"

            # Build image URLs
            headshot_path = model.get("headshotImagePath", "")
            headshot_sfw_path = model.get("headshotImagePathSfw", "")

            if not headshot_path:
                self.logger.warning(f"No headshot image for performer: {name} ({short_name})")
                continue

            nsfw_url = f"{CDN_BASE_URL}/{site_uuid}{headshot_path}"
            sfw_url = f"{CDN_BASE_URL}/{site_uuid}{headshot_sfw_path}" if headshot_sfw_path else None

            # Get or create performer in database
            performer = get_or_create_performer(
                self.site.id,
                short_name,
                name,
                performer_url,
            )

            # Build image URLs list
            image_urls = [
                {"url": nsfw_url, "type": "profile"},  # Main image, named {performer_uuid}.jpg
            ]
            if sfw_url:
                image_urls.append({"url": sfw_url, "type": "profile-sfw"})

            self.logger.info(f"Found performer: {name} ({short_name}) with {len(image_urls)} images")

            yield PerformerItem(
                performer=performer,
                image_urls=image_urls,
            )

        # Handle pagination
        current_count = previous_count + len(models)
        if current_count < total:
            next_page = page_num + 1
            self.logger.info(f"Letter {letter}: Requesting page {next_page} ({current_count}/{total})")
            yield scrapy.Request(
                url=f"{self.base_url}/api/models?page={next_page}&firstNameLetter={letter}&order=NAME&direction=ASC&first=100",
                callback=self.parse_models_page,
                meta={"letter": letter, "page": next_page, "count": current_count},
            )
        else:
            self.logger.info(f"Letter {letter}: Finished processing all {current_count} performers")
