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

cookies = json.loads(os.getenv("HEGRE_COOKIES"))
base_url = os.getenv("HEGRE_BASE_URL")

class HegreSpider(scrapy.Spider):
    name = "hegre"
    allowed_domains = os.getenv("HEGRE_ALLOWED_DOMAINS").split(",")
    start_urls = [base_url]
    site_short_name = "hegre"
    
    # Add this new class attribute to store desired performer short names
    desired_performers = []

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(HegreSpider, cls).from_crawler(crawler, *args, **kwargs)
        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(f"Site with short_name '{spider.site_short_name}' not found in the database.")
        spider.site = site_item
        spider.existing_releases = get_existing_release_short_names(site_item.id)
        return spider

    def parse(self, response):
        # yield scrapy.Request(
        #     url=f"{base_url}/movies",
        #     callback=self.parse_movies,
        #     cookies=cookies)

        yield scrapy.Request(
            url=f"{base_url}/photos",
            callback=self.parse_photos,
            cookies=cookies)

    def parse_movies(self, response):
        pass

    def parse_photos(self, response):
        yield scrapy.Request(
            url=f"{base_url}/photos?galleries_sort=most_recent&galleries_page=1",
            callback=self.parse_photos_page,
            cookies=cookies,
            meta={"page": 1}
        )

    def parse_photos_page(self, response):
        # Check if the page is empty
        if response.css('h2.hint:contains("This list is currently empty")'):
            return  # Stop pagination when we hit an empty page
        
        # Process posts on the current page
        posts = response.css('div.item')
        for post in posts:
            external_id = "gallery-" + post.css('a::attr(data-id)').get()
            title = post.css('a::attr(title)').get()
            
            # Get URLs from the cover-links div inside details
            cover_url = post.css('div.details div.cover-links a[data-lightbox="lightbox--poster_image"]::attr(href)').get()
            board_url = post.css('div.details div.cover-links a[data-lightbox="lightbox--board_image"]::attr(href)').get()
            
            # Get the release date from the details section and parse it
            raw_release_date = post.css('div.details h4 small.right::text').get()
            if raw_release_date:
                # Remove the ordinal indicators (st, nd, rd, th) before parsing
                cleaned_date = raw_release_date.replace('st,', ',').replace('nd,', ',').replace('rd,', ',').replace('th,', ',')
                parsed_release_date = datetime.strptime(cleaned_date.strip(), '%b %d, %Y').date()
                release_date = parsed_release_date.isoformat()
            else:
                release_date = None

            post_url = post.css('a::attr(href)').get()

            post_data = {
                "external_id": external_id,
                "title": title,
                "cover_url": cover_url,
                "board_url": board_url,
                "release_date": release_date
            }
            
            # Check if any of the desired performers are in this release
            # if self.desired_performers and not any(model['short_name'] in self.desired_performers for model in models):
            #     continue  # Skip this release if it doesn't contain any desired performers

            yield scrapy.Request(
                url=f"{base_url}{post_url}",
                callback=self.parse_photoset,
                cookies=cookies,
                # TODO: priority=10,
                meta={
                    "post_data": post_data
                }
            )
        
        # Request the next page
        current_page = response.meta["page"]
        next_page = current_page + 1
        
        yield scrapy.Request(
            url=f"{base_url}/photos?galleries_sort=most_recent&galleries_page={next_page}",
            callback=self.parse_photos_page,
            cookies=cookies,
            meta={"page": next_page}
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

        # Parse performers from record-models div
        performers = []
        performer_elements = response.css('div.record-models a.record-model')
        for performer_element in performer_elements:
            performer_name = performer_element.css('::attr(title)').get()
            performer_url = f"{base_url}{performer_element.css('::attr(href)').get()}"
            performer_short_name = performer_url.split('/')[-1]
            
            # Create or get performer from database
            performer = get_or_create_performer(
                self.site.id,
                performer_short_name,
                performer_name,
                performer_url
            )
            performers.append(performer)

        # Parse additional performers from related content section
        additional_performers = []
        related_sections = response.css('div.record-related-content div.linked-items > div')
        for section in related_sections:
            section_title = section.css('h3::text').get()
            if section_title and 'Galleries' in section_title:
                # Extract performer name from section title (e.g., "Goro Galleries" -> "Goro")
                performer_name = section_title.replace(' Galleries', '').strip()
                performer_short_name = performer_name.lower()
                performer_url = f"{base_url}/models/{performer_short_name}"
                
                additional_performers.append({
                    "name": performer_name,
                    "short_name": performer_short_name,
                    "url": performer_url
                })
                
                # Create or get performer from database
                performer = get_or_create_performer(
                    self.site.id,
                    performer_short_name,
                    performer_name,
                    performer_url
                )
                
                # Only add if not already in performers list
                if not any(p.short_name == performer_short_name for p in performers):
                    performers.append(performer)

        # Parse tags from the approved-tags div
        tags = []
        tag_elements = response.css('div.approved-tags a.tag')
        for tag_element in tag_elements:
            tag_name = tag_element.css('::text').get()
            tag_id = tag_element.css('::attr(data-id)').get()
            tag_short_name = tag_name.lower().replace(' ', '-')
            tag_url = f"{base_url}{tag_element.css('::attr(href)').get()}"
            
            # Create or get tag from database
            tag = get_or_create_tag(
                self.site.id,
                tag_short_name,
                tag_name,
                tag_url
            )
            tags.append(tag)
        
        available_files = []
        
        # Extract gallery download links from the new structure
        gallery_links = response.css('div.gallery-zips a')
        largest_gallery = None
        largest_size_mb = 0
        
        for link in gallery_links:
            url = link.attrib['href']
            # Extract resolution from the URL (e.g., "14000px" from filename)
            resolution = url.split('-')[-1].split('.')[0]
            
            # Get the edition name and file size info
            variant = link.css('strong::text').get().strip()
            file_size_text = link.css('em::text').get()
            
            # Extract file size in MB
            if file_size_text and 'MB' in file_size_text:
                # Get the last number before "MB" (e.g., from "6000px, 69 MB" get "69")
                size_mb = float(file_size_text.split('MB')[0].split(',')[-1].strip())
                
                # Keep track of the largest gallery
                if size_mb > largest_size_mb:
                    largest_size_mb = size_mb
                    
                    # Handle 'originals' case
                    if resolution == 'originals':
                        # Try to get resolution from the file size text
                        if 'px' in file_size_text:
                            width = int(file_size_text.split('px')[0].strip())
                        else:
                            width = 0
                    else:
                        width = int(resolution.replace('px', ''))
                    
                    largest_gallery = {
                        'url': url,
                        'variant': variant,
                        'width': width
                    }
        
        # Add only the largest gallery to available_files
        if largest_gallery:
            available_files.append(AvailableGalleryZipFile(
                file_type='zip',
                content_type='gallery',
                variant=largest_gallery['variant'],
                url=largest_gallery['url'],
                resolution_width=largest_gallery['width'],
            ))
                               
        cover_url = post_data.get('cover_url')
        if cover_url:
            available_files.append(AvailableImageFile(
                file_type='image',
                content_type='cover',
                variant='cover',
                url=cover_url,
            ))
            
        board_url = post_data.get('board_url')
        if board_url:
            available_files.append(AvailableImageFile(
                file_type='image',
                content_type='board',
                variant='board',
                url=board_url,
            ))
            
        # Update post_data with additional information
        post_data.update({
            "additional_performers": additional_performers,
            "raw_html": response.text
        })

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
            performers=performers,
            tags=tags,
            available_files=json.dumps(available_files, cls=AvailableFileEncoder),
            json_document=json.dumps(post_data),
            site_uuid=self.site.id,
            site=self.site,
        )
        
        yield release_item


    def parse_videos(self, response):
        # Start with page 1
        yield scrapy.Request(
            url=f"{base_url}/videos?page=1",
            callback=self.parse_videos_page,
            cookies=cookies,
            meta={"page": 1}
        )

    def parse_videos_page(self, response):
        # Check if the page is empty
        if response.css('h2.hint:contains("This list is currently empty")'):
            return  # Stop pagination when we hit an empty page
        
        # Process posts on the current page
        posts = response.css('div.post_item')
        for post in posts[0:1]:
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

        # Request the next page
        current_page = response.meta["page"]
        next_page = current_page + 1
        
        yield scrapy.Request(
            url=f"{base_url}/videos?page={next_page}",
            callback=self.parse_videos_page,
            cookies=cookies,
            meta={"page": next_page}
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
                variant='cover',
                url=cover_url,
            ))
            
        board_url = post_data.get('board_url')
        if board_url:
            available_files.append(AvailableImageFile(
                file_type='image',
                content_type='board',
                variant='board',
                url=board_url,
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
