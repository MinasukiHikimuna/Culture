import os
import json
import newnewid
from datetime import datetime, timezone
from dotenv import load_dotenv
import scrapy
from cultureextractorscrapy.spiders.database import get_site_item, get_existing_release_short_names, get_or_create_performer, get_or_create_tag
from cultureextractorscrapy.items import (
    AvailableGalleryZipFile, AvailableImageFile, AvailableVideoFile, AvailableVttFile,
    AvailableFileEncoder, available_file_decoder, ReleaseItem, SiteItem
)
from cultureextractorscrapy.utils import parse_resolution_height, parse_resolution_width


load_dotenv()

cookies = json.loads(os.getenv("FEMJOY_COOKIES"))
base_url = os.getenv("FEMJOY_BASE_URL")

class FemjoySpider(scrapy.Spider):
    name = "femjoy"
    allowed_domains = os.getenv("FEMJOY_ALLOWED_DOMAINS").split(",")
    start_urls = [base_url]
    site_short_name = "femjoy"

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
        # yield scrapy.Request(
        #     url=f"{base_url}/photos",
        #     callback=self.parse_photos,
        #     cookies=cookies)
        
        yield scrapy.Request(
            url=f"{base_url}/videos",
            callback=self.parse_videos,
            cookies=cookies)

    def parse_photos(self, response):
        # Extract pagination data
        pagination = response.css('div._pagination div.paginationArea')
        
        # Get the current page number
        current_page = int(pagination.css('div.center a.highlight::text').get())
        
        # Get the last page number
        last_page = int(pagination.css('div.right a.pageBtn[title="last"]::attr(data-page)').get())
        
        for page in range(1, 2): # TODO: last_page + 1):
            yield scrapy.Request(
                url=f"{base_url}/photos?page={page}",
                callback=self.parse_photos_page,
                cookies=cookies,
                meta={"page": page}
            )
       
    def parse_photos_page(self, response):
        posts = response.css('div.post_item')
        for post in posts[0:1]:
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
                models.append({
                    "name": model_name,
                    "short_name": model_url.split('/')[-1] if model_url else None,
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
            created=datetime.now(tz=timezone.utc).astimezone(),
            last_updated=datetime.now(tz=timezone.utc).astimezone(),
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
        
        # Get the current page number
        current_page = int(pagination.css('div.center a.highlight::text').get())
        
        # Get the last page number
        last_page = int(pagination.css('div.right a.pageBtn[title="last"]::attr(data-page)').get())
        
        for page in range(1, 2): # TODO: last_page + 1):
            yield scrapy.Request(
                url=f"{base_url}/videos?page={page}",
                callback=self.parse_videos_page,
                cookies=cookies,
                meta={"page": page}
            )
    
    def parse_videos_page(self, response):
        posts = response.css('div.post_item')
        for post in posts[0:1]:
            external_id = post.css('::attr(data-post-id)').get()
            title = post.css('h1 a::text').get()
            cover_url = post.css('div.post_video a img.item_cover::attr(src)').get()
            
            raw_release_date = post.css('h3 span.posted_on::text').get()
            parsed_release_date = datetime.strptime(raw_release_date, '%b %d, %Y').date() if raw_release_date else None
            release_date = parsed_release_date.isoformat() if parsed_release_date else None
            
            duration_text = post.css('h3 span.counter_photos::text').get().strip()
            if duration_text:
                duration_parts = duration_text.split(':')
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
                models.append({
                    "name": model_name,
                    "short_name": model_url.split('/')[-1] if model_url else None,
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
        for link in video_links:
            url = link.attrib['href']
            variant = link.xpath('text()').get()
            width = parse_resolution_width(variant)
            height = parse_resolution_height(variant)
            
            available_files.append(AvailableVideoFile(
                file_type='video',
                content_type='scene',
                variant=variant,
                url=url,
                resolution_width=width,
                resolution_height=height,
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
            created=datetime.now(tz=timezone.utc).astimezone(),
            last_updated=datetime.now(tz=timezone.utc).astimezone(),
            performers=post_data.get('models'),
            tags=tags,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(post_data),
            site_uuid=self.site.id,
            site=self.site,
        )
        
        yield release_item