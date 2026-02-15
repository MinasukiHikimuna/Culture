# %%
import os
import sys
from pathlib import Path


sys.path.append(str(Path.cwd().parent))

from libraries.client_stashapp import StashAppClient, get_stashapp_client
from libraries.StashDbClient import StashDbClient


stash = get_stashapp_client()
stash_client = StashAppClient()

stashbox_client = StashDbClient(
    os.getenv("STASHDB_ENDPOINT"),
    os.getenv("STASHDB_API_KEY"),
)

scene_id = 29817
existing_scene = stash_client.find_scenes({ "id": { "value": scene_id, "modifier": "EQUALS" } })
existing_scene

import re


# Function to parse slug from filename
def parse_slug(filename):
    # Remove resolution and extension using regex
    # This will match _<numbers>P.mp4 at the end of the string
    return re.sub(r"_\d+P\.mp4$", "", filename)

slug = parse_slug(existing_scene.to_dicts()[0]["stashapp_primary_file_basename"])
slug



# %%
slug = "ana-video-dido-angel"


# %%
from datetime import datetime

import requests
from bs4 import BeautifulSoup


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

site_url = f"https://www.puffynetwork.com/videos/{slug}/"

response = requests.get(site_url, headers=headers)
print(response.status_code)
print(response.text)


# %%
import base64

from bs4 import BeautifulSoup


soup = BeautifulSoup(response.text, "html.parser")

# Find the video element by ID
video_element = soup.find(id="video")
if video_element:
    poster_url = video_element.get("poster")
    if poster_url:
        # Download the image and convert to base64
        image_response = requests.get(poster_url, headers=headers)
        if image_response.status_code == 200:
            base64_image = base64.b64encode(image_response.content).decode("utf-8")
            cover_image_base64 = f"data:image/jpeg;base64,{base64_image}"
            print(f"Cover Image Base64: {cover_image_base64}")
        else:
            print("Failed to download image")

# Parse title information
title_span = soup.select_one("h2.title > span")
if title_span:
    # Get text and clean it
    title_text = title_span.text.strip()
    # Split by "—" (note: this is an em dash)
    parts = title_text.split("—")
    if len(parts) == 2:
        performer = parts[0].strip()
        title = parts[1].strip()
        print(f"Performer: {performer}")
        print(f"Title: {title}")

# Parse description
show_more = soup.select_one("div.show_more")
if show_more:
    # Get direct text content before any child elements using string instead of text
    description = show_more.find(string=True, recursive=False).strip()
    print(f"Description: {description}")

# Parse date
date_span = soup.select_one("dt span[style*='color:#d23783']")
if date_span:
    date_str = date_span.text.strip()
    # Convert date from "Nov 29, 2011" to "2011-11-29"
    date_obj = datetime.strptime(date_str, "%b %d, %Y")
    formatted_date = date_obj.strftime("%Y-%m-%d")
    print(f"Release Date: {formatted_date}")

# Parse performers
performers_section = soup.select_one("section.downloads.downloads2 dl")
if performers_section:
    # Find all performer links within the dl element
    performer_links = performers_section.select("dd a")
    performers = [link.text for link in performer_links]
    print(f"Performers: {performers}")

# %%
print(performers)

# %%
performer = stash.find_performer("Dido Angel")
print(performer["id"] + " " + performer["name"])


# %%
performer_mapping = {
    "Gina": 935,
    "Christy Charming": 155,
    "Kari": 952,
    "Delphine": 462,
    "Charlotte": 331,
    "Zuzana": 249,
    "Lola": 3,
}


# %%
# Check if all performers are in the mapping
if not all(performer in performer_mapping for performer in performers):
    raise ValueError("Some performers are not in the mapping")

stash.update_scene({
    "id": scene_id,
    "title": title,
    "details": description,
    "date": formatted_date,
    "performer_ids": [performer_mapping[performer] for performer in performers],
    "studio_id": 1237,
    "cover_image": cover_image_base64,
    "urls": site_url
})

