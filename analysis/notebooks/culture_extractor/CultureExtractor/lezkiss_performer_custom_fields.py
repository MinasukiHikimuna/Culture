# %%
import os
import sys

import polars as pl
from dotenv import load_dotenv


sys.path.append(os.path.dirname(os.getcwd()))

import libraries.client_culture_extractor as client_culture_extractor


load_dotenv()

# Culture Extractor
user = os.environ.get("CE_DB_USERNAME")
pw = os.environ.get("CE_DB_PASSWORD")
host = os.environ.get("CE_DB_HOST")
port = os.environ.get("CE_DB_PORT")
db = os.environ.get("CE_DB_NAME")

connection_string = f"dbname={db} user={user} password={pw} host={host} port={port}"

culture_extractor_client = client_culture_extractor.ClientCultureExtractor(
    connection_string
)


# StashApp
from libraries.client_stashapp import StashAppClient, get_stashapp_client


stash_client = StashAppClient()
stash_raw_client = get_stashapp_client()


# StashDB
import os

import dotenv

from libraries.StashDbClient import StashDbClient


dotenv.load_dotenv()

stashbox_client = StashDbClient(
    os.getenv("STASHDB_ENDPOINT"),
    os.getenv("STASHDB_API_KEY"),
)


# Functions
def hex_to_binary(hex_string):
    return bin(int(hex_string, 16))[2:].zfill(64)


def calculate_hamming_distance(phash1, phash2):
    # Convert hexadecimal phashes to binary
    binary1 = hex_to_binary(phash1)
    binary2 = hex_to_binary(phash2)

    # Ensure both binary strings are of equal length
    if len(binary1) != len(binary2):
        raise ValueError("Binary strings must be of equal length")

    # Calculate Hamming distance
    return sum(c1 != c2 for c1, c2 in zip(binary1, binary2))


# Example usage:
# phash1 = "951428607cf7cb8f"
# phash2 = "951428607cf7cb8e"
# distance = calculate_hamming_distance(phash1, phash2)
# print(f"Hamming distance between {phash1} and {phash2}: {distance}")


def levenshtein(s1: str, s2: str):
    if not s1:
        return None
    if not s2:
        return None
    from Levenshtein import distance

    return distance(s1.lower(), s2.lower())


# %%
all_tags = stash_raw_client.find_tags()
all_ce_sites = culture_extractor_client.get_sites()
all_ce_sub_sites = culture_extractor_client.get_sub_sites()
all_stash_studios = stash_client.get_studios()
# all_ce_sites_stash_studios_joined = all_ce_sites.join(
#     all_stash_studios, left_on="ce_sites_uuid", right_on="stash_studios_ce_id", how="left", coalesce=False
# )
all_ce_sites_stash_studios_joined = all_ce_sites.join(
    all_stash_studios,
    left_on="ce_sites_name",
    right_on="stash_studios_name",
    how="left",
    coalesce=False,
)

# Then join remaining unmatched rows by name
for row in all_ce_sites_stash_studios_joined.filter(
    pl.col("stash_studios_id").is_null()
).iter_rows(named=True):
    print(f"Unmatched studio {row["ce_sites_uuid"]} {row["ce_sites_name"]}")

# %%
# Link by name
site_name = "LezKiss"
rows = all_ce_sites_stash_studios_joined.filter(
    pl.col("stash_studios_name").str.contains(site_name)
)
selected_studio = rows.to_dicts()[0]
stash_client.set_studio_stash_id_for_endpoint(
    selected_studio["stash_studios_id"],
    "https://culture.extractor/graphql",
    selected_studio["ce_sites_uuid"],
)
selected_studio

# Manual override
# stash_client.set_studio_stash_id_for_endpoint(306, "https://culture.extractor/graphql", "018b94b1-b5e9-71d7-ab70-8665111e8bd8")
# selected_studio = all_ce_sites_stash_studios_joined.filter(
#     pl.col("ce_sites_uuid").eq("018b94b1-b5e9-71d7-ab70-8665111e8bd8")
# ).to_dicts()[0]
# selected_studio

# %%
downloads = culture_extractor_client.get_downloads(selected_studio["ce_sites_uuid"])
downloads


# %%
short_name = "lezkiss"

all_stashapp_performers = stash_client.get_performers()
all_stashapp_performers = all_stashapp_performers.with_columns(
    pl.col("stashapp_custom_fields")
    .list.eval(
        pl.when(pl.element().struct.field("key") == f"CultureExtractor.{short_name}")
        .then(pl.element().struct.field("value"))
        .otherwise(None)
    )
    .list.eval(pl.element().filter(pl.element().is_not_null()))
    .list.first()
    .alias("ce_custom_field_value")
)
all_stashapp_performers

# %%
site_performers = all_stashapp_performers.filter(
    pl.col("ce_custom_field_value").is_not_null()
)
site_performers

# %%
scenes = stash_client.find_scenes_by_studio([selected_studio["stash_studios_id"]])
scenes

# First, let's see what columns we have in the scenes DataFrame
print("\nAvailable columns in scenes DataFrame:")
print(scenes.columns)


# Get all performers who appear in LezKiss scenes
def get_lezkiss_scene_performers(scenes_df, all_stashapp_performers):
    # Show a small sample of the performers data
    print("\nDebug: Sample of scenes' performers (first 2 scenes):")
    performers_list = scenes_df["stashapp_performers"].to_list()
    for i, performers in enumerate(performers_list[:2]):
        print(f"Scene {i + 1} performers:", performers)

    # Get all performer IDs from the scenes
    performer_ids = set()

    # Get the performers column as a list
    for scene_performers in performers_list:
        if scene_performers:
            try:
                # The performers are dictionaries with 'stashapp_performers_id' field
                performer_ids.update(
                    str(p["stashapp_performers_id"])
                    for p in scene_performers
                    if p.get("stashapp_performers_id")
                )
            except Exception as e:
                print(f"Error processing performers: {e}")
                print(f"Problematic data: {scene_performers}")

    print("\nDebug: Sample of found performer IDs (first 5):", list(performer_ids)[:5])

    # Get performers from the all_stashapp_performers DataFrame
    scene_performers = all_stashapp_performers.filter(
        pl.col("stashapp_id").cast(pl.Utf8).is_in(list(performer_ids))
    )
    return scene_performers


# Get performers with LezKiss custom field
def get_lezkiss_custom_field_performers(all_stashapp_performers):
    return all_stashapp_performers.filter(pl.col("ce_custom_field_value").is_not_null())


# Get the data
scene_performers = get_lezkiss_scene_performers(scenes, all_stashapp_performers)
custom_field_performers = get_lezkiss_custom_field_performers(all_stashapp_performers)

# Print results with sorted names for easier comparison
print("\nSample of performers in LezKiss scenes (first 5):")
print(
    scene_performers.select(["stashapp_id", "stashapp_name", "ce_custom_field_value"])
    .sort("stashapp_name")
    .head(5)
)

print("\nSample of performers with LezKiss CE UUID (first 5):")
print(
    custom_field_performers.select(
        ["stashapp_id", "stashapp_name", "ce_custom_field_value"]
    )
    .sort("stashapp_name")
    .head(5)
)

# Find performers that appear in scenes but don't have CE UUID
missing_custom_field = scene_performers.filter(
    pl.col("ce_custom_field_value").is_null()
)
print("\nSample of performers in scenes but missing CE UUID (first 5):")
print(
    missing_custom_field.select(["stashapp_id", "stashapp_name"])
    .sort("stashapp_name")
    .head(5)
)

# Find performers that have CE UUID but don't appear in scenes
not_in_scenes = custom_field_performers.filter(
    ~pl.col("stashapp_id").is_in(scene_performers["stashapp_id"])
)
print("\nSample of performers with CE UUID but not in scenes (first 5):")
print(
    not_in_scenes.select(["stashapp_id", "stashapp_name", "ce_custom_field_value"])
    .sort("stashapp_name")
    .head(5)
)
