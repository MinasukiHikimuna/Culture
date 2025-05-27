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

# Define Culture Extractor URL pattern
CULTURE_EXTRACTOR_URL_PATTERN = "https://culture.extractor/galleries/"


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


def get_existing_ce_url(existing_urls: List[str], ce_uuid: str) -> str | None:
    """Get existing Culture Extractor URL if it exists for the given UUID."""
    expected_url = f"{CULTURE_EXTRACTOR_URL_PATTERN}{ce_uuid}"
    return expected_url if expected_url in existing_urls else None


# %%
# Get all galleries with their files and existing URLs
galleries = stash_raw_client.find_galleries(
    fragment="""
    id
    title
    urls
    files {
        id
        basename
        path
    }
    """
)

# Process galleries and files to extract UUIDs from filenames
results = []

for gallery in galleries:
    gallery_id = gallery.get("id")
    gallery_title = gallery.get("title")
    existing_urls = gallery.get("urls", [])
    files = gallery.get("files", [])
    for file in files:
        file_basename = file.get("basename")
        file_path = file.get("path")
        # Only consider files in the specified PATHS
        if not any(str(file_path).startswith(p) for p in PATHS):
            continue
        ce_uuid = extract_uuid_from_filename(file_basename)
        results.append(
            {
                "gallery_id": gallery_id,
                "gallery_title": gallery_title,
                "file_basename": file_basename,
                "file_path": file_path,
                "ce_uuid": ce_uuid,
                "existing_urls": existing_urls,
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
# Filter out galleries that already have the matching Culture Extractor URL
galleries_to_update = []
galleries_already_set = []

for row in files_with_uuid_df.iter_rows(named=True):
    existing_urls = row["existing_urls"] or []
    existing_ce_url = get_existing_ce_url(existing_urls, row["ce_uuid"])

    # Check if the Culture Extractor URL already exists
    if existing_ce_url:
        galleries_already_set.append(row)
    else:
        galleries_to_update.append(row)

# Create DataFrames for verification
galleries_to_update_df = (
    pl.DataFrame(galleries_to_update) if galleries_to_update else pl.DataFrame()
)
galleries_already_set_df = (
    pl.DataFrame(galleries_already_set) if galleries_already_set else pl.DataFrame()
)

print(f"Total galleries with UUIDs found: {len(files_with_uuid_df)}")
print(f"Galleries that need updating: {len(galleries_to_update_df)}")
print(f"Galleries already set (skipped): {len(galleries_already_set_df)}")

if len(galleries_already_set_df) > 0:
    print("\nGalleries already set with matching Culture Extractor URL:")
    print(
        galleries_already_set_df.select(
            ["gallery_id", "gallery_title", "file_basename", "ce_uuid"]
        )
    )

print("\nGalleries to be updated:")
galleries_to_update_df

# %%
# Apply step: Update galleries with extracted UUIDs as URLs
update_results = []

for row in galleries_to_update_df.iter_rows(named=True):
    gallery_id = row["gallery_id"]
    ce_uuid = row["ce_uuid"]
    gallery_title = row["gallery_title"]
    file_basename = row["file_basename"]
    existing_urls = row["existing_urls"] or []

    # Create the Culture Extractor URL
    ce_url = f"{CULTURE_EXTRACTOR_URL_PATTERN}{ce_uuid}"

    try:
        # Add the new URL to existing URLs
        updated_urls = existing_urls + [ce_url]

        # Update the gallery with the new URL list
        result = stash_raw_client.update_gallery(
            {
                "id": gallery_id,
                "urls": updated_urls,
            }
        )

        update_results.append(
            {
                "gallery_id": gallery_id,
                "gallery_title": gallery_title,
                "file_basename": file_basename,
                "ce_uuid": ce_uuid,
                "status": "success",
                "error": None,
            }
        )

        print(f"✓ Updated gallery {gallery_id} ({gallery_title}) with URL {ce_url}")

    except Exception as e:
        update_results.append(
            {
                "gallery_id": gallery_id,
                "gallery_title": gallery_title,
                "file_basename": file_basename,
                "ce_uuid": ce_uuid,
                "status": "error",
                "error": str(e),
            }
        )

        print(f"✗ Failed to update gallery {gallery_id} ({gallery_title}): {e}")

# %%
# Verification of apply step results
if update_results:
    update_results_df = pl.DataFrame(update_results)
    print(f"Total galleries processed: {len(update_results_df)}")
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
    print("No galleries needed updating.")
