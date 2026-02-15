# %%
import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath("")))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

stash = get_stashapp_client()
stash_client = StashAppClient()


# %%
oshash_and_duration_match_tag = stash.find_tag({ "name": "Duplicate: OSHASH And Duration Match" })
duration_match_tag = stash.find_tag({ "name": "Duplicate: Duration Match" })
scenes_with_multiple_versions = stash.find_tag({ "name": "Scene: Multiple Versions" })
duration_mismatch_tag = stash.find_tag({ "name": "Duplicate: Duration Mismatch" })



# %%
scenes_with_duration_mismatch_tag_but_only_one_file = stash.find_scenes({
    "tags": { "value": [duration_mismatch_tag["id"]], "modifier": "INCLUDES" },
    "file_count": { "modifier": "EQUALS", "value": 1 }
}, fragment="id title tags { id name }")
scenes_with_duration_mismatch_tag_but_only_one_file_ids = [scene["id"] for scene in scenes_with_duration_mismatch_tag_but_only_one_file]
scenes_with_duration_mismatch_tag_but_only_one_file




# %%
stash_client.update_tags_for_scenes(
    scenes_with_duration_mismatch_tag_but_only_one_file_ids,
    [],
    [duration_mismatch_tag["name"]]
)






# %%
scenes_with_dupes = stash.find_scenes({ 
  "file_count": {
    "modifier": "GREATER_THAN",
    "value": 1
  },
  "tags": {
    "value": [],
    "modifier": "INCLUDES",
    "excludes": [scenes_with_multiple_versions["id"]]
  }
}, fragment="id title date studio { name } files { id duration path width height size fingerprints { type value } }")





# %%
# Create a list to store all file records
file_records = []

for scene in scenes_with_dupes:
    for i, file in enumerate(scene["files"]):
        # Extract fingerprints
        oshash = next((fp["value"] for fp in file["fingerprints"] if fp["type"] == "oshash"), None)
        phash = next((fp["value"] for fp in file["fingerprints"] if fp["type"] == "phash"), None)
        
        # Create a record for each file
        record = {
            "scene_id": scene["id"],
            "title": scene["title"],
            "date": scene["date"],
            "studio_name": scene["studio"]["name"] if scene["studio"] else None,
            "file_id": file["id"],
            "file_path": file["path"],
            "resolution_width": file["width"],
            "resolution_height": file["height"],
            "size": file["size"],
            "duration": file["duration"],
            "oshash": oshash,
            "phash": phash,
            "is_primary": i == 0  # True if this is the first file in the scene's files list
        }
        file_records.append(record)

# Create Polars DataFrame
scenes_with_multiple_files_df = pl.DataFrame(file_records)
scenes_with_multiple_files_df







# %% [markdown]
# # Finding scenes where durations do not match

# %%
# Create a list to store all file records
file_records = []

for scene in scenes_with_dupes:
    for i, file in enumerate(scene["files"]):
        # Extract fingerprints
        oshash = next((fp["value"] for fp in file["fingerprints"] if fp["type"] == "oshash"), None)
        phash = next((fp["value"] for fp in file["fingerprints"] if fp["type"] == "phash"), None)
        
        # Create a record for each file
        record = {
            "scene_id": scene["id"],
            "title": scene["title"],
            "date": scene["date"],
            "studio_name": scene["studio"]["name"] if scene["studio"] else None,
            "file_id": file["id"],
            "file_path": file["path"],
            "resolution_width": file["width"],
            "resolution_height": file["height"],
            "size": file["size"],
            "duration": round(file["duration"]),  # Round duration to nearest second
            "oshash": oshash,
            "phash": phash,
            "is_primary": i == 0  # True if this is the first file in the scene's files list
        }
        file_records.append(record)

# Create Polars DataFrame
scenes_with_multiple_files_df = pl.DataFrame(file_records)

# Group by scene_id and find scenes where durations don't match
duration_mismatches = scenes_with_multiple_files_df.group_by("scene_id").agg([
    pl.col("title").first().alias("title"),
    pl.col("duration").n_unique().alias("unique_durations"),
    pl.col("duration").alias("all_durations"),
    pl.col("file_id").alias("all_file_ids"),
    pl.col("file_path").alias("all_file_paths"),
    pl.col("size").alias("all_file_sizes"),
    pl.col("is_primary").alias("all_is_primary")
]).filter(
    pl.col("unique_durations") > 1  # Only keep scenes with different durations
).sort("scene_id")

# Print summary of mismatched files
print("\nScenes with duration mismatches:")
for row in duration_mismatches.iter_rows(named=True):
    print(f"\nScene {row['scene_id']} - {row['title']}")
    
    for i, (duration, file_id, file_path, size, is_primary) in enumerate(zip(
        row["all_durations"], 
        row["all_file_ids"], 
        row["all_file_paths"],
        row["all_file_sizes"],
        row["all_is_primary"]
    )):
        primary_status = " (Primary)" if is_primary else ""
        print(f"  File{primary_status}: {file_path}")
        print(f"    Duration: {duration}s, ID: {file_id}, Size: {size:,} bytes")

# Print summary statistics
print(f"\nTotal scenes with duration mismatches: {len(duration_mismatches)}")




# %%
duration_mismatches_scene_ids = duration_mismatches.select("scene_id").to_series().to_list()
stash_client.update_tags_for_scenes(
    duration_mismatches_scene_ids,
    [duration_mismatch_tag["name"]],
    []
)
