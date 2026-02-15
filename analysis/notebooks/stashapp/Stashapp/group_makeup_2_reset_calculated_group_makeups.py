# %% Initialize the clients
import sys
from pathlib import Path

import polars as pl


sys.path.append(str(Path.cwd().parent))

from libraries.client_stashapp import StashAppClient, get_stashapp_client


stash = get_stashapp_client()
stash_client = StashAppClient()





# %% Get the tags
group_makeup_verified_tag_id = stash.find_tag("Group Makeup Verified")["id"]
group_makeup_calculated_parent_tag = stash.find_tag("Group Makeup Calculated", fragment="id name children { id name }")
group_makeup_calculated_tag_ids = [tag["id"] for tag in group_makeup_calculated_parent_tag["children"]]





# %% Reset calculated group makeup tags
all_scenes = pl.DataFrame(stash.find_scenes(fragment="id title date performers { id name gender } tags { id name }"))
for scene in all_scenes.iter_rows(named=True):
    existing_tag_ids = [tag["id"] for tag in scene["tags"]]
    cleaned_tag_ids = [tag_id for tag_id in existing_tag_ids if tag_id not in group_makeup_calculated_tag_ids]
    stash.update_scene({
        "id": scene["id"],
        "tag_ids": cleaned_tag_ids
    })