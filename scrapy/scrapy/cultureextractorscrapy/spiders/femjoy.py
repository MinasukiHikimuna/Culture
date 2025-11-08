import json
import os
from datetime import UTC, datetime

import newnewid
from dotenv import load_dotenv

import scrapy
from cultureextractorscrapy.items import (
    AvailableFileEncoder,
    AvailableGalleryZipFile,
    AvailableImageFile,
    AvailableVideoFile,
    ReleaseItem,
)
from cultureextractorscrapy.spiders.database import (
    get_existing_release_short_names,
    get_site_item,
)
from cultureextractorscrapy.utils import parse_resolution_height, parse_resolution_width

load_dotenv()

cookies = json.loads(os.getenv("FEMJOY_COOKIES"))
base_url = "https://femjoy.com"

class FemjoySpider(scrapy.Spider):
    name = "femjoy"
    allowed_domains = ["https://femjoy.com"]
    start_urls = [base_url]
    site_short_name = "femjoy"

    # Add this new class attribute to store desired performer short names
    desired_performers = ["heidi-romanova", "carisha", "belinda", "ashley", "ryana", "linda-a", "sofie", "susi-r", "darina-a", "cara-mell-1", "susann", "cara-mell", "stella-cardo", "candy-d", "vanea-h", "miela", "davina-e", "niemira", "corinna", "josephine", "jane-f", "ariel", "vika-p", "caprice", "marga-e", "pandora-red", "aelita", "lana-lane", "vika-a", "karla-s", "melina-d", "stacy-cruz", "mila-k", "missa", "sugar-ann", "erin-k", "paula-s", "anneth", "jasmine-a", "annabell", "alice-kelly", "rinna", "myla", "simona", "penelope-g", "april-e", "olivia-linz", "lillie", "ella-c", "danica", "kinga", "anna-delos", "casey", "mara-blake", "aveira", "melisa", "alisha", "alicia-fox", "hayden-w", "vanessa-a", "jenni", "mariposa", "ruth", "linda-a", "susi-r", "marria-leeah", "ramona", "lizzie", "laura", "paula-s", "anna-t", "bella-o", "lee-d", "magdalene", "abigail", "dori-k", "karol", "lucy-l", "katy", "foxy-t", "paloma", "aida", "kissin", "katie-g", "amaris", "acacia", "anastasia", "charlotta", "kamilla-j", "zelda", "dido", "beata-p", "yanina", "amelie-belain", "holly-m", "lena-s", "chesney", "lena-r", "varya-k", "vicky-z", "pamela", "anika"]

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(FemjoySpider, cls).from_crawler(crawler, *args, **kwargs)
        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(f"Site with short_name '{spider.site_short_name}' not found in the database.")
        spider.site = site_item
        spider.existing_releases = get_existing_release_short_names(site_item.id)
        return spider

    def parse(self, response):
        yield scrapy.Request(
            url=f"{base_url}/photos",
            callback=self.parse_photos,
            cookies=cookies)

        yield scrapy.Request(
            url=f"{base_url}/videos",
            callback=self.parse_videos,
            cookies=cookies)

    def parse_photos(self, response):
        # Extract pagination data
        pagination = response.css('div._pagination div.paginationArea')

        # Get the last page number
        last_page = int(pagination.css('div.right a.pageBtn[title="last"]::attr(data-page)').get())

        for page in range(1, last_page + 1):
            yield scrapy.Request(
                url=f"{base_url}/photos?page={page}",
                callback=self.parse_photos_page,
                cookies=cookies,
                meta={"page": page}
            )

    def parse_photos_page(self, response):
        posts = response.css('div.post_item')
        for post in posts:
            external_id = post.css('::attr(data-post-id)').get()
            title = post.css('h1 a::text').get()
            cover_url = post.css('div.post_image a img.item_cover::attr(src)').get()

            raw_release_date = post.css('h3 span.posted_on::text').get()
            parsed_release_date = datetime.strptime(raw_release_date, '%b %d, %Y').date() if raw_release_date else None
            release_date = parsed_release_date.isoformat() if parsed_release_date else None

            photo_count = int(post.css('h3 span.counter_photos::text').re_first(r'\d+') or 0)

            # Extract multiple models
            models = []
            model_elements = post.css('h2 a[href^="/models/"]')
            for model_element in model_elements:
                model_name = model_element.css('::text').get()
                model_url = model_element.css('::attr(href)').get()
                model_short_name = model_url.split('/')[-1] if model_url else None
                models.append({
                    "name": model_name,
                    "short_name": model_short_name,
                    "url": model_url
                })

            director = {}
            director_element = post.css('h2 a[href^="/director/"]')
            if director_element:
                director_url = director_element.css('::attr(href)').get()
                director = {
                    "name": director_element.css('::text').get(),
                    "short_name": director_url.split('/')[-1] if director_url else None,
                    "url": director_url
                }

            post_url = post.css('h1 a::attr(href)').get()

            post_data = {
                "external_id": external_id,
                "title": title,
                "cover_url": cover_url,
                "release_date": release_date,
                "photo_count": photo_count,
                "models": models,
                "director": director
            }

            # Check if any of the desired performers are in this release
            if self.desired_performers and not any(model['short_name'] in self.desired_performers for model in models):
                continue  # Skip this release if it doesn't contain any desired performers

            yield scrapy.Request(
                url=f"{base_url}{post_url}",
                callback=self.parse_photoset,
                cookies=cookies,
                # TODO: priority=10,
                meta={
                    "post_data": post_data
                }
            )

    def parse_photoset(self, response):
        post_data = response.meta["post_data"]

        external_id = post_data["external_id"]

        # Check if this release already exists
        existing_release_id = self.existing_releases.get(external_id)
        release_id = existing_release_id if existing_release_id else newnewid.uuid7()
        if existing_release_id:
            self.logger.info(f"Release ID={existing_release_id} short_name={external_id} already exists. Updating existing release.")
        else:
            self.logger.info(f"Creating new release ID={release_id} short_name={external_id}.")

        # No tags on this site.
        tags = []

        available_files = []

        # Extract gallery download links
        gallery_links = response.css('div.column a.post_download')
        for link in gallery_links:
            url = link.attrib['href']
            variant = link.xpath('text()').get()
            width = int(variant.split()[-1].replace('px', '')) if 'px' in variant else None

            available_files.append(AvailableGalleryZipFile(
                file_type='zip',
                content_type='gallery',
                variant=variant,
                url=url,
                resolution_width=width,
            ))

        cover_url = post_data.get('cover_url')
        if cover_url:
            available_files.append(AvailableImageFile(
                file_type='image',
                content_type='cover',
                variant='',
                url=cover_url,
            ))

        release_item = ReleaseItem(
            id=release_id,
            release_date=post_data.get('release_date'),
            short_name=external_id,
            name=post_data.get('title'),
            url=response.url,
            description="",
            duration=0,
            created=datetime.now(tz=UTC).astimezone(),
            last_updated=datetime.now(tz=UTC).astimezone(),
            performers=post_data.get('models'),
            tags=tags,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(post_data),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item


    def parse_videos(self, response):
        # Extract pagination data
        pagination = response.css('div._pagination div.paginationArea')

        # Get the last page number
        last_page = int(pagination.css('div.right a.pageBtn[title="last"]::attr(data-page)').get())

        for page in range(1, last_page + 1):
            yield scrapy.Request(
                url=f"{base_url}/videos?page={page}",
                callback=self.parse_videos_page,
                cookies=cookies,
                meta={"page": page}
            )

    def parse_videos_page(self, response):
        posts = response.css('div.post_item')
        for post in posts:
            external_id = post.css('::attr(data-post-id)').get()
            title = post.css('h1 a::text').get()
            cover_url = post.css('div.post_video a img.item_cover::attr(src)').get()

            raw_release_date = post.css('h3 span.posted_on::text').get()
            parsed_release_date = datetime.strptime(raw_release_date, '%b %d, %Y').date() if raw_release_date else None
            release_date = parsed_release_date.isoformat() if parsed_release_date else None

            raw_duration_text = post.css('h3 span.counter_photos::text').get()
            if raw_duration_text:
                duration_parts = raw_duration_text.strip().split(':')
                if len(duration_parts) == 2:
                    minutes, seconds = map(int, duration_parts)
                    duration = minutes * 60 + seconds
                else:
                    duration = 0
            else:
                duration = 0

            # Extract multiple models
            models = []
            model_elements = post.css('h2 a[href^="/models/"]')
            for model_element in model_elements:
                model_name = model_element.css('::text').get()
                model_url = model_element.css('::attr(href)').get()
                model_short_name = model_url.split('/')[-1] if model_url else None
                models.append({
                    "name": model_name,
                    "short_name": model_short_name,
                    "url": model_url
                })

            # Check if any of the desired performers are in this release
            if self.desired_performers and not any(model['short_name'] in self.desired_performers for model in models):
                continue  # Skip this release if it doesn't contain any desired performers

            director = {}
            director_element = post.css('h2 a[href^="/director/"]')
            if director_element:
                director_url = director_element.css('::attr(href)').get()
                director = {
                    "name": director_element.css('::text').get(),
                    "short_name": director_url.split('/')[-1] if director_url else None,
                    "url": director_url
                }

            post_url = post.css('h1 a::attr(href)').get()

            post_data = {
                "external_id": external_id,
                "title": title,
                "cover_url": cover_url,
                "release_date": release_date,
                "duration": duration,
                "models": models,
                "director": director
            }

            yield scrapy.Request(
                url=f"{base_url}{post_url}",
                callback=self.parse_video,
                cookies=cookies,
                # TODO: priority=10,
                meta={
                    "post_data": post_data
                }
            )

    def parse_video(self, response):
        post_data = response.meta["post_data"]

        external_id = post_data["external_id"]

        # Check if this release already exists
        existing_release_id = self.existing_releases.get(external_id)
        release_id = existing_release_id if existing_release_id else newnewid.uuid7()
        if existing_release_id:
            self.logger.info(f"Release ID={existing_release_id} short_name={external_id} already exists. Updating existing release.")
        else:
            self.logger.info(f"Creating new release ID={release_id} short_name={external_id}.")

        # No tags on this site.
        tags = []

        available_files = []

        # Extract video download links
        video_links = response.css('div.column a.post_download')
        video_files = {}
        for link in video_links:
            url = link.attrib['href']
            variant = link.xpath('text()').get()
            width = parse_resolution_width(variant)
            height = parse_resolution_height(variant)

            # Create a key based on resolution
            resolution_key = f"{width}x{height}"

            # Check if this resolution already exists and if the new file is MOV
            if resolution_key in video_files:
                existing_file = video_files[resolution_key]
                if 'mp4' in variant.lower():
                    # Always prefer MP4
                    video_files[resolution_key] = {
                        'url': url,
                        'variant': variant,
                        'width': width,
                        'height': height
                    }
                elif 'mov' in variant.lower() and 'mp4' not in existing_file['variant'].lower():
                    # Prefer MOV over WMV
                    video_files[resolution_key] = {
                        'url': url,
                        'variant': variant,
                        'width': width,
                        'height': height
                    }
                # If it's WMV and we don't have MP4 or MOV, keep the existing WMV
            else:
                # Add new resolution
                video_files[resolution_key] = {
                    'url': url,
                    'variant': variant,
                    'width': width,
                    'height': height
                }

        # Add the selected video files to available_files
        for video_file in video_files.values():
            available_files.append(AvailableVideoFile(
                file_type='video',
                content_type='scene',
                variant=video_file['variant'],
                url=video_file['url'],
                resolution_width=video_file['width'],
                resolution_height=video_file['height'],
            ))

        cover_url = post_data.get('cover_url')
        if cover_url:
            available_files.append(AvailableImageFile(
                file_type='image',
                content_type='cover',
                variant='',
                url=cover_url,
            ))

        release_item = ReleaseItem(
            id=release_id,
            release_date=post_data.get('release_date'),
            short_name=external_id,
            name=post_data.get('title'),
            url=response.url,
            description="",
            duration=0,
            created=datetime.now(tz=UTC).astimezone(),
            last_updated=datetime.now(tz=UTC).astimezone(),
            performers=post_data.get('models'),
            tags=tags,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(post_data),
            site_uuid=self.site.id,
            site=self.site,
        )

        yield release_item
