# %%
import os
import sys

import dotenv
import polars as pl


sys.path.append(os.path.dirname(os.path.abspath("")))

from libraries.client_stashapp import get_stashapp_client
from libraries.StashDbClient import StashDbClient


# Format a StashDB ID for use as an aliasin Stash
stashdb_id_alias_prefix = "StashDB ID: "
def format_stashdb_id(id):
    return f"{stashdb_id_alias_prefix}{id}"

def contains_cjk(text):
    """Check if text contains CJK (Chinese, Japanese, Korean) characters."""
    # Unicode ranges for CJK characters
    cjk_ranges = [
        (0x4E00, 0x9FFF),   # CJK Unified Ideographs
        (0x3040, 0x309F),   # Hiragana
        (0x30A0, 0x30FF),   # Katakana
        (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
        (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
        (0xAC00, 0xD7AF),   # Korean Hangul Syllables
    ]

    return any(any(ord(char) >= start and ord(char) <= end
               for start, end in cjk_ranges)
               for char in text)


dotenv.load_dotenv()

stash = get_stashapp_client()

stashbox_client = StashDbClient(
    os.getenv("STASHDB_ENDPOINT"),
    os.getenv("STASHDB_API_KEY"),
)





# %%
to_be_merged_tag = stash.find_tag({ "name": "Standing Double Penetration" })
target_tag = stash.find_tag({ "name": "Standing Sex (DP)" })

print(to_be_merged_tag)
print("=>")
print(target_tag)
print()

tag_filter = {"tags": {"value": [to_be_merged_tag["id"]], "modifier": "INCLUDES"}}
scenes = stash.find_scenes(tag_filter, fragment="id title tags { id name }")
galleries = stash.find_galleries(tag_filter, fragment="id title tags { id name }")
images = stash.find_images(tag_filter, fragment="id title tags { id name }")
markers = stash.find_scene_markers(
    tag_filter,
    fragment="id scene { id title } title primary_tag { id name } tags { id name }",
)

print(f"Scenes: {len(scenes)}")
print(f"Markers: {len(markers)}")
print(f"Galleries: {len(galleries)}")
print(f"Images: {len(images)}")





# %%
# Update scenes
for scene in scenes:
    scene_id = scene["id"]
    current_scene_tag_ids = [tag["id"] for tag in scene["tags"]]
    update_scene_tag_ids = [tag_id for tag_id in current_scene_tag_ids if tag_id != to_be_merged_tag["id"]] + [target_tag["id"]]
    stash.update_scene({ "id": scene_id, "tag_ids": update_scene_tag_ids })
    print(f"Updated scene {scene_id} with tag {target_tag['name']}")





# %%
# Update markers
for marker in markers:
    marker_id = marker["id"]
    current_marker_tag_ids = [tag["id"] for tag in marker["tags"]]
    update_marker_tag_ids = [tag_id for tag_id in current_marker_tag_ids if tag_id != to_be_merged_tag["id"]] + [target_tag["id"]]
    stash.update_scene_marker({ "id": marker_id, "title": target_tag["name"], "primary_tag_id": target_tag["id"] })
    print(f"Updated marker {marker_id} with tag {target_tag['name']} for scene {marker['scene']['title']} (ID: {marker['scene']['id']})")





# %%
# Update galleries
for gallery in galleries:
    gallery_id = gallery["id"]
    current_gallery_tag_ids = [tag["id"] for tag in gallery["tags"]]
    update_gallery_tag_ids = [tag_id for tag_id in current_gallery_tag_ids if tag_id != to_be_merged_tag["id"]] + [target_tag["id"]]
    stash.update_gallery({ "id": gallery_id, "tag_ids": update_gallery_tag_ids })
    print(f"Updated gallery {gallery_id} with tag {target_tag['name']}")





# %%
# Update images
for image in images:
    image_id = image["id"]
    current_image_tag_ids = [tag["id"] for tag in image["tags"]]
    update_image_tag_ids = [tag_id for tag_id in current_image_tag_ids if tag_id != to_be_merged_tag["id"]] + [target_tag["id"]]
    stash.update_image({ "id": image_id, "tag_ids": update_image_tag_ids })
    print(f"Updated image {image_id} with tag {target_tag['name']}")





# %%
stash.destroy_tag(to_be_merged_tag["id"])
