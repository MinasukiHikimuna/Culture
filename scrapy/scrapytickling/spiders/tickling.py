from datetime import datetime, timezone
import os
import json
import newnewid
from dotenv import load_dotenv
import scrapy
from scrapytickling.spiders.database import get_sites, get_existing_release_short_names
from scrapytickling.items import ReleaseItem

load_dotenv()

cookies = json.loads(os.getenv("COOKIES"))
base_url = os.getenv("BASE_URL")

class TicklingSpider(scrapy.Spider):
    name = "tickling"
    allowed_domains = os.getenv("ALLOWED_DOMAINS").split(",")
    start_urls = [f"{base_url}/updates/"]
    site_short_name = "ticklingsubmission"
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(TicklingSpider, cls).from_crawler(crawler, *args, **kwargs)
        sites = get_sites()
        site = next((site for site in sites if site.short_name == spider.site_short_name), None)
        if site is None:
            raise ValueError(f"Site with short_name '{spider.site_short_name}' not found in the database.")
        spider.site = site
        spider.existing_short_names = get_existing_release_short_names(site.uuid)
        return spider

    def parse(self, response):
        yield scrapy.Request(url=response.url, callback=self.parse_studios, cookies=cookies)

    def parse_studios(self, response):
        menu_items = response.css("div.studio-side-menu ul.menu li")

        for item in menu_items[0:1]:
            href = item.css('a::attr(href)').get()
            yield scrapy.Request(
                url=f"{base_url}{href}",
                callback=self.parse_studio,
                cookies=cookies
            )

    def parse_studio(self, response):
        # Get the last page number from the pager-last element
        last_page = response.css('ul.pager li.pager-last a::attr(href)').re_first(r'page=(\d+)')
        if last_page:
            last_page = int(last_page)
            # The page nuumbering is weird. First page is 0 but last page is the total number of pages.
            # If last page is 116, then there are 117 pages.
            for page_number in range(0, last_page)[0:1]:
                yield scrapy.Request(
                    url=f"{response.url}?page={page_number}",
                    callback=self.parse_updates,
                    cookies=cookies
                )

    def parse_updates(self, response):
        updates = response.css('div.views-row div.node')
        for update in updates[0:1]:
            url = update.css('h2 a::attr(href)').get()
            yield scrapy.Request(
                url=f"{base_url}{url}",
                callback=self.parse_update,
                cookies=cookies
            )

    def parse_update(self, response):
        studio_slug = response.url.split('/')[-3]
        movie_slug = response.url.split('/')[-2]
        studio_name = response.css(f'div#main-content ul.menu li a.{studio_slug}::attr(title)').get()
        movie_name = response.css('h1.title::text').get()

        # Check if this release already exists
        if movie_slug in self.existing_short_names:
            self.logger.info(f"Release with short_name {movie_slug} already exists for this site. Skipping.")
            return

        date_text = response.xpath('//p[@class="content"][span[@class="label" and contains(text(), "Datum:")]]/text()').get()
        
        if date_text:
            date_text = date_text.strip()
            try:
                date = datetime.strptime(date_text, '%b %d %Y').date()
            except ValueError:
                date = None
        else:
            date = None

        # Corrected XPath for duration
        duration_raw = response.xpath('string(//div[contains(@class, "field-item")][div[contains(@class, "field-label-inline-first") and contains(text(), "Time:")]])').get().strip()
        if duration_raw:
            duration_text = duration_raw.replace('Time:', '').strip()
        else:
            duration_text = None

        # Extract performers
        performers = []
        performer_elements = response.css('div.field-field-tag-performers div.field-items div.field-item')
        for element in performer_elements:
            if 'Performers:' in element.get():
                name = element.css('a::text').get()
                url = element.css('a::attr(href)').get()
                if name and url:
                    performers.append({
                        'name': name.strip(),
                        'url': f"{base_url}{url.strip()}"
                    })

        keywords = []
        keyword_elements = response.css('div.field-field-tag-keywords div.field-items div.field-item')
        for element in keyword_elements:
            if 'Keywords:' in element.get():
                name = element.css('a::text').get()
                url = element.css('a::attr(href)').get()
                if name and url:
                    keywords.append({
                        'name': name.strip(),
                        'url': f"{base_url}{url.strip()}"
                    })

        description = response.css("div.product-body p::text").get()

        # Extract downloadable files
        download_links = []
        file_elements = response.css('div.download-files-block span.views-field-field-mp4fullhd-url, div.download-files-block span.views-field-field-mp4hd-url')
        for element in file_elements:
            link = element.css('a::attr(href)').get()
            title = element.css('a::attr(title)').get()
            text = element.css('a::text').get()
            file_type = element.css('span.field-content::text').re_first(r'\((.*?)\)')
            if link and title and text:
                download_links.append({
                    'url': link,
                    'title': title,
                    'text': text,
                    'type': file_type
                })

        preview_video_url = response.css("div#mediaspace span.field-content a::attr(href)").get()
        preview_image_url = response.css("div#mediaspace span.field-content a img::attr(src)").get()

        # Create ReleaseItem
        release_item = ReleaseItem(
            id=newnewid.uuid7(),
            release_date=date.isoformat() if date else None,
            short_name=movie_slug,
            name=movie_name,
            url=response.url,
            description=description,
            duration=0,
            created=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
            performers=[],
            tags=[],
            available_files=json.dumps(download_links),
            json_document=json.dumps({
                'preview_video_url': preview_video_url,
                'preview_image_url': preview_image_url,
                'studio_name': studio_name,
                'studio_slug': studio_slug,
            }),
            site_uuid=self.site.uuid
        )

        # Add the new short_name to the set of existing short_names
        self.existing_short_names.add(movie_slug)

        yield release_item
