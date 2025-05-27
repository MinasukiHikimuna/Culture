# %%
import os
import polars as pl
import re
from typing import List, Dict, Any
import uuid
from dotenv import load_dotenv
import sys

load_dotenv()

sys.path.append(os.path.dirname(os.getcwd()))


# Import StashApp client
from libraries.client_stashapp import StashAppClient, get_stashapp_client


# Initialize clients
stash_client = StashAppClient()
stash_raw_client = get_stashapp_client()

# Define paths to scan
PATHS = [
    r"F:\Culture\Staging",
    r"W:\Culture\Videos",
    r"X:\Culture\Videos",
    r"Y:\Culture\Videos",
    r"Z:\Culture\Videos",
]

# Define Culture Extractor endpoint
CULTURE_EXTRACTOR_ENDPOINT = "https://culture.extractor/graphql"


def is_valid_uuid(uuid_str: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid_obj = uuid.UUID(uuid_str)
        return str(uuid_obj) == uuid_str
    except ValueError:
        return False


def extract_uuid_from_filename(filename: str) -> str | None:
    """Extract UUID from filename if it exists."""
    # Match UUID pattern at the end of filename before extension
    match = re.search(
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.", filename
    )
    if match and is_valid_uuid(match.group(1)):
        return match.group(1)
    return None


def get_existing_ce_stash_id(existing_stash_ids: List[Dict]) -> str | None:
    """Get existing Culture Extractor stash_id if it exists."""
    for sid in existing_stash_ids:
        if sid.get("endpoint") == CULTURE_EXTRACTOR_ENDPOINT:
            return sid.get("stash_id")
    return None


def merge_stash_ids(
    existing_stash_ids: List[Dict], new_endpoint: str, new_stash_id: str
) -> List[Dict]:
    """Merge new stash_id with existing ones, preserving other endpoints."""
    # Start with existing stash_ids, filtering out any existing culture.extractor entries
    merged = [sid for sid in existing_stash_ids if sid.get("endpoint") != new_endpoint]

    # Add the new culture.extractor stash_id
    merged.append({"endpoint": new_endpoint, "stash_id": new_stash_id})

    return merged


# %%
# Get all scenes with their files and existing stash_ids
scenes = stash_raw_client.find_scenes(
    fragment="""
    id
    title
    stash_ids {
        endpoint
        stash_id
    }
    files {
        id
        basename
        path
    }
    """
)

# Process scenes and files to extract UUIDs from filenames
results = []

for scene in scenes:
    scene_id = scene.get("id")
    scene_title = scene.get("title")
    existing_stash_ids = scene.get("stash_ids", [])
    files = scene.get("files", [])
    for file in files:
        file_basename = file.get("basename")
        file_path = file.get("path")
        # Only consider files in the specified PATHS
        if not any(str(file_path).startswith(p) for p in PATHS):
            continue
        ce_uuid = extract_uuid_from_filename(file_basename)
        results.append(
            {
                "scene_id": scene_id,
                "scene_title": scene_title,
                "file_basename": file_basename,
                "file_path": file_path,
                "ce_uuid": ce_uuid,
                "existing_stash_ids": existing_stash_ids,
            }
        )

# Ensure all dicts have the same keys
all_keys = {k for d in results for k in d.keys()}
for d in results:
    for k in all_keys:
        if k not in d:
            d[k] = None

# Ensure all ce_uuid values are str or None
for d in results:
    if d["ce_uuid"] is not None:
        d["ce_uuid"] = str(d["ce_uuid"])
    else:
        d["ce_uuid"] = None

# Build DataFrame with explicit schema override for ce_uuid column
files_df = pl.DataFrame(
    results, schema_overrides={"ce_uuid": pl.Utf8}, infer_schema_length=1000
)

# Filter to only files with a found UUID
files_with_uuid_df = files_df.filter(pl.col("ce_uuid").is_not_null())

# %%
# Filter out scenes that already have the matching Culture Extractor stash ID
scenes_to_update = []
scenes_already_set = []

for row in files_with_uuid_df.iter_rows(named=True):
    existing_stash_ids = row["existing_stash_ids"] or []
    existing_ce_stash_id = get_existing_ce_stash_id(existing_stash_ids)

    # Check if the same UUID is already set
    if existing_ce_stash_id == row["ce_uuid"]:
        scenes_already_set.append(row)
    else:
        scenes_to_update.append(row)

# Create DataFrames for verification
scenes_to_update_df = (
    pl.DataFrame(scenes_to_update) if scenes_to_update else pl.DataFrame()
)
scenes_already_set_df = (
    pl.DataFrame(scenes_already_set) if scenes_already_set else pl.DataFrame()
)

print(f"Total scenes with UUIDs found: {len(files_with_uuid_df)}")
print(f"Scenes that need updating: {len(scenes_to_update_df)}")
print(f"Scenes already set (skipped): {len(scenes_already_set_df)}")

if len(scenes_already_set_df) > 0:
    print("\nScenes already set with matching Culture Extractor stash ID:")
    print(
        scenes_already_set_df.select(
            ["scene_id", "scene_title", "file_basename", "ce_uuid"]
        )
    )

print("\nScenes to be updated:")
scenes_to_update_df

# %%
# Apply step: Update scenes with extracted UUIDs as stash_ids (preserving existing stash_ids)
update_results = []

for row in scenes_to_update_df.iter_rows(named=True):
    scene_id = row["scene_id"]
    ce_uuid = row["ce_uuid"]
    scene_title = row["scene_title"]
    file_basename = row["file_basename"]
    existing_stash_ids = row["existing_stash_ids"] or []

    try:
        # Merge stash_ids preserving existing ones
        merged_stash_ids = merge_stash_ids(
            existing_stash_ids, CULTURE_EXTRACTOR_ENDPOINT, ce_uuid
        )

        # Update the scene with merged stash_ids
        result = stash_raw_client.update_scene(
            {
                "id": scene_id,
                "stash_ids": merged_stash_ids,
            }
        )

        update_results.append(
            {
                "scene_id": scene_id,
                "scene_title": scene_title,
                "file_basename": file_basename,
                "ce_uuid": ce_uuid,
                "status": "success",
                "error": None,
            }
        )

        print(
            f"✓ Updated scene {scene_id} ({scene_title}) with UUID {ce_uuid} (preserved {len(existing_stash_ids)} existing stash_ids)"
        )

    except Exception as e:
        update_results.append(
            {
                "scene_id": scene_id,
                "scene_title": scene_title,
                "file_basename": file_basename,
                "ce_uuid": ce_uuid,
                "status": "error",
                "error": str(e),
            }
        )

        print(f"✗ Failed to update scene {scene_id} ({scene_title}): {e}")

# %%
# Verification of apply step results
if update_results:
    update_results_df = pl.DataFrame(update_results)
    print(f"Total scenes processed: {len(update_results_df)}")
    print(
        f"Successful updates: {len(update_results_df.filter(pl.col('status') == 'success'))}"
    )
    print(
        f"Failed updates: {len(update_results_df.filter(pl.col('status') == 'error'))}"
    )

    # Show any errors
    errors_df = update_results_df.filter(pl.col("status") == "error")
    if len(errors_df) > 0:
        print("\nErrors encountered:")
        errors_df

    # Show successful updates
    success_df = update_results_df.filter(pl.col("status") == "success")
    success_df
else:
    print("No scenes needed updating.")
