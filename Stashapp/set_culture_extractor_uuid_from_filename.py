# %%
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
import re
from libraries.client_stashapp import get_stashapp_client, StashAppClient

# %%
def extract_guidv7(filename: str) -> str:
    """Extract GUIDv7 from filename if present"""
    # Pattern to match GUIDv7 at the end of filename before extension
    pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.'
    match = re.search(pattern, filename.lower())
    return match.group(1) if match else None

# %%
# Initialize stash clients
stash = get_stashapp_client()

# %%
# Define fragment to only get required fields
fragment = """
    id
    title
    files {
        basename
    }
"""

# %%
# Get scenes that don't have culture.extractor ID
filter_dict = {
    "stash_id_endpoint": {
        "endpoint": "https://culture.extractor/graphql",
        "modifier": "IS_NULL",
    }
}

# %%
# Get filtered scenes with minimal data
scenes = stash.find_scenes(filter_dict, fragment=fragment)
print(f"Found {len(scenes)} scenes without culture.extractor ID")

# %%
# Process scenes and extract GUIDv7
processed_scenes = []
for scene in scenes:
    # Get the first file's basename that has a GUIDv7
    guidv7 = None
    filename = None
    for file in scene.get('files', []):
        basename = file.get('basename', '')
        extracted_guidv7 = extract_guidv7(basename)
        if extracted_guidv7:
            guidv7 = extracted_guidv7
            filename = basename
            break
            
    if guidv7:
        processed_scenes.append({
            'scene_id': scene['id'],
            'title': scene['title'],
            'filename': filename,
            'guidv7': guidv7
        })

# %%
# Convert to DataFrame
result = pl.DataFrame(processed_scenes)
result



# %%
updated_count = 0
for row in result.iter_rows(named=True):
    scene_id = row['scene_id']
    guidv7 = row['guidv7']
    
    # Add the stash ID to the scene
    try:
        existing_stash_ids = stash.find_scene(scene_id)['stash_ids']
        updated_stash_ids = existing_stash_ids + [
            {
                "endpoint": "https://culture.extractor/graphql",
                "stash_id": guidv7
            }
        ]
        stash.update_scene(
            {
                "id": scene_id,
                "stash_ids": updated_stash_ids
            }
        )
        updated_count += 1
        print(f"Updated scene {scene_id} with culture.extractor ID {guidv7}")
    except Exception as e:
        print(f"Error updating scene {scene_id}: {str(e)}")

print(f"\nUpdated {updated_count} scenes with culture.extractor IDs")
