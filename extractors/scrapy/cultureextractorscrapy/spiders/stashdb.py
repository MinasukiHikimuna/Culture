"""StashDB spider for replicating scene metadata to Delta Lake."""

import os
from pathlib import Path

import scrapy
from dotenv import load_dotenv
from libraries.stashdb_lake import StashDbLake
from libraries.StashDbClient import StashDbClient

load_dotenv()


class StashDBSpider(scrapy.Spider):
    """Spider for scraping StashDB scene metadata."""

    name = "stashdb"
    allowed_domains = ["stashdb.org"]

    custom_settings = {
        "ITEM_PIPELINES": {
            "cultureextractorscrapy.pipelines.StashDbImagePipeline": 200,
        },
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
    }

    def __init__(
        self,
        mode: str = "performer",
        performer_id: str | None = None,
        studio_id: str | None = None,
        download_images: bool = True,
        data_path: str = "data/stashdb",
        *args,
        **kwargs,
    ):
        """Initialize StashDB spider.

        Args:
            mode: Query mode - "performer" or "studio"
            performer_id: StashDB performer UUID (required for performer mode)
            studio_id: StashDB studio UUID (required for studio mode)
            download_images: Whether to download preview images
            data_path: Base path for Delta Lake storage
        """
        super().__init__(*args, **kwargs)

        self.mode = mode
        self.performer_id = performer_id
        self.studio_id = studio_id
        self.download_images = download_images if isinstance(download_images, bool) else download_images == "True"
        self.data_path = data_path

        if mode == "performer" and not performer_id:
            raise ValueError("performer_id is required for performer mode")
        if mode == "studio" and not studio_id:
            raise ValueError("studio_id is required for studio mode")
        if mode not in ("performer", "studio"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'performer' or 'studio'")

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """Initialize spider from crawler with StashDB client."""
        spider = super().from_crawler(crawler, *args, **kwargs)

        endpoint = os.getenv("STASHDB_ENDPOINT", "https://stashdb.org/graphql")
        api_key = os.getenv("STASHDB_API_KEY")
        if not api_key:
            raise ValueError("STASHDB_API_KEY environment variable is required")

        spider.stashdb_client = StashDbClient(endpoint, api_key)
        spider.lake = StashDbLake(spider.data_path)

        images_path = Path(spider.data_path) / "images"
        crawler.settings.set("IMAGES_STORE", str(images_path))

        return spider

    def start_requests(self):
        """Query StashDB and process scenes."""
        if self.mode == "performer":
            self.logger.info(f"Querying scenes for performer: {self.performer_id}")
            scenes = self.stashdb_client.query_scenes_by_performer(self.performer_id)
        else:
            self.logger.info(f"Querying scenes for studio: {self.studio_id}")
            scenes = self.stashdb_client.query_scenes_by_studio(self.studio_id)

        self.logger.info(f"Found {len(scenes)} scenes")

        if not scenes:
            self.logger.warning("No scenes found")
            return

        self._process_scenes(scenes)

        if self.download_images:
            yield from self._generate_image_requests(scenes)

    def _process_scenes(self, scenes: list[dict]) -> None:
        """Process and store scenes to Delta Lake."""
        self.lake.upsert_scenes(scenes)
        self.logger.info(f"Stored {len(scenes)} scenes to Delta Lake")

        performers = self._extract_performers(scenes)
        if performers:
            self.lake.upsert_performers(performers)
            self.logger.info(f"Stored {len(performers)} performers to Delta Lake")

        studios = self._extract_studios(scenes)
        if studios:
            self.lake.upsert_studios(studios)
            self.logger.info(f"Stored {len(studios)} studios to Delta Lake")

        tags = self._extract_tags(scenes)
        if tags:
            self.lake.upsert_tags(tags)
            self.logger.info(f"Stored {len(tags)} tags to Delta Lake")

    def _extract_performers(self, scenes: list[dict]) -> list[dict]:
        """Extract unique performers from scenes."""
        performers = {}
        for scene in scenes:
            for perf_entry in scene.get("performers", []):
                perf = perf_entry.get("performer", {})
                if perf.get("id") and perf["id"] not in performers:
                    performers[perf["id"]] = perf
        return list(performers.values())

    def _extract_studios(self, scenes: list[dict]) -> list[dict]:
        """Extract unique studios from scenes (including parents)."""
        studios = {}
        for scene in scenes:
            studio = scene.get("studio")
            if studio and studio.get("id"):
                if studio["id"] not in studios:
                    studios[studio["id"]] = studio
                parent = studio.get("parent")
                if parent and parent.get("id") and parent["id"] not in studios:
                    studios[parent["id"]] = parent
        return list(studios.values())

    def _extract_tags(self, scenes: list[dict]) -> list[dict]:
        """Extract unique tags from scenes."""
        tags = {}
        for scene in scenes:
            for tag in scene.get("tags", []):
                if tag.get("id") and tag["id"] not in tags:
                    tags[tag["id"]] = tag
        return list(tags.values())

    def _generate_image_requests(self, scenes: list[dict]):
        """Generate requests for downloading images."""
        for scene in scenes:
            scene_images = scene.get("images", [])
            if scene_images:
                image_url = scene_images[0].get("url")
                if image_url:
                    yield StashDbImageItem(
                        image_type="scene",
                        entity_id=scene["id"],
                        image_urls=[image_url],
                    )

            for perf_entry in scene.get("performers", []):
                perf = perf_entry.get("performer", {})
                perf_images = perf.get("images", [])
                if perf_images:
                    image_url = perf_images[0].get("url")
                    if image_url:
                        yield StashDbImageItem(
                            image_type="performer",
                            entity_id=perf["id"],
                            image_urls=[image_url],
                        )

            studio = scene.get("studio")
            if studio:
                studio_images = studio.get("images", [])
                if studio_images:
                    image_url = studio_images[0].get("url")
                    if image_url:
                        yield StashDbImageItem(
                            image_type="studio",
                            entity_id=studio["id"],
                            image_urls=[image_url],
                        )

                parent = studio.get("parent")
                if parent:
                    parent_images = parent.get("images", [])
                    if parent_images:
                        image_url = parent_images[0].get("url")
                        if image_url:
                            yield StashDbImageItem(
                                image_type="studio",
                                entity_id=parent["id"],
                                image_urls=[image_url],
                            )


class StashDbImageItem(scrapy.Item):
    """Item for StashDB image downloads."""

    image_type = scrapy.Field()  # "scene", "performer", or "studio"
    entity_id = scrapy.Field()  # StashDB UUID
    image_urls = scrapy.Field()  # List of image URLs
    images = scrapy.Field()  # Downloaded image info (set by pipeline)
