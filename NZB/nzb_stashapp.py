# %%

import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath("")))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

import sys
import os

sys.path.append(os.path.dirname(os.getcwd()))

from NZB.search import NZBSearch
from NZB.sabnzbd import SABnzbdClient

searcher = NZBSearch()


def format_str_iso_date_as_yy_mm_dd(iso_date_str):
    from datetime import datetime

    parsed_date = datetime.strptime(iso_date_str, "%Y-%m-%d")
    return format_iso_date_as_yy_mm_dd(parsed_date)


def format_iso_date_as_yy_mm_dd(iso_date):
    return iso_date.strftime("%y %m %d")


def format_studio_name(studio_name):
    return studio_name.replace(" ", "").replace("-", "")


stash = get_stashapp_client("MISSING_SDB_")
stash_client = StashAppClient("MISSING_SDB_")

# %%
# StashDB
from libraries.StashDbClient import StashDbClient
import dotenv
import os

dotenv.load_dotenv()

stashbox_client = StashDbClient(
    os.getenv("STASHDB_ENDPOINT"),
    os.getenv("STASHDB_API_KEY"),
)

# %%
# Find by studio
studio_id = stash.find_studio("Parasited")["id"]

target_scenes: pl.DataFrame = pl.DataFrame(
    stash.find_scenes(
        {"studios": {"value": [studio_id], "modifier": "INCLUDES"}},
        fragment="id title date details studio { id name } performers { id name }",
    )
)
target_scenes = target_scenes.sort(by=["studio", "date"])
target_scenes

# %%
# Find by performer
performer_id = stash.find_performer("Stacy Cruz")["id"]

target_scenes: pl.DataFrame = pl.DataFrame(
    stash.find_scenes(
        {"performers": {"value": [performer_id], "modifier": "INCLUDES"}},
        fragment="id title date details studio { id name } performers { id name }",
    )
)
target_scenes = target_scenes.sort(by=["studio", "date"])
# target_scenes = target_scenes.filter(pl.col("studio").struct.field("name").str.contains("Passion HD"))
target_scenes = target_scenes.slice(0, 10)
target_scenes


# %%
# Find by performer and studio
performer_id = stash.find_performer("Pearl")["id"]
studio_id = stash.find_studio("Viv Thomas")["id"]

target_scenes: pl.DataFrame = pl.DataFrame(
    stash.find_scenes(
        {
            "performers": {"value": [performer_id], "modifier": "INCLUDES"},
            "studios": {"value": [studio_id], "modifier": "INCLUDES"},
        },
        fragment="id title date details studio { id name } performers { id name }",
    )
)
target_scenes = target_scenes.sort(by=["studio", "date"])
target_scenes


# %%
def generate_search_queries(stashdb_target_scene, stashdb_primary_performers):
    """Generate a list of search queries for a scene, from most to least specific"""
    queries = []

    # Get performer names (using alias if available)
    performer_names = [
        performer["as"] or performer["performer"]["name"]
        for performer in stashdb_primary_performers
    ]

    # Format date in multiple formats for better matching
    from datetime import datetime

    date_obj = datetime.strptime(stashdb_target_scene["date"], "%Y-%m-%d")

    # Different date formats that might appear in NZB titles
    date_formats = [
        date_obj.strftime("%y.%m.%d"),  # 25.02.22
        date_obj.strftime("%Y.%m.%d"),  # 2025.02.22
        date_obj.strftime("%y %m %d"),  # 25 02 22 (original format)
        date_obj.strftime("%Y %m %d"),  # 2025 02 22
    ]

    studio_name = format_studio_name(stashdb_target_scene["studio"]["name"])

    # Most specific: studio + performer + date (try multiple date formats)
    if performer_names:
        for date_format in date_formats:
            queries.append(f'{studio_name} {performer_names[0]} "{date_format}"')

    # Next: studio + date (try multiple date formats)
    for date_format in date_formats:
        queries.append(f'{studio_name} "{date_format}"')

    # Less specific fallbacks only if we haven't found anything
    if performer_names:
        # Performer + date without studio
        for date_format in date_formats:
            queries.append(f'{performer_names[0]} "{date_format}"')

        # Finally: studio + first performer (no date)
        queries.append(f"{studio_name} {performer_names[0]}")

    return queries


# Get search queries for each scene
search_queries_list = []
scene_info_list = []  # Store scene info for later mapping

for scene_dict in target_scenes.to_dicts():
    # Get StashDB data for scene
    stashapp_target_scene = stash.find_scene(
        scene_dict["id"],
        fragment="id title details urls date performers { id name stash_ids { stash_id endpoint } } studio { id name } stash_ids { stash_id endpoint }",
    )

    # Get StashDB ID
    stashdb_ids = [
        stash_id["stash_id"]
        for stash_id in stashapp_target_scene["stash_ids"]
        if stash_id["endpoint"] == "https://stashdb.org/graphql"
    ]
    if not stashdb_ids:
        continue

    # Get StashDB scene data
    stashdb_scenes = stashbox_client.query_scenes([stashdb_ids[0]])
    if stashdb_scenes.is_empty():
        continue
    stashdb_target_scene = stashdb_scenes.to_dicts()[0]

    # Get primary performers
    primary_performer_ids = [
        stash_id["stash_id"]
        for performer in stashapp_target_scene["performers"]
        for stash_id in performer["stash_ids"]
        if stash_id["endpoint"] == "https://stashdb.org/graphql"
    ]

    stashdb_primary_performers = [
        performer
        for performer in stashdb_target_scene["performers"]
        if performer["performer"]["id"] in primary_performer_ids
    ]

    # Generate queries for this scene
    scene_queries = generate_search_queries(
        stashdb_target_scene, stashdb_primary_performers
    )
    search_queries_list.append(scene_queries)

    # Store scene info
    scene_info = {
        "stashapp_id": stashapp_target_scene["id"],
        "stashapp_title": stashapp_target_scene["title"],
        "stashdb_id": stashdb_ids[0],
        "stashdb_title": stashdb_target_scene["title"],
        "studio": stashdb_target_scene["studio"]["name"],
        "date": stashdb_target_scene["date"],
        "performers": [p["performer"]["name"] for p in stashdb_primary_performers],
        "primary_query": scene_queries[0],  # Store primary query to use as join key
    }
    scene_info_list.append(scene_info)

# Create DataFrame with scene info
scenes_df = pl.DataFrame(scene_info_list)

# Prepare validation info for the search
validation_info = [
    {
        "studio": scene_info["studio"],
        "date": scene_info["date"],
        "performers": scene_info["performers"],
    }
    for scene_info in scene_info_list
]

# Perform the search with validation
results = searcher.search_multiple(search_queries_list, validation_info)

# Join scene info with search results
results_with_scenes = results.join(
    scenes_df, left_on="primary_query", right_on="primary_query", how="left"
)

# Sort results to show best matches first for each scene
results_with_scenes = results_with_scenes.sort(
    [
        "stashapp_id",  # Group by scene
        "is_best_match",  # Best matches first
        "size",  # Larger files first
    ],
    descending=[False, True, True],
)

results_with_scenes

# %%
best_results = results_with_scenes.filter(pl.col("is_best_match")).unique(
    ["link", "title"]
)
best_results

# %%
best_results.write_json()


# %%
sab = SABnzbdClient()

for result in best_results.iter_rows(named=True):
    # Add the download
    nzb_result = sab.add_nzb_url(result["link"], result["title"])

# if nzb_result['status']:
#     if 'nzo_id' in nzb_result:
#         # Wait for download to complete
#         download_result = sab.wait_for_completion(nzb_result['nzo_id'])
#         if download_result['status'] == 'completed':
#             print(f"Download completed! File saved to: {download_result['path']}")
#         else:
#             print(f"Download failed: {download_result.get('error', 'Unknown error')}")
#     else:
#         print(f"Added to SABnzbd but couldn't get job ID: {nzb_result.get('error')}")
# else:
#     print(f"Failed to add to SABnzbd: {nzb_result.get('error')}")

# %%
search_query = "hersexdebut sata"

# %%
results = searcher.search(search_query)
if results.is_empty():
    results = searcher.search(performer_search_query)

results


# %%
first_result = results.to_dicts()[0]

# %%
result = sab.add_nzb_url(first_result["link"], first_result["title"])

# %%
import os

# Get all files in download directory
files = os.listdir(download_result["path"])

# Get full paths and sizes
file_info = []
for f in files:
    full_path = os.path.join(download_result["path"], f)
    if os.path.isfile(full_path):
        size = os.path.getsize(full_path)
        file_info.append((full_path, size))

# Sort by size descending
file_info.sort(key=lambda x: x[1], reverse=True)

# Get largest video file
video_extensions = {".mp4", ".mkv", ".avi", ".wmv", ".mov"}
for filepath, size in file_info:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in video_extensions:
        converted_filepath = filepath
        break
else:
    raise Exception("No video file found in download directory")

print(f"Using video file: {converted_filepath} ({size/1024/1024:.1f} MB)")


# %%
import subprocess
import json

process = subprocess.run(
    [
        "C:\\Tools\\videohashes-windows-amd64.exe",
        "-json",
        converted_filepath,
    ],
    capture_output=True,  # Captures both stdout and stderr
    text=True,  # Returns strings instead of bytes
)
assert process.returncode == 0, f"Failed to run videohashes: {process.stderr}"
videohashes_data = json.loads(process.stdout)
videohashes_data

# %%
videohashes_data["phash"] in [
    fingerprint["hash"]
    for fingerprint in target_scene["fingerprints"]
    if fingerprint["algorithm"] == "PHASH"
]
