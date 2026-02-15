# %% [markdown]
# # Duplicate Links
# 
# This notebook removes duplicate links from scenes and galleries.

# %%
import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath("")))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

stash = get_stashapp_client()
stash_client = StashAppClient()



# %%
def unique_stable(lst):
    return list(dict.fromkeys(lst))



# %% [markdown]
# # Scenes

# %%
scenes_with_links = pl.DataFrame(stash.find_scenes({
  "url": {
    "value": "",
    "modifier": "NOT_NULL"
  }
}, fragment="id title urls"))

scenes_with_duplicate_links = scenes_with_links.filter(
    pl.col("urls").list.len() != pl.col("urls").list.unique().list.len()
).with_columns(
    pl.col("urls").map_elements(unique_stable, return_dtype=pl.List(pl.Utf8)).alias("unique_urls")
)
scenes_with_duplicate_links




# %%
for scene in scenes_with_duplicate_links.iter_rows(named=True):
    stash.update_scene({
        "id": scene["id"],
        "urls": scene["unique_urls"]
    })



# %% [markdown]
# # Galleries

# %%
galleries_with_links = pl.DataFrame(stash.find_galleries({
  "url": {
    "value": "",
    "modifier": "NOT_NULL"
  }
}, fragment="id title urls"))

galleries_with_duplicate_links = galleries_with_links.filter(
    pl.col("urls").list.len() != pl.col("urls").list.unique().list.len()
).with_columns(
    pl.col("urls").map_elements(unique_stable, return_dtype=pl.List(pl.Utf8)).alias("unique_urls")
)
galleries_with_duplicate_links



# %%
for scene in galleries_with_duplicate_links.iter_rows(named=True):
    stash.update_gallery({
        "id": scene["id"],
        "urls": scene["unique_urls"]
    })


