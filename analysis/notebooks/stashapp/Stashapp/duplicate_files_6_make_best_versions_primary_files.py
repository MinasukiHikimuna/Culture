# %%
import os
import sys

import polars as pl


# Fix the import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libraries.client_stashapp import StashAppClient, get_stashapp_client


stash = get_stashapp_client()
stash_client = StashAppClient()

# %%
oshash_and_duration_match_tag = stash.find_tag({ "name": "Duplicate: OSHASH And Duration Match" })
duration_match_tag = stash.find_tag({ "name": "Duplicate: Duration Match" })
scenes_with_multiple_versions = stash.find_tag({ "name": "Scene: Multiple Versions" })
duration_mismatch_tag = stash.find_tag({ "name": "Duplicate: Duration Mismatch" })

# %% [markdown]
# # Making higher quality versions the primary file

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
}, fragment=(
    "id title date studio { name } files { id duration path width height size"
    " fingerprints { type value } format video_codec audio_codec }"
))

# Create Polars DataFrame with strict=False to handle mixed numeric types
scenes_with_dupes_df = pl.DataFrame(scenes_with_dupes, strict=False)

# Function to select best quality file from a list of files
def select_best_quality_file(files):
    # Convert Polars Series to list if needed
    if isinstance(files, pl.Series):
        files = files.to_list()

    if not isinstance(files, list) or not files:
        return {"best_file": None, "primary_file": None}

    # Convert each file to a dictionary with relevant fields
    files_data = []
    for file in files:
        try:
            file_dict = {
                "id": file["id"],
                "path": file["path"],
                "width": file["width"],
                "height": file["height"],
                "size": file["size"],
                "resolution": file["width"] * file["height"] if file["width"] and file["height"] else 0,
                "duration": file["duration"],
                "format": file["format"],
                "video_codec": file["video_codec"],
                "audio_codec": file["audio_codec"],
                "fingerprints": file["fingerprints"],
                "is_primary": files.index(file) == 0  # Mark if this is the primary file
            }
            files_data.append(file_dict)
        except Exception as e:
            continue

    if not files_data:
        return {"best_file": None, "primary_file": None}

    # Sort by resolution (primary) and size (secondary)
    sorted_files = sorted(files_data, key=lambda x: (x["resolution"], x["size"]), reverse=True)

    best_file = sorted_files[0]
    primary_file = next(f for f in files_data if f["is_primary"])

    # Only return different files if the best file is better than the primary
    if best_file["id"] != primary_file["id"] and (
        best_file["resolution"] > primary_file["resolution"] or
        (best_file["resolution"] == primary_file["resolution"] and best_file["size"] > primary_file["size"])
    ):
        return {
            "best_file": best_file,
            "primary_file": primary_file
        }
    return {"best_file": None, "primary_file": None}

# Add best_file column and filter for scenes where best file differs from primary
scenes_with_dupes_df = scenes_with_dupes_df.with_columns(
    pl.col("files").map_elements(select_best_quality_file, return_dtype=pl.Struct).alias("file_comparison")
)

# Filter for scenes where we have a better quality file
scenes_with_potentially_better_files_df = scenes_with_dupes_df.filter(
    pl.col("file_comparison").map_elements(lambda x: x["best_file"] is not None, return_dtype=pl.Boolean)
)

# Print results
results_list = []
if len(scenes_with_potentially_better_files_df) > 0:
    print(f"\nFound {len(scenes_with_potentially_better_files_df)} scenes where primary file is not the best quality.")
    print("\nScenes that need to be updated:")

    for row in scenes_with_potentially_better_files_df.to_dicts():
        if row["file_comparison"] and row["file_comparison"]["best_file"]:
            best = row["file_comparison"]["best_file"]
            primary = row["file_comparison"]["primary_file"]
            resolution_improvement = ((best["resolution"] - primary["resolution"])/primary["resolution"]*100)
            size_improvement = ((best["size"] - primary["size"])/primary["size"]*100)

            result_dict = {
                "id": row["id"],
                "title": row["title"],
                "studio": row["studio"]["name"] if row["studio"] else None,
                "date": row["date"],
                "current_resolution": f"{primary['width']}x{primary['height']}",
                "current_size": primary["size"],
                "better_resolution": f"{best['width']}x{best['height']}",
                "better_size": best["size"],
                "resolution_improvement": resolution_improvement,
                "size_improvement": size_improvement,
                "current_file_path": primary["path"],
                "better_file_path": best["path"],
                "current_file_id": primary["id"],
                "better_file_id": best["id"]
            }
            results_list.append(result_dict)

# Create results DataFrame
results_df = pl.DataFrame(results_list)

if len(results_df) > 0:
    print(f"\nFound {len(scenes_with_dupes_df)} total scenes with multiple files")
    print(f"Found {len(results_df)} scenes with better quality files")

    # Sort by total improvement (resolution + size)
    results_df = results_df.with_columns(
        (pl.col("resolution_improvement") + pl.col("size_improvement")).alias("total_improvement")
    ).sort("total_improvement", descending=True)

    # Display summary statistics
    print("\nSummary Statistics:")
    print(f"Average Resolution Improvement: {results_df['resolution_improvement'].mean():.1f}%")
    print(f"Average Size Improvement: {results_df['size_improvement'].mean():.1f}%")
    print(f"Median Resolution Improvement: {results_df['resolution_improvement'].median():.1f}%")
    print(f"Median Size Improvement: {results_df['size_improvement'].median():.1f}%")

    # Save results to CSV
    results_df.write_csv("quality_improvement_results.csv")
    print("\nDetailed results have been saved to 'quality_improvement_results.csv'")
else:
    print("\nNo scenes found with significant quality improvements.")



# %%
for row in results_df.to_dicts():
    stash.update_scene({
        "id": row["id"],
        "primary_file_id": row["better_file_id"]
    })

