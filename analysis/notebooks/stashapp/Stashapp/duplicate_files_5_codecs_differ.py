# %%
import sys
from pathlib import Path

import polars as pl


sys.path.append(str(Path.cwd().parent))

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
scenes_with_dupes_df





# %%
import polars as pl


# Explode the files array to get one row per file
files_df = scenes_with_dupes_df.explode("files")

# Group by scene ID and check if there are different codecs within each group
codec_analysis = (files_df
    .select([
        "id",
        "title",
        pl.col("files").struct.field("video_codec").alias("video_codec"),
        pl.col("files").struct.field("audio_codec").alias("audio_codec")
    ])
    .group_by("id")
    .agg([
        pl.col("title").first(),
        pl.col("video_codec").alias("video_codecs"),
        pl.col("audio_codec").alias("audio_codecs"),
        pl.col("video_codec").n_unique().alias("unique_video_codecs"),
        pl.col("audio_codec").n_unique().alias("unique_audio_codecs")
    ])
    .filter(
        (pl.col("unique_video_codecs") > 1) |
        (pl.col("unique_audio_codecs") > 1)
    )
)
codec_analysis




# %%
stash_client.update_tags_for_scenes(
    codec_analysis.select("id").to_series().to_list(),
    ["Duplicate: Video or Audio Formats Differ"],
    []
)
