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


# %%
def extract_uuid_from_url(url: str) -> str | None:
    """Extract UUID from Culture Extractor gallery URL."""
    if not url:
        return None

    # Match UUID pattern in Culture Extractor gallery URLs
    match = re.search(
        r"https://culture\.extractor/galleries/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        url,
    )
    if match:
        return match.group(1)
    return None


def extract_uuid_from_stash_id(stash_ids: List[Dict]) -> str | None:
    """Extract UUID from Culture Extractor stash_ids."""
    if not stash_ids:
        return None

    for stash_id in stash_ids:
        if stash_id.get("endpoint") == "https://culture.extractor/graphql":
            return stash_id.get("stash_id")
    return None


# %%
# Get all scenes with their stash_ids
scenes = stash_raw_client.find_scenes(
    fragment="""
    id
    title
    stash_ids {
        endpoint
        stash_id
    }
    galleries {
        id
        title
    }
    """
)

# %%
# Get all galleries with their URLs
galleries = stash_raw_client.find_galleries(
    fragment="""
    id
    title
    urls
    scenes {
        id
        title
    }
    """
)

# %%
# Process scenes to extract Culture Extractor UUIDs
scene_results = []

for scene in scenes:
    scene_id = scene.get("id")
    scene_title = scene.get("title")
    stash_ids = scene.get("stash_ids", [])
    existing_galleries = scene.get("galleries", [])

    ce_uuid = extract_uuid_from_stash_id(stash_ids)

    scene_results.append(
        {
            "scene_id": scene_id,
            "scene_title": scene_title,
            "ce_uuid": ce_uuid,
            "existing_gallery_ids": [g["id"] for g in existing_galleries],
            "existing_gallery_count": len(existing_galleries),
        }
    )

# Create DataFrame for scenes with explicit schema override for ce_uuid column
scenes_df = pl.DataFrame(
    scene_results, schema_overrides={"ce_uuid": pl.Utf8}, infer_schema_length=1000
)

# Filter to only scenes with Culture Extractor UUIDs
scenes_with_uuid_df = scenes_df.filter(pl.col("ce_uuid").is_not_null())

print(f"Total scenes: {len(scenes_df)}")
print(f"Scenes with Culture Extractor UUID: {len(scenes_with_uuid_df)}")

scenes_with_uuid_df

# %%
# Process galleries to extract Culture Extractor UUIDs
gallery_results = []

for gallery in galleries:
    gallery_id = gallery.get("id")
    gallery_title = gallery.get("title")
    urls = gallery.get("urls", [])
    existing_scenes = gallery.get("scenes", [])

    ce_uuid = None
    for url in urls:
        ce_uuid = extract_uuid_from_url(url)
        if ce_uuid:
            break

    gallery_results.append(
        {
            "gallery_id": gallery_id,
            "gallery_title": gallery_title,
            "ce_uuid": ce_uuid,
            "existing_scene_ids": [s["id"] for s in existing_scenes],
            "existing_scene_count": len(existing_scenes),
        }
    )

# Create DataFrame for galleries
galleries_df = pl.DataFrame(gallery_results)

# Filter to only galleries with Culture Extractor UUIDs
galleries_with_uuid_df = galleries_df.filter(pl.col("ce_uuid").is_not_null())

print(f"Total galleries: {len(galleries_df)}")
print(f"Galleries with Culture Extractor UUID: {len(galleries_with_uuid_df)}")

galleries_with_uuid_df

# %%
# Operation step: Join scenes and galleries on Culture Extractor UUID
matches_df = scenes_with_uuid_df.join(
    galleries_with_uuid_df, on="ce_uuid", how="inner", suffix="_gallery"
)

print(f"Found {len(matches_df)} scene-gallery matches based on Culture Extractor UUID")

# Check for scenes/galleries that need to be linked
needs_linking_df = matches_df.filter(
    # Scene doesn't have this gallery linked
    ~pl.col("gallery_id").is_in(pl.col("existing_gallery_ids").explode())
)

print(f"Found {len(needs_linking_df)} scene-gallery pairs that need to be linked")

# Show the matches that need linking
needs_linking_df.select(
    [
        "scene_id",
        "scene_title",
        "gallery_id",
        "gallery_title",
        "ce_uuid",
        "existing_gallery_count",
        "existing_scene_count",
    ]
)

# %%
# Verification step: Review the matches before applying
verification_df = needs_linking_df.select(
    [
        "scene_id",
        "scene_title",
        "gallery_id",
        "gallery_title",
        "ce_uuid",
        "existing_gallery_ids",
        "existing_scene_ids",
    ]
).with_columns(
    [
        # Check if scene already has this gallery
        pl.col("gallery_id")
        .is_in(pl.col("existing_gallery_ids").explode())
        .alias("scene_has_gallery"),
        # Check if gallery already has this scene
        pl.col("scene_id")
        .is_in(pl.col("existing_scene_ids").explode())
        .alias("gallery_has_scene"),
    ]
)

print("Verification of matches to be applied:")
verification_df

# %%
# Apply step: Update scenes and galleries to link them
update_results = []

for row in needs_linking_df.iter_rows(named=True):
    scene_id = row["scene_id"]
    gallery_id = row["gallery_id"]
    scene_title = row["scene_title"]
    gallery_title = row["gallery_title"]
    ce_uuid = row["ce_uuid"]
    existing_gallery_ids = row["existing_gallery_ids"]
    existing_scene_ids = row["existing_scene_ids"]

    # Check if scene needs gallery linked
    scene_needs_gallery = gallery_id not in existing_gallery_ids
    # Check if gallery needs scene linked
    gallery_needs_scene = scene_id not in existing_scene_ids

    try:
        # Update scene to include gallery if needed
        if scene_needs_gallery:
            updated_gallery_ids = list(set(existing_gallery_ids + [gallery_id]))
            scene_result = stash_raw_client.update_scene(
                {"id": scene_id, "gallery_ids": updated_gallery_ids}
            )
            print(
                f"✓ Linked gallery {gallery_id} ({gallery_title}) to scene {scene_id} ({scene_title})"
            )
        else:
            print(f"- Scene {scene_id} already has gallery {gallery_id}")

        update_results.append(
            {
                "scene_id": scene_id,
                "scene_title": scene_title,
                "gallery_id": gallery_id,
                "gallery_title": gallery_title,
                "ce_uuid": ce_uuid,
                "scene_updated": scene_needs_gallery,
                "gallery_updated": gallery_needs_scene,
                "status": "success",
                "error": None,
            }
        )

    except Exception as e:
        update_results.append(
            {
                "scene_id": scene_id,
                "scene_title": scene_title,
                "gallery_id": gallery_id,
                "gallery_title": gallery_title,
                "ce_uuid": ce_uuid,
                "scene_updated": False,
                "gallery_updated": False,
                "status": "error",
                "error": str(e),
            }
        )
        print(f"✗ Failed to link scene {scene_id} and gallery {gallery_id}: {e}")

# %%
# Verification of apply step results
update_results_df = pl.DataFrame(update_results)

print(f"Total scene-gallery pairs processed: {len(update_results_df)}")
print(
    f"Successful updates: {len(update_results_df.filter(pl.col('status') == 'success'))}"
)
print(f"Failed updates: {len(update_results_df.filter(pl.col('status') == 'error'))}")

# Show scene updates
scene_updates = update_results_df.filter(pl.col("scene_updated") == True)
print(f"Scenes updated with new galleries: {len(scene_updates)}")

# Show gallery updates
gallery_updates = update_results_df.filter(pl.col("gallery_updated") == True)
print(f"Galleries updated with new scenes: {len(gallery_updates)}")

# Show any errors
errors_df = update_results_df.filter(pl.col("status") == "error")
if len(errors_df) > 0:
    print("\nErrors encountered:")
    errors_df

# Show successful updates
success_df = update_results_df.filter(pl.col("status") == "success")
success_df
