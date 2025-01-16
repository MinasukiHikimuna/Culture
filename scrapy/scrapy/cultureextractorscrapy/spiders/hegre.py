import os
import json
import newnewid
from datetime import datetime, timezone
from dotenv import load_dotenv
import scrapy
from cultureextractorscrapy.spiders.database import get_site_item, get_or_create_performer, get_or_create_tag, get_existing_releases_with_status
from cultureextractorscrapy.items import (
    AvailableGalleryZipFile, AvailableImageFile, AvailableVideoFile, AvailableFileEncoder, ReleaseItem, DirectDownloadItem
)
from cultureextractorscrapy.utils import parse_resolution_height, parse_resolution_width, get_log_filename
from itemadapter import ItemAdapter


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
        
        # Set the log file using the spider name
        crawler.settings.set('LOG_FILE', get_log_filename(spider.name))
        
        # Get force_update from crawler settings or default to False
        spider.force_update = crawler.settings.getbool('FORCE_UPDATE', False)
        
        site_item = get_site_item(spider.site_short_name)
        if site_item is None:
            raise ValueError(f"Site with short_name '{spider.site_short_name}' not found in the database.")
        spider.site = site_item
        
        # Get existing releases with their download status
        spider.existing_releases = get_existing_releases_with_status(site_item.id)
        return spider

    def parse(self, response):
        yield scrapy.Request(
            url=f"{base_url}/movies",
            callback=self.parse_movies,
            cookies=cookies)

        # yield scrapy.Request(
        #     url=f"{base_url}/photos",
        #     callback=self.parse_photos,
        #     cookies=cookies)

    def parse_movies(self, response):
        yield scrapy.Request(
            url=f"{base_url}/movies?films_sort=most_recent&films_page=1",
            callback=self.parse_movies_page,
            cookies=cookies,
            meta={"page": 1}
        )

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
            
            # If force update is enabled, we need to fetch the full page to update metadata
            if self.force_update:
                post_url = post.css('a::attr(href)').get()
                yield scrapy.Request(
                    url=f"{base_url}{post_url}",
                    callback=self.parse_photoset,
                    cookies=cookies,
                    meta={"post_data": self.extract_photo_post_data(post)}
                )
                continue
            
            # Check if we have this release in database
            existing_release = self.existing_releases.get(external_id)
            if existing_release:
                # Compare available files with downloaded files
                available_files = existing_release['available_files']
                downloaded_files = existing_release['downloaded_files']
                
                needed_files = set(
                    (f['file_type'], f['content_type'], f['variant']) 
                    for f in available_files
                )
                
                if not needed_files.issubset(downloaded_files):
                    # We have missing files - yield DirectDownloadItems
                    missing_files = [f for f in available_files if 
                        (f['file_type'], f['content_type'], f['variant']) not in downloaded_files]
                    
                    for file in missing_files:
                        yield DirectDownloadItem(
                            release_id=existing_release['uuid'],
                            file_info=file,
                            url=file['url']
                        )
                    self.logger.info(f"Release {external_id} exists but missing {len(missing_files)} files. Downloading them.")
                else:
                    self.logger.info(f"Release {external_id} already exists with all files downloaded. Skipping.")
            else:
                # If we get here, this is a new release - need to fetch the full page
                post_url = post.css('a::attr(href)').get()
                yield scrapy.Request(
                    url=f"{base_url}{post_url}",
                    callback=self.parse_photoset,
                    cookies=cookies,
                    meta={"post_data": self.extract_photo_post_data(post)}
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


    def parse_movies_page(self, response):
        # Check if the page is empty
        if response.css('h2.hint:contains("This list is currently empty")'):
            return  # Stop pagination when we hit an empty page
        
        # Process posts on the current page
        posts = response.css('div.item')
        for post in posts[0:1]:
            external_id = "movie-" + post.css('a::attr(data-id)').get()
            
            # If force update is enabled, we need to fetch the full page to update metadata
            if self.force_update:
                post_url = post.css('a::attr(href)').get()
                yield scrapy.Request(
                    url=f"{base_url}{post_url}",
                    callback=self.parse_movie,
                    cookies=cookies,
                    meta={"post_data": self.extract_movie_post_data(post)}
                )
                continue
            
            # Check if we have this release in database
            existing_release = self.existing_releases.get(external_id)
            if existing_release:
                # Compare available files with downloaded files
                available_files = existing_release['available_files']
                downloaded_files = existing_release['downloaded_files']
                
                needed_files = set(
                    (f['file_type'], f['content_type'], f['variant']) 
                    for f in available_files
                )
                
                if not needed_files.issubset(downloaded_files):
                    # We have missing files - yield DirectDownloadItems
                    missing_files = [f for f in available_files if 
                        (f['file_type'], f['content_type'], f['variant']) not in downloaded_files]
                    
                    for file in missing_files:
                        yield DirectDownloadItem(
                            release_id=existing_release['uuid'],
                            file_info=file,
                            url=file['url']
                        )
                    self.logger.info(f"Release {external_id} exists but missing {len(missing_files)} files. Downloading them.")
                else:
                    self.logger.info(f"Release {external_id} already exists with all files downloaded. Skipping.")
            else:
                # If we get here, this is a new release - need to fetch the full page
                post_url = post.css('a::attr(href)').get()
                yield scrapy.Request(
                    url=f"{base_url}{post_url}",
                    callback=self.parse_movie,
                    cookies=cookies,
                    meta={"post_data": self.extract_movie_post_data(post)}
                )
        
        # Request the next page
        current_page = response.meta["page"]
        next_page = current_page + 1
        
        # yield scrapy.Request(
        #     url=f"{base_url}/movies?films_sort=most_recent&films_page={next_page}",
        #     callback=self.parse_movies_page,
        #     cookies=cookies,
        #     meta={"page": next_page}
        # )

    def parse_movie(self, response):
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
        
        # Extract video download links - only main video files (not trailers)
        video_links = response.css('div.film-downloads h2.download-type:contains("Full feature film") + div.resolution.content a')
        highest_quality_video = None
        highest_resolution = 0
        
        for link in video_links:
            url = link.attrib['href']
            variant = link.css('strong::text').get().strip()
            
            # Extract resolution from the em tag
            resolution_text = link.css('em::text').get()
            if resolution_text:
                # Parse resolution (e.g., "3840x2160, 2.1 GB")
                resolution = resolution_text.strip().split(',')[0]
                width, height = map(int, resolution.split('x'))
                
                # Keep track of highest quality
                total_pixels = width * height
                if total_pixels > highest_resolution:
                    highest_resolution = total_pixels
                    highest_quality_video = {
                        'url': url,
                        'variant': variant,
                        'width': width,
                        'height': height
                    }
        
        # Add only the highest quality video to available_files
        if highest_quality_video:
            video_file = AvailableVideoFile(
                file_type='video',
                content_type='scene',
                variant=highest_quality_video['variant'],
                url=highest_quality_video['url'],
                resolution_width=highest_quality_video['width'],
                resolution_height=highest_quality_video['height']
            )
            available_files.append(video_file)
            
            # Yield DirectDownloadItem for video
            yield DirectDownloadItem(
                release_id=release_id,
                file_info=ItemAdapter(video_file).asdict(),
                url=video_file.url
            )
        
        # Add and download cover and board images
        cover_url = post_data.get('cover_url')
        if cover_url:
            cover_file = AvailableImageFile(
                file_type='image',
                content_type='cover',
                variant='cover',
                url=cover_url,
            )
            available_files.append(cover_file)
            
            yield DirectDownloadItem(
                release_id=release_id,
                file_info=ItemAdapter(cover_file).asdict(),
                url=cover_file.url
            )
            
        board_url = post_data.get('board_url')
        if board_url:
            board_file = AvailableImageFile(
                file_type='image',
                content_type='board',
                variant='board',
                url=board_url,
            )
            available_files.append(board_file)
            
            yield DirectDownloadItem(
                release_id=release_id,
                file_info=ItemAdapter(board_file).asdict(),
                url=board_file.url
            )
            
        # Update post_data with additional information
        post_data.update({
            "additional_performers": additional_performers,
            "raw_html": response.text
        })

        # Create and yield the ReleaseItem (without downloading files)
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

    def extract_movie_post_data(self, post):
        """Extract metadata from a post element on the movie list page."""
        external_id = "movie-" + post.css('a::attr(data-id)').get()
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

        return {
            "external_id": external_id,
            "title": title,
            "cover_url": cover_url,
            "board_url": board_url,
            "release_date": release_date
        }

    def extract_photo_post_data(self, post):
        """Extract metadata from a post element on the gallery list page."""
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

        return {
            "external_id": external_id,
            "title": title,
            "cover_url": cover_url,
            "board_url": board_url,
            "release_date": release_date
        }
