# %%
import polars as pl
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.getcwd()))

from libraries.client_stashapp import StashAppClient, get_stashapp_client

load_dotenv()

stash_client = StashAppClient()
stash_raw_client = get_stashapp_client()

all_stash_studios = stash_client.get_studios()
all_stashapp_performers = stash_client.get_performers()

use_studio_code_tag = stash_raw_client.find_tag("Filenames: Use Studio Code")


# Lookup functions
def get_by_parent_studio(parent_studio_id):
    return all_stash_studios.filter(
        pl.col("stash_studios_parent_studio_id") == parent_studio_id
    )


def get_studio(studio_id):
    return all_stash_studios.filter(pl.col("stash_studios_id") == studio_id)


def get_parent_studio_by_name(parent_studio_name):
    return all_stash_studios.filter(
        pl.col("stash_studios_parent_studio_name") == parent_studio_name
    )


def get_studio_by_name(studio_name):
    return all_stash_studios.filter(pl.col("stash_studios_name") == studio_name)


def get_performer(performer_id):
    return all_stashapp_performers.filter(pl.col("stashapp_id") == performer_id)


def trigger_metadata_scan(paths):
    stash_raw_client.metadata_scan(
        paths,
        {
            "scanGenerateClipPreviews": False,
            "scanGenerateCovers": True,
            "scanGenerateImagePreviews": False,
            "scanGeneratePhashes": True,
            "scanGeneratePreviews": False,
            "scanGenerateSprites": False,
            "scanGenerateThumbnails": False,
        },
    )


# %%
# current_studios = get_parent_studio_by_name("Vixen Media Group")
current_studios = get_studio_by_name("Karups Older Women")

# exclusion_id_list = [774, 170]
# current_studios = current_studios.filter(~pl.col("stash_studios_id").is_in(exclusion_id_list))

current_studio_ids = (
    current_studios.select(pl.col("stash_studios_id")).to_series().to_list()
)

current_studios


# %%
videos_paths = [
    "W:\\Culture\\Videos",
    "X:\\Culture\\Videos",
    "Y:\\Culture\\Videos",
    "Z:\\Culture\\Videos",
]
trigger_metadata_scan(videos_paths)


# %%
# scenes_df = stash_client.find_scenes_by_studio(current_studio_ids)
scenes_df = stash_client.find_scenes({})
print(len(scenes_df))


# %%
import os
from libraries.file_renamer import create_filename
import traceback


def safe_function(use_studio_code_tag, row):
    try:
        # Replace 'your_function' with the actual function you're applying
        return create_filename(use_studio_code_tag, row)
    except Exception as e:
        # Log the error with row details
        print(f"Error processing row {row}: {e}")
        traceback.print_exc()
        return None  # or an appropriate default value


scene_renames_df = scenes_df.select(
    [
        pl.col("stashapp_id"),
        pl.col("stashapp_studio"),
        pl.col("stashapp_primary_file_path")
        .map_elements(
            lambda directory: os.path.dirname(directory), return_dtype=pl.Utf8
        )
        .alias("directory"),
        pl.col("stashapp_primary_file_basename").alias("old_filename"),
        pl.struct(["*"])
        .map_elements(
            lambda row: safe_function(use_studio_code_tag, row), return_dtype=pl.Utf8
        )
        .alias("new_filename"),
        pl.col("stashapp_primary_file_path").alias("old_path"),
    ]
).with_columns(
    [
        pl.col("new_filename")
        .map_elements(
            lambda filename: len(filename) if filename else 0, return_dtype=pl.Int32
        )
        .alias("new_filename_length"),
        pl.concat_str(
            [pl.col("directory"), pl.lit(os.sep), pl.col("new_filename")]
        ).alias("new_path"),
    ]
)

scene_renames_df = scene_renames_df.select(
    [
        pl.col("stashapp_id"),
        pl.col("stashapp_studio"),
        pl.col("directory"),
        pl.col("old_filename"),
        pl.col("new_filename"),
        pl.col("new_filename_length"),
        pl.col("old_path"),
        pl.col("new_path"),
    ]
)

scene_renames_df = scene_renames_df.filter(
    pl.col("old_filename") != pl.col("new_filename")
)

# Add check for duplicate new filenames
duplicate_filenames = (
    scene_renames_df.group_by("new_filename")
    .agg([pl.len().alias("count"), pl.col("old_filename").alias("old_filenames")])
    .filter(pl.col("count") > 1)
)

if len(duplicate_filenames) > 0:
    print("\nWARNING: Found duplicate new filenames:")
    for row in duplicate_filenames.iter_rows(named=True):
        print(f"\nNew filename: {row['new_filename']}")
        print(f"Used {row['count']} times for files:")
        for old_name in row["old_filenames"]:
            print(f"- {old_name}")

scene_renames_df


# %%
# Get summary of studios with scenes to rename
studios_to_rename = (
    scene_renames_df.group_by("stashapp_studio")
    .agg(
        [
            pl.count().alias("scenes_to_rename"),
            pl.col("old_filename").alias("example_filenames"),
        ]
    )
    .sort("scenes_to_rename", descending=True)
    .with_columns(
        [
            pl.col("stashapp_studio").struct.field("id").alias("studio_id"),
            pl.col("stashapp_studio").struct.field("name").alias("studio_name"),
            pl.col("stashapp_studio").struct.field("url").alias("studio_url"),
            pl.col("stashapp_studio")
            .struct.field("parent_studio")
            .struct.field("id")
            .alias("parent_studio_id"),
            pl.col("stashapp_studio")
            .struct.field("parent_studio")
            .struct.field("name")
            .alias("parent_studio_name"),
            pl.col("stashapp_studio")
            .struct.field("parent_studio")
            .struct.field("url")
            .alias("parent_studio_url"),
        ]
    )
    .drop("stashapp_studio")
)

print(f"Found {len(studios_to_rename)} studios with scenes that need renaming:")
studios_to_rename


# %%
studios_to_rename.schema


# %%
# Rename the files
import os
import polars as pl

scenes_success_rows = []
scenes_failed_rows = []

for row in scene_renames_df.iter_rows(named=True):
    old_path = row["old_path"]
    new_path = row["new_path"]
    failure_info = dict(row)  # Create a copy of the row data

    # Check for missing new path
    if new_path is None:
        failure_info["failure_reason"] = "Missing new path"
        failure_info["error_message"] = f"New path not found for {old_path}"
        scenes_failed_rows.append(failure_info)
        print(failure_info["error_message"])
        continue

    # Attempt to move the file if the old path is a file and the new path does not exist
    if os.path.isfile(old_path):
        if not os.path.exists(new_path):
            try:
                os.rename(old_path, new_path)

                # Check for and rename AI JSON sidecar file if it exists
                ai_json_path = f"{old_path}.AI.json"
                if os.path.isfile(ai_json_path):
                    new_ai_json_path = f"{new_path}.AI.json"
                    try:
                        os.rename(ai_json_path, new_ai_json_path)
                        print(
                            f"Renamed AI JSON sidecar file:\n{ai_json_path}\n{new_ai_json_path}"
                        )
                    except Exception as e:
                        failure_info["failure_reason"] = "Sidecar rename failed"
                        failure_info["error_message"] = str(e)
                        scenes_failed_rows.append(failure_info)
                        continue
                print(f"Rename file:\n{old_path}\n{new_path}\n")
                scenes_success_rows.append(row)
            except Exception as e:
                failure_info["failure_reason"] = "Rename failed"
                failure_info["error_message"] = str(e)
                scenes_failed_rows.append(failure_info)
                print(f"Failed to rename:\n{old_path}\n{new_path}\n{e}")
        else:
            failure_info["failure_reason"] = "File exists"
            failure_info["error_message"] = (
                f"A file already exists in the new path: {new_path}"
            )
            scenes_failed_rows.append(failure_info)
            print(failure_info["error_message"])
    else:
        failure_info["failure_reason"] = "File not found"
        failure_info["error_message"] = f"File does not exist: {old_path}"
        scenes_failed_rows.append(failure_info)
        print(failure_info["error_message"])

scenes_success_df = (
    pl.DataFrame(scenes_success_rows)
    if scenes_success_rows
    else pl.DataFrame(schema=scene_renames_df.schema)
)
scenes_failed_df = (
    pl.DataFrame(scenes_failed_rows)
    if scenes_failed_rows
    else pl.DataFrame(
        schema={
            **scene_renames_df.schema,
            "failure_reason": pl.Utf8,
            "error_message": pl.Utf8,
        }
    )
)

paths = scenes_success_df.select(pl.col("directory").unique()).to_series().to_list()
trigger_metadata_scan(paths)

print(
    f"Rename succeeded for {len(scenes_success_df)}/{len(scene_renames_df)} scenes, failed for {len(scenes_failed_df)}."
)


# %%
paths


# %%
trigger_metadata_scan(paths)


# %%
scenes_success_df


# %%
scenes_failed_df
