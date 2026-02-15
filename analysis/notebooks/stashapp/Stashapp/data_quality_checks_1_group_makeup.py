# %%
import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath("")))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

stash = get_stashapp_client()
stash_client = StashAppClient()




# %%
multiple_sex_scenes_tag_id = stash.find_tag("Multiple Sex Scenes in a Scene")["id"]
missing_performer_male_tag_id = stash.find_tag("Missing Performer (Male)")["id"]
missing_performer_female_tag_id = stash.find_tag("Missing Performer (Female)")["id"]

all_scenes = pl.DataFrame(stash.find_scenes({ "tags": { "value": [], "modifier": "INCLUDES", "excludes": [multiple_sex_scenes_tag_id, missing_performer_male_tag_id, missing_performer_female_tag_id] } }, fragment="id title performers { id name gender } tags { id name }"))
all_tags = pl.DataFrame(stash.find_tags(fragment="id name"))

group_makeup_tags = all_tags.filter(
    pl.col("name").str.contains("Solo") |
    pl.col("name").str.contains("Twosome") |
    pl.col("name").str.contains("Threesome") |
    pl.col("name").str.contains("Foursome") |
    pl.col("name").str.contains("Fivesome") |
    pl.col("name").str.contains("Sixsome") |
    pl.col("name").str.contains("Sevensome")
)





# %%
def get_performer_makeup(performers):
    """Convert performers list to a makeup string like 'BGT' (sorted alphabetically)"""
    gender_map = {"MALE": "B", "FEMALE": "G", "TRANSGENDER_FEMALE": "T", "TRANSGENDER_MALE": "T", "NON_BINARY": "N"}
    return "".join(sorted(gender_map[p["gender"]] for p in performers))

def get_expected_group_tags(performers, all_tags_df):
    """Get the expected group makeup tags based on performer count and genders"""
    makeup = get_performer_makeup(performers)
    count = len(performers)

    # Map common counts to their base names
    count_map = {
        1: "Solo",
        2: "Twosome",
        3: "Threesome", 
        4: "Foursome",
        5: "Fivesome",
        6: "Sixsome",
        7: "Sevensome"
    }

    if count not in count_map:
        return []

    base_tag = count_map[count]
    tag_names = [base_tag]  # Always include base tag

    # Add specific makeup tag if applicable
    if count == 1:
        if makeup == "B":
            tag_names.append(f"{base_tag} Male")
        elif makeup == "G":
            tag_names.append(f"{base_tag} Female")
        elif makeup == "T":
            tag_names.append(f"{base_tag} Trans")
    else:
        # Add orientation-based tags
        if all(p["gender"] == "MALE" for p in performers):
            tag_names.append(f"{base_tag} (Gay)")
        elif all(p["gender"] == "FEMALE" for p in performers):
            tag_names.append(f"{base_tag} (Lesbian)")
        elif all(p["gender"] in ["TRANSGENDER_FEMALE", "TRANSGENDER_MALE"] for p in performers):
            tag_names.append(f"{base_tag} (Trans)")
        elif len(performers) == 2:
            # Special case for twosomes
            if makeup == "BG":
                tag_names.append(f"{base_tag} (Straight)")
            elif any(p["gender"] == "TRANSGENDER_FEMALE" for p in performers):
                # Check combinations with trans female
                if any(p["gender"] == "FEMALE" for p in performers):
                    tag_names.append(f"{base_tag} (Trans-Female)")
                elif any(p["gender"] == "MALE" for p in performers):
                    tag_names.append(f"{base_tag} (Trans-Male)")
            elif any(p["gender"] == "TRANSGENDER_MALE" for p in performers):
                # Check combinations with trans male
                if any(p["gender"] == "FEMALE" for p in performers):
                    tag_names.append(f"{base_tag} (Trans-Female)")
                elif any(p["gender"] == "MALE" for p in performers):
                    tag_names.append(f"{base_tag} (Trans-Male)")

        # Add specific makeup tag for mixed groups of 3+ performers
        if count > 2 and not all(p["gender"] == "FEMALE" for p in performers):
            tag_names.append(f"{base_tag} ({makeup})")

    # Convert tag names to structs with id and name
    return [{"id": row["id"], "name": row["name"]} 
            for row in all_tags_df.filter(pl.col("name").is_in(tag_names)).to_dicts()]

def get_scene_group_makeup_issues(scene, group_makeup_tags, exclude_tag_ids, all_tags_df):
    """Get group makeup issues for a scene and return as a dict"""

    # Convert scene row tuple to dict using column names
    scene = {
        "id": scene[0],
        "title": scene[1],
        "performers": scene[2],
        "tags": scene[3]
    }

    # Skip scenes with exclude tags
    if any(tag["id"] in exclude_tag_ids for tag in scene["tags"]):
        return None

    scene_tags = {tag["name"]: tag["id"] for tag in scene["tags"]}
    group_makeup_tags = {tag["name"]: tag["id"] 
                        for tag in scene["tags"] 
                        if any(tag["name"].startswith(prefix) 
                            for prefix in ["Solo", "Twosome", "Threesome", "Foursome", "Fivesome", "Sixsome", "Sevensome"])}

    expected_tags = get_expected_group_tags(scene["performers"], all_tags_df)
    expected_tag_dict = {tag["name"]: tag["id"] for tag in expected_tags}

    issues = []

    # Check for missing expected tags
    missing_tags = [{"id": tag["id"], "name": tag["name"]} 
                   for tag in expected_tags if tag["name"] not in scene_tags]
    if missing_tags:
        issues.append(f"Missing tags: {', '.join(tag['name'] for tag in missing_tags)}")

    # Check for conflicting or incomplete tag sets
    tag_prefixes = ["Solo", "Twosome", "Threesome", "Foursome", "Fivesome", "Sixsome", "Sevensome"]
    for prefix in tag_prefixes:
        matching_tags = [(name, id) for name, id in group_makeup_tags.items() if name.startswith(prefix)]
        if matching_tags:
            # Must have base tag if any specific tags exist
            if prefix not in scene_tags:
                issues.append(f"Missing base {prefix} tag but has specific tags: {', '.join(name for name, _ in matching_tags)}")

            # Check for incorrect specific tags
            if any(tag["name"].startswith(prefix) for tag in expected_tags):
                unexpected_tags = [{"id": id, "name": name} 
                                 for name, id in matching_tags 
                                 if name not in expected_tag_dict]
                if unexpected_tags:
                    issues.append(f"Has incorrect specific tags: {', '.join(tag['name'] for tag in unexpected_tags)}")

    if not issues:
        return None

    # Format performers as string
    performers_str = "; ".join(f"{p['name']} ({p['gender']})" for p in scene["performers"])

    return {
        "scene_id": int(scene["id"]),
        "title": scene["title"],
        "performers": performers_str,
        "expected_tags": [{"id": tag["id"], "name": tag["name"]} for tag in expected_tags],
        "actual_group_tags": [{"id": id, "name": name} for name, id in group_makeup_tags.items()],
        "issues": "; ".join(issues)
    }

# Get issues for all scenes
exclude_tags = ["Multiple Sex Scenes in a Scene", "Full Movie", "Behind the Scenes", "Missing Performer (Male)", "Non-Sex Performer"]
exclude_tag_ids = [row["id"] for row in all_tags.filter(pl.col("name").is_in(exclude_tags)).to_dicts()]

scene_issues = []
for scene in all_scenes.iter_rows():
    issues = get_scene_group_makeup_issues(scene, group_makeup_tags, exclude_tag_ids, all_tags)
    if issues:
        scene_issues.append(issues)

# Create DataFrame with struct columns for tags
issues_df = pl.DataFrame(scene_issues).with_columns([
    pl.col("expected_tags").cast(pl.List(pl.Struct([pl.Field("id", pl.Utf8), pl.Field("name", pl.Utf8)]))),
    pl.col("actual_group_tags").cast(pl.List(pl.Struct([pl.Field("id", pl.Utf8), pl.Field("name", pl.Utf8)])))
])

# Sort by scene_id
issues_df = issues_df.sort("scene_id")

# Display the DataFrame
issues_df






# # %%
# selected = issues_df.head(1).to_dicts()[0]
# selected
# 
# # %%
# # Update the scene with the expected tags
# expected_tags = selected['expected_tags']
# expected_tag_ids = [tag['id'] for tag in expected_tags]
# expected_tag_ids
# 
# refreshed_scene = stash.find_scene(selected['scene_id'])
# current_tags = refreshed_scene['tags']
# current_tag_ids = [tag['id'] for tag in current_tags]
# print(current_tag_ids)
# updated_tag_ids = current_tag_ids + expected_tag_ids
# print(updated_tag_ids)
# 
# stash.update_scene({
#     'id': selected['scene_id'],
#     'tag_ids': updated_tag_ids
# })
# 
# # %%
# # Update the scene with Non-Sex Performer tag
# non_sex_performer_tag = all_tags.filter(pl.col('name') == "Non-Sex Performer").to_dicts()[0]['id']
# 
# stash.update_scene({
#     'id': selected['scene_id'],
#     'tag_ids': updated_tag_ids + [non_sex_performer_tag]
# })
