# %%
import os
import sys
from pathlib import Path

import polars as pl
from dotenv import load_dotenv


sys.path.append(str(Path.cwd().parent))

from libraries.client_stashapp import StashAppClient, get_stashapp_client


load_dotenv()

stash_client = StashAppClient()
stash_raw_client = get_stashapp_client()

all_stash_studios = stash_client.get_studios()
all_stashapp_performers = stash_client.get_performers()

use_studio_code_tag = stash_raw_client.find_tag("Filenames: Use Studio Code")

# Lookup functions
def get_by_parent_studio(parent_studio_id):
    return all_stash_studios.filter(pl.col("stash_studios_parent_studio_id") == parent_studio_id)

def get_studio(studio_id):
    return all_stash_studios.filter(pl.col("stash_studios_id") == studio_id)

def get_parent_studio_by_name(parent_studio_name):
    return all_stash_studios.filter(pl.col("stash_studios_parent_studio_name") == parent_studio_name)

def get_studio_by_name(studio_name):
    return all_stash_studios.filter(pl.col("stash_studios_name") == studio_name)

def get_performer(performer_id):
    return all_stashapp_performers.filter(pl.col("stashapp_id") == performer_id)

def trigger_metadata_scan(paths):
    stash_raw_client.metadata_scan(paths, {
        "scanGenerateClipPreviews": False,
        "scanGenerateCovers": True,
        "scanGenerateImagePreviews": False,
        "scanGeneratePhashes": True,
        "scanGeneratePreviews": False,
        "scanGenerateSprites": False,
        "scanGenerateThumbnails": False
    })


# %%
# current_studios = get_parent_studio_by_name("Vixen Media Group")
current_studios = get_studio_by_name("Sperm Mania")

# exclusion_id_list = [774, 170]
# current_studios = current_studios.filter(~pl.col("stash_studios_id").is_in(exclusion_id_list))

current_studio_ids = current_studios.select(pl.col("stash_studios_id")).to_series().to_list()

current_studios



# %%
gallery_paths = ["W:\\Culture\\Photos"]
trigger_metadata_scan(gallery_paths)





# %%
galleries_df = stash_client.find_galleries_by_studio(current_studio_ids)
print(len(galleries_df))




# %%
import os

from libraries.file_renamer import create_filename


gallery_renames_df = galleries_df.select([
    pl.col("stashapp_id"),
    pl.col("stashapp_primary_file_path").map_elements(
        lambda directory: str(Path(directory).parent), return_dtype=pl.Utf8,
    ).alias("directory"),
    pl.col("stashapp_primary_file_basename").alias("old_filename"),
    pl.struct(["*"]).map_elements(
        lambda row: create_filename(use_studio_code_tag, row), return_dtype=pl.Utf8,
    ).alias("new_filename"),
    pl.col("stashapp_primary_file_path").alias("old_path"),
]).with_columns([
    pl.col("new_filename").map_elements(
        lambda filename: len(filename) if filename else 0, return_dtype=pl.Int32,
    ).alias("new_filename_length"),
    pl.concat_str([
        pl.col("directory"),
        pl.lit(os.sep),
        pl.col("new_filename")
    ]).alias("new_path")
])

# Reorder the columns
gallery_renames_df = gallery_renames_df.select([
    pl.col("stashapp_id"),
    pl.col("directory"),
    pl.col("old_filename"),
    pl.col("new_filename"),
    pl.col("new_filename_length"),
    pl.col("old_path"),
    pl.col("new_path"),
])

gallery_renames_df = gallery_renames_df.filter(pl.col("old_filename") != pl.col("new_filename"))

# Add check for duplicate new filenames
duplicate_filenames = gallery_renames_df.group_by("new_filename").agg([
    pl.len().alias("count"),
    pl.col("old_filename").alias("old_filenames")
]).filter(pl.col("count") > 1)

if len(duplicate_filenames) > 0:
    print("\nWARNING: Found duplicate new filenames:")
    for row in duplicate_filenames.iter_rows(named=True):
        print(f"\nNew filename: {row['new_filename']}")
        print(f"Used {row['count']} times for files:")
        for old_name in row["old_filenames"]:
            print(f"- {old_name}")

gallery_renames_df




# %%
# Rename the files
import os

import polars as pl


galleries_success_rows = []
galleries_failed_rows = []

for row in gallery_renames_df.iter_rows(named=True):
    old_path = row["old_path"]
    new_path = row["new_path"]
    failure_info = dict(row)  # Create a copy of the row data

    # Check for missing new path
    if new_path is None:
        failure_info["failure_reason"] = "Missing new path"
        failure_info["error_message"] = f"New path not found for {old_path}"
        galleries_failed_rows.append(failure_info)
        print(failure_info["error_message"])
        continue

    # Attempt to move the file if the old path is a file and the new path does not exist
    if os.path.isfile(old_path):
        if not os.path.exists(new_path):
            try:
                os.rename(old_path, new_path)
                print(f"Rename file:\n{old_path}\n{new_path}\n")
                galleries_success_rows.append(row)
            except Exception as e:
                failure_info["failure_reason"] = "Rename failed"
                failure_info["error_message"] = str(e)
                galleries_failed_rows.append(failure_info)
                print(f"Failed to rename:\n{old_path}\n{new_path}\n{e}")
        else:
            failure_info["failure_reason"] = "File exists"
            failure_info["error_message"] = f"A file already exists in the new path: {new_path}"
            galleries_failed_rows.append(failure_info)
            print(failure_info["error_message"])
    else:
        failure_info["failure_reason"] = "File not found"
        failure_info["error_message"] = f"File does not exist: {old_path}"
        galleries_failed_rows.append(failure_info)
        print(failure_info["error_message"])

galleries_success_df = pl.DataFrame(galleries_success_rows) if galleries_success_rows else pl.DataFrame(schema=gallery_renames_df.schema)
galleries_failed_df = (
    pl.DataFrame(galleries_failed_rows) if galleries_failed_rows
    else pl.DataFrame(schema={**gallery_renames_df.schema, "failure_reason": pl.Utf8, "error_message": pl.Utf8})
)

paths = galleries_success_df.select(pl.col("directory").unique()).to_series().to_list()
trigger_metadata_scan(paths)

print(f"Rename succeeded for {len(galleries_success_df)}/{len(gallery_renames_df)} galleries, failed for {len(galleries_failed_df)}.")



# %%
paths

# %%
trigger_metadata_scan(paths)

# %%
galleries_success_df

# %%
galleries_failed_df


