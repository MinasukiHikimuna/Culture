# %% Initialize the clients
import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath('')))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

stash = get_stashapp_client()
stash_client = StashAppClient()





# %% Get the tags
full_movie_tag = stash.find_tag("Full Movie")["id"]
compilation_tag = stash.find_tag("Compilation")["id"]
multiple_sex_scenes_in_a_scene_tag = stash.find_tag("Multiple Sex Scenes in a Scene")["id"]
behind_the_scenes_tag = stash.find_tag("Behind the Scenes")["id"]
tv_series_tag = stash.find_tag("TV Series")["id"]
non_sex_performer_tag = stash.find_tag("Non-Sex Performer")["id"]
virtual_sex_tag = stash.find_tag("Virtual Sex")["id"]
missing_performer_male_tag = stash.find_tag("Missing Performer (Male)")["id"]
missing_performer_female_tag = stash.find_tag("Missing Performer (Female)")["id"]

excluded_tags = [full_movie_tag, compilation_tag, multiple_sex_scenes_in_a_scene_tag, behind_the_scenes_tag, tv_series_tag, non_sex_performer_tag, virtual_sex_tag, missing_performer_male_tag, missing_performer_female_tag]

group_makeup_verified_tag_id = stash.find_tag("Group Makeup Verified")["id"]
group_makeup_calculated_parent_tag = stash.find_tag("Group Makeup Calculated", fragment="id name children { id name }")
group_makeup_calculated_tag_ids = [tag["id"] for tag in group_makeup_calculated_parent_tag["children"]]





# %% Get all scenes and calculate the gender makeup in a data frame
def get_gender_makeup(performers):
    # Initialize counters for each gender
    counts = {
        "TRANSGENDER_FEMALE": 0,
        "TRANSGENDER_MALE": 0,
        "NON_BINARY": 0,
        "FEMALE": 0,
        "MALE": 0
    }
    
    # Count each gender
    for performer in performers:
        counts[performer["gender"]] += 1
    
    # Create abbreviations mapping
    abbrev = {
        "TRANSGENDER_FEMALE": "TF",
        "TRANSGENDER_MALE": "TM",
        "NON_BINARY": "NB",
        "FEMALE": "F",
        "MALE": "M"
    }
    
    # Build the string
    result = ""
    for gender in ["TRANSGENDER_FEMALE", "TRANSGENDER_MALE", "NON_BINARY", "FEMALE", "MALE"]:
        if counts[gender] > 0:
            result += f"{counts[gender]}{abbrev[gender]}"
    
    return result

filtered_scenes = pl.DataFrame(stash.find_scenes({ "tags": { "value": [], "modifier": "INCLUDES", "excludes": excluded_tags }}, fragment="id title date performers { id name gender } tags { id name }"))
filtered_scenes = filtered_scenes.filter(pl.col("performers").list.len() > 0)
filtered_scenes

unique_genders = (
    filtered_scenes
    .explode("performers")
    .select(pl.col("performers").struct.field("gender"))
    .unique()
)

# Add the gender makeup as a new column
all_scenes_with_makeup = filtered_scenes.with_columns(
    pl.col("performers").map_elements(get_gender_makeup, return_dtype=pl.Utf8).alias("gender_makeup")
)

# Show some examples
all_scenes_with_makeup




# %% Get unique gender makeups
group_makeup_calculated = (
    all_scenes_with_makeup
    .select("gender_makeup")
    .unique()
    .sort(by="gender_makeup")
    .with_columns(
        ("Group Makeup Calculated: " + pl.col("gender_makeup")).alias("full_tag_name")
    )
)
group_makeup_calculated





# %% Create tags for the gender makeups
all_tags = pl.DataFrame(stash.find_tags(fragment="id name"))
unique_group_makeup_calculated_tags = all_tags.join(group_makeup_calculated, left_on="name", right_on="full_tag_name", how="right")
group_makeup_calculated_lookup = {row["full_tag_name"]: row["id"] for row in unique_group_makeup_calculated_tags.iter_rows(named=True)}

group_makeup_calculated_parent_tag_id = stash.find_tag("Group Makeup Calculated")["id"]
group_makeup_calculated_parent_tag_id

created_new_tags = False
for gender_makeup in group_makeup_calculated.iter_rows(named=True):
    if gender_makeup["full_tag_name"] in group_makeup_calculated_lookup and group_makeup_calculated_lookup[gender_makeup["full_tag_name"]] is not None:
        continue

    tag = stash.create_tag({ 
        "name": gender_makeup["full_tag_name"],
        "parent_ids": [group_makeup_calculated_parent_tag_id]
    })
    print(f"Created tag: {tag['id']} - {tag['name']}")
    created_new_tags = True

if created_new_tags:
    print("Please re-run this cell to get updated lookup table")




# %% Create a data frame with all the scene edits for manual verification
scene_edits = []
for scene in all_scenes_with_makeup.iter_rows(named=True):
    tag_name = "Group Makeup Calculated: " + scene["gender_makeup"]
    tag_id = group_makeup_calculated_lookup[tag_name]
    if not tag_id:
        raise Exception(f"Tag not found: {tag_name}")

    existing_tag_ids = [tag["id"] for tag in scene["tags"]]
    if tag_id not in existing_tag_ids:
        updated_tag_ids = existing_tag_ids + [tag_id]
        scene_edits.append({
            "id": scene["id"],
            "tag_ids": updated_tag_ids
        })

print(scene_edits)

if len(scene_edits) == 0:
    print("No scene edits needed")
else:
    # Create a DataFrame with scenes that need edits
    scenes_to_edit_df = pl.DataFrame(scene_edits).join(
        all_scenes_with_makeup.select(["id", "title", "date", "performers", "tags", "gender_makeup"]), 
        on="id",
        how="left"
    ).with_columns([
        pl.col("tag_ids").alias("updated_tag_ids"),  # Rename for clarity
        pl.col("tags").map_elements(lambda x: [t["id"] for t in x], return_dtype=pl.List(pl.Utf8)).alias("original_tag_ids")
    ])

    # Show the DataFrame
    scenes_to_edit_df.select([
        "id", 
        "title",
        "date",
        "gender_makeup",
        "original_tag_ids",
        "updated_tag_ids"
    ]) 




# %% Update the scenes with the new tags
for scene in scenes_to_edit_df.iter_rows(named=True):
    stash.update_scene({
        "id": scene["id"],
        "tag_ids": scene["updated_tag_ids"]
    })
