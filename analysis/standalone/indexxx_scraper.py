import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


class Release:
    def __init__(self, url, title, date, models):
        self.url = url
        self.title = title
        self.date = date
        self.models = models  # List of (official_name, alias) tuples

    def to_dict(self):
        return {
            "url": self.url,
            "title": self.title,
            "date": self.date,
            "models": [{"official_name": m[0], "alias": m[1]} for m in self.models]
        }

class Scraper:
    def __init__(self, base_url="https://www.indexxx.com", site_id=None, site_slug=None):
        self.base_url = base_url
        self.site_id = site_id
        self.site_slug = site_slug
        self.session = requests.Session()

        # Add comprehensive headers
        self.session.headers.update({
            "authority": "www.indexxx.com",
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,fi;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "sec-ch-ua": '"Not(A:Brand";v="99", "Microsoft Edge";v="133", "Chromium";v="133"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
            )
        })

        # Add cookies
        self.session.cookies.update({
            "ageVerified": "true",
            "cf_clearance": (
                "gws_iACWaFPjTCrarTjqpMa82rEgRmXK45l4ndArCEY-1738553527-1.2.1.1-"
                "Fn3Z5R5yOSuklpSjU6IAWyjXMtrIzGuJ1Ex9VzAjwSrfoqlXCqxjnJ2JPjxqdbg34iLDziG0KE4EnkIv1PH3g6ydFu77SzoUo0"
                "IL04ojYme2kHf7uczVsRTjk1MVaRBbX17a7SV2j2LyawuCMWIn3a2dqH0agRql0stNYOTT6MDHEpKkw8jA9_vP0L8hSeYcJ1Yl"
                "D8g.tYmSZmBYsWZMhiS6Ip7VQhqsMiNY3iHI8Be30kWItk6FMTw2HcwMw4SeUkgOLv.GVjievGbzr4X4359LGWzold4LK1c9v"
                ".B0myA"
            )
        })

    def get_site_url(self, page=None):
        """Get URL for site's releases page"""
        if not self.site_id or not self.site_slug:
            raise ValueError("site_id and site_slug must be set")

        url = f"{self.base_url}/websites/{self.site_id}/{self.site_slug}/sets/"
        if page is not None:
            url += f"?page={page}"
        return url

    def get_soup(self, url, delay=1):
        """Get BeautifulSoup object for a URL with rate limiting"""
        time.sleep(delay)  # Rate limiting

        # Update referer for each request
        self.session.headers.update({
            "referer": "/".join(url.split("/")[:-1]) if url.endswith("/") else "/".join(url.split("/")[:-2])
        })

        response = self.session.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch {url}: Status code {response.status_code}")

        return BeautifulSoup(response.text, "html.parser")

    def parse_release_page(self, url):
        """Parse individual release page"""
        soup = self.get_soup(url)

        # Extract basic info
        date = soup.find("span", {"itemprop": "datePublished"}).text
        title = soup.find("span", {"itemprop": "description"}).text

        # Extract models
        models = []
        model_section = soup.find("div", {"itemprop": "about"})
        if model_section:
            for model in model_section.find_all("div", {"itemtype": "http://schema.org/Person"}):
                official_name = model.find("span", {"itemprop": "name"}).text
                alias_div = model.find("div", text=lambda t: t and "as:" in t)
                alias = alias_div.text.replace("as:", "").strip() if alias_div else official_name
                models.append((official_name, alias))

        return Release(url, title, date, models)

    def scrape_list_page(self, page_num):
        """Scrape a single list page"""
        url = self.get_site_url(page_num)
        soup = self.get_soup(url)

        releases = []
        for pset in soup.find_all("div", {"class": "pset"}):
            link = pset.find("div", {"class": "my-2"}).find("a")
            if link:
                release_url = self.base_url + link["href"]
                try:
                    release = self.parse_release_page(release_url)
                    releases.append(release)
                    print(f"Scraped: {release.title}")
                except Exception as e:
                    print(f"Error scraping {release_url}: {e}")

        return releases

    def get_last_page(self):
        """Get the last page number from the pagination"""
        url = self.get_site_url()
        soup = self.get_soup(url)

        # Find the first page number in pagination (which is the last page)
        pagination = soup.find("ul", {"class": "pagination"})
        if pagination:
            # Skip the "newer" button and get the first actual page number
            pages = pagination.find_all("li", {"class": "page-item"})
            for page in pages:
                if "disabled" not in page.get("class", []):
                    try:
                        return int(page.find("a").text)
                    except (ValueError, AttributeError):
                        continue

        raise ValueError("Could not determine last page number")

    def scrape_all_pages(self, start_page=1, end_page=None):
        """Scrape all pages in range"""
        if end_page is None:
            end_page = self.get_last_page()
            print(f"Detected {end_page} total pages")

        all_releases = []

        for page in range(start_page, end_page + 1):
            print(f"\nScraping page {page}/{end_page}...")
            releases = self.scrape_list_page(page)
            all_releases.extend(releases)

            # Save progress after each page
            self.save_releases(all_releases, f"releases_progress_p{page}.json")

        return all_releases

    def save_releases(self, releases, filename):
        """Save releases to JSON file"""
        with Path(filename).open("w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in releases], f, indent=2)

def main():
    # Example usage for x-art
    scraper = Scraper(
        site_id="293",
        site_slug="x-art"
    )
    releases = scraper.scrape_all_pages()
    scraper.save_releases(releases, "releases_final.json")

    # Could also scrape other sites
    # scraper2 = Scraper(site_id="123", site_slug="other-site")
    # releases2 = scraper2.scrape_all_pages()

if __name__ == "__main__":
    main()
