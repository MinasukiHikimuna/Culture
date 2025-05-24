# %%
import polars as pl
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.getcwd()))

from libraries.client_stashapp import StashAppClient, get_stashapp_client
from libraries.file_renamer import create_filename

load_dotenv()

# Initialize clients and get base data
stash_client = StashAppClient()
stash_raw_client = get_stashapp_client()
use_studio_code_tag = stash_raw_client.find_tag("Filenames: Use Studio Code")
full_movie_tag = stash_raw_client.find_tag("Full Movie")


def create_scene_renames_df(scenes_df):
    return scenes_df.select(
        [
            pl.col("stashapp_id"),
            pl.col("stashapp_title"),
            pl.col("stashapp_studio"),
            pl.col("stashapp_primary_file_path")
            .map_elements(
                lambda directory: os.path.dirname(directory), return_dtype=pl.Utf8
            )
            .alias("directory"),
            pl.col("stashapp_primary_file_basename").alias("old_filename"),
            pl.struct(["*"])
            .map_elements(
                lambda row: create_filename(use_studio_code_tag, row),
                return_dtype=pl.Utf8,
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


def get_renames_for_studio(studio_id):
    """Get all scenes that need renaming for a specific studio"""
    return (
        scene_renames_df.with_columns(
            [pl.col("stashapp_studio").struct.field("id").alias("temp_studio_id")]
        )
        .filter(pl.col("temp_studio_id") == studio_id)
        .drop("temp_studio_id")
    )


def check_duplicates_for_studio(studio_renames_df):
    """Check for duplicate filenames within a studio's rename set"""
    duplicates = (
        studio_renames_df.group_by("new_filename")
        .agg([pl.len().alias("count"), pl.col("old_filename").alias("old_filenames")])
        .filter(pl.col("count") > 1)
    )

    if len(duplicates) > 0:
        print("\nWARNING: Found duplicate new filenames:")
        for row in duplicates.iter_rows(named=True):
            print(f"\nNew filename: {row['new_filename']}")
            print(f"Used {row['count']} times for files:")
            for old_name in row["old_filenames"]:
                print(f"- {old_name}")

    return duplicates


def rename_files_for_studio(studio_renames_df):
    """Execute renames for a specific studio"""
    success_rows = []
    failed_rows = []

    for row in studio_renames_df.iter_rows(named=True):
        old_path = row["old_path"]
        new_path = row["new_path"]
        failure_info = dict(row)

        if new_path is None:
            failure_info["failure_reason"] = "Missing new path"
            failure_info["error_message"] = f"New path not found for {old_path}"
            failed_rows.append(failure_info)
            print(failure_info["error_message"])
            continue

        if os.path.isfile(old_path):
            if not os.path.exists(new_path):
                try:
                    os.rename(old_path, new_path)

                    # Handle AI JSON sidecar file
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
                            failed_rows.append(failure_info)
                            continue

                    print(f"Renamed file:\n{old_path}\n{new_path}\n")
                    success_rows.append(row)
                except Exception as e:
                    failure_info["failure_reason"] = "Rename failed"
                    failure_info["error_message"] = str(e)
                    failed_rows.append(failure_info)
                    print(f"Failed to rename:\n{old_path}\n{new_path}\n{e}")
            else:
                failure_info["failure_reason"] = "File exists"
                failure_info["error_message"] = f"File already exists: {new_path}"
                failed_rows.append(failure_info)
                print(failure_info["error_message"])
        else:
            failure_info["failure_reason"] = "File not found"
            failure_info["error_message"] = f"File not found: {old_path}"
            failed_rows.append(failure_info)
            print(failure_info["error_message"])

    return (
        (
            pl.DataFrame(success_rows)
            if success_rows
            else pl.DataFrame(schema=studio_renames_df.schema)
        ),
        (
            pl.DataFrame(failed_rows)
            if failed_rows
            else pl.DataFrame(
                schema={
                    **studio_renames_df.schema,
                    "failure_reason": pl.Utf8,
                    "error_message": pl.Utf8,
                }
            )
        ),
    )


def trigger_metadata_scan(paths):
    stash_raw_client.metadata_scan(
        paths,
        {
            "scanGenerateClipPreviews": False,
            "scanGenerateCovers": False,
            "scanGenerateImagePreviews": False,
            "scanGeneratePhashes": True,
            "scanGeneratePreviews": False,
            "scanGenerateSprites": False,
            "scanGenerateThumbnails": False,
        },
    )


# %%
# Step 1: Get all scenes and create the initial rename dataframe
# Get all scenes
scenes_df = stash_client.find_scenes(
    {"tags": {"value": [], "modifier": "INCLUDES", "excludes": [full_movie_tag["id"]]}}
)
print(f"Found {len(scenes_df)} total scenes")

# Create initial rename dataframe
scene_renames_df = create_scene_renames_df(scenes_df)

# Filter to only scenes that need renaming
scene_renames_df = scene_renames_df.filter(
    pl.col("old_filename") != pl.col("new_filename")
)
print(f"Found {len(scene_renames_df)} scenes that need renaming")

# Filter out scenes with null studios and warn about them
scenes_no_studio = scene_renames_df.filter(pl.col("stashapp_studio").is_null())
scene_renames_df = scene_renames_df.filter(pl.col("stashapp_studio").is_not_null())

if len(scenes_no_studio) > 0:
    print(f"\nWARNING: Skipping {len(scenes_no_studio)} scenes with no studio assigned")
    print("Example filenames:")
    for filename in scenes_no_studio.select("old_filename").head(5).to_series():
        print(f"- {filename}")
    if len(scenes_no_studio) > 5:
        print(f"... and {len(scenes_no_studio) - 5} more")

# %%
# Step 2: Get summary of studios that need renaming
studios_to_rename = (
    scene_renames_df.group_by("stashapp_studio")
    .agg(
        [
            pl.len().alias("scenes_to_rename"),
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

print(
    f"Found {len(studios_to_rename)} studios with {len(scene_renames_df)} scenes that need renaming:"
)

# Display studios with their rename counts
print("\nStudios and their rename counts:")
print("--------------------------------")
for row in studios_to_rename.iter_rows(named=True):
    parent = (
        f" (part of {row['parent_studio_name']})" if row["parent_studio_name"] else ""
    )
    print(f"{row['studio_name']}{parent}: {row['scenes_to_rename']} scenes to rename")

studios_to_rename

# %%
# Step 3: Example of how to process a single studio:

# Get a studio's info
studio = studios_to_rename.filter(pl.col("studio_name") == "Playboy Plus")
if len(studio) == 0:
    print("Studio not found!")
else:
    studio_id = studio[0]["studio_id"]

    # Get and review the renames for this studio
    studio_renames = get_renames_for_studio(studio_id)
    print(
        f"Found {len(studio_renames)} scenes to rename for {studio[0]['studio_name']}"
    )
    # Check for any duplicate filenames
    duplicates = check_duplicates_for_studio(studio_renames)
    if len(duplicates) != 0:
        print("Duplicates found!")

# %%
filenames = studio_renames.select(
    "stashapp_id", "stashapp_title", "old_filename", "new_filename"
)
filenames


# %%
# Step 4: If everything looks good, execute the renames
if len(duplicates) == 0:
    success_df, failed_df = rename_files_for_studio(studio_renames)
    print(f"Successfully renamed {len(success_df)} files")
    print(f"Failed to rename {len(failed_df)} files")

    # Trigger metadata scan for the affected directories
    if len(success_df) > 0:
        paths = success_df.select(pl.col("directory").unique()).to_series().to_list()
        trigger_metadata_scan(paths)
