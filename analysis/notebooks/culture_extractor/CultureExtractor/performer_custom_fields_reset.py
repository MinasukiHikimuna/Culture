###############################################
# This notebook will reset the custom fields
# for performers for a given site.
###############################################

# %%
import sys
from pathlib import Path

import polars as pl
from dotenv import load_dotenv


sys.path.append(str(Path.cwd().parent))

from libraries.client_stashapp import StashAppClient, get_stashapp_client

load_dotenv()


stash_client = StashAppClient()
stash_raw_client = get_stashapp_client()


# %%
short_name = "lezkiss"
ce_custom_field_key = f"CultureExtractor.{short_name}"

all_stashapp_performers = stash_client.get_performers()
all_stashapp_performers = all_stashapp_performers.with_columns(
    pl.col("stashapp_custom_fields")
    .list.eval(
        pl.when(pl.element().struct.field("key") == ce_custom_field_key)
        .then(pl.element().struct.field("value"))
        .otherwise(None)
    )
    .list.eval(pl.element().filter(pl.element().is_not_null()))
    .list.first()
    .alias("ce_custom_field_value")
)
all_stashapp_performers

# %%
performers_with_custom_field = all_stashapp_performers.filter(
    pl.col("ce_custom_field_value").is_not_null()
)
performers_with_custom_field

# %%
for performer in performers_with_custom_field.iter_rows(named=True):
    performer_id = performer["stashapp_id"]
    custom_fields_list = performer["stashapp_custom_fields"]
    custom_fields = {}
    for field in custom_fields_list:
        custom_fields[field["key"]] = field["value"]

    if ce_custom_field_key in custom_fields:
        del custom_fields[ce_custom_field_key]
        stash_client.update_performer_custom_fields_full(performer_id, custom_fields)
