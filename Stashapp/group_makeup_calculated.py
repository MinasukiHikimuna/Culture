# %%
import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath('')))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

stash = get_stashapp_client()
stash_client = StashAppClient()


# %%
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


# %%
group_makeup_verified_tag_id = stash.find_tag("Group Makeup Verified")["id"]
group_makeup_calculated_parent_tag = stash.find_tag("Group Makeup Calculated", fragment="id name children { id name }")
group_makeup_calculated_tag_ids = [tag["id"] for tag in group_makeup_calculated_parent_tag["children"]]


# %%
excluded_scenes = stash.find_scenes({ "tags": { "value": excluded_tags, "modifier": "INCLUDES" } }, fragment="id title date tags { id name }")
for scene in excluded_scenes:
    scene_tag_ids = [tag["id"] for tag in scene["tags"]]
    if any(tag_id in group_makeup_calculated_tag_ids for tag_id in scene_tag_ids):
        matching_tag = next((tag for tag in scene["tags"] if tag["id"] in group_makeup_calculated_tag_ids), None)
        if matching_tag:
            print("Scene", scene["id"], "has group makeup calculated tag:", matching_tag["name"])


# %%
# Reset calculated group makeup tags
all_scenes = pl.DataFrame(stash.find_scenes(fragment="id title date performers { id name gender } tags { id name }"))
for scene in all_scenes.iter_rows(named=True):
    existing_tag_ids = [tag["id"] for tag in scene["tags"]]
    cleaned_tag_ids = [tag_id for tag_id in existing_tag_ids if tag_id not in group_makeup_calculated_tag_ids]
    stash.update_scene({
        "id": scene["id"],
        "tag_ids": cleaned_tag_ids
    })


# %% [markdown]
# # Temp

# %%
all_tags = pl.DataFrame(stash.find_tags(fragment="id name"))
all_tags


# %%
group_makeup_generic_parent_tag = stash.find_tag("Group Makeup Generic", fragment="id name children { id name }")
group_makeup_generic_parent_tag

group_makeup_generic_tags = [tag for tag in group_makeup_generic_parent_tag["children"]]
group_makeup_generic_tag_ids = [tag["id"] for tag in group_makeup_generic_tags]

group_makeup_specific_parent_tag = stash.find_tag("Group Makeup Specific", fragment="id name children { id name children { id name } }")
# List tag ids for child tags of child tags of group makeup specific parent tag
group_makeup_specific_tags = [
    grandchild
    for child in group_makeup_specific_parent_tag["children"]
    for grandchild in child["children"]
]
group_makeup_specific_tag_ids = [tag["id"] for tag in group_makeup_specific_tags]

# %%
group_makeup_verified_tag_id = stash.find_tag("Group Makeup Verified")["id"]

verified_scenes = stash.find_scenes({ "tags": { "value": [group_makeup_verified_tag_id], "modifier": "INCLUDES" } }, fragment="id title date tags { id name }")

def check_group_makeup_tags(scene):
    """Check if a scene has exactly one generic and one specific group makeup tag"""
    scene_tag_ids = set(tag["id"] for tag in scene["tags"])
    
    # Count generic tags
    generic_count = sum(1 for tag_id in group_makeup_generic_tag_ids if tag_id in scene_tag_ids)
    
    # Count specific tags
    specific_count = sum(1 for tag_id in group_makeup_specific_tag_ids if tag_id in scene_tag_ids)
    
    return {
        "generic_count": generic_count,
        "specific_count": specific_count,
        "has_correct_tags": generic_count == 1 and specific_count == 1
    }

# Analyze verified scenes
results = []
for scene in verified_scenes:
    tag_counts = check_group_makeup_tags(scene)
    if not tag_counts["has_correct_tags"]:
        results.append({
            "id": scene["id"],
            "title": scene["title"],
            "generic_count": tag_counts["generic_count"],
            "specific_count": tag_counts["specific_count"],
            "tags": [tag["name"] for tag in scene["tags"] 
                    if tag["id"] in group_makeup_generic_tag_ids 
                    or tag["id"] in group_makeup_specific_tag_ids]
        })

# Convert to DataFrame for better visualization
issues_df = pl.DataFrame(results)

if len(results) == 0:
    print("All verified scenes have correct group makeup tag counts!")
else:
    print(f"Found {len(results)} scenes with incorrect tag counts:")
    print(issues_df)


# %%
class GroupMakeupMapping:
    def __init__(self, all_tags_df):
        self.mappings = {}  # calculated_tag_name -> (generic_tag_name, specific_tag_name)
        self.ignored_tags = set()  # Set of calculated tags to ignore
        self.valid_tag_names = set(all_tags_df["name"])
        
    def add_mapping(self, calculated_name, generic_name, specific_name=None):
        # Strip the prefix if present
        if calculated_name.startswith("Group Makeup Calculated: "):
            calculated_name = calculated_name[len("Group Makeup Calculated: "):]
            
        # Validate generic tag exists
        if generic_name not in self.valid_tag_names:
            raise ValueError(f"Generic tag '{generic_name}' does not exist")
            
        # Validate specific tag exists if provided
        if specific_name is not None and specific_name not in self.valid_tag_names:
            raise ValueError(f"Specific tag '{specific_name}' does not exist")
            
        self.mappings[calculated_name] = (generic_name, specific_name)
    
    def add_to_ignore(self, calculated_name):
        # Strip the prefix if present
        if calculated_name.startswith("Group Makeup Calculated: "):
            calculated_name = calculated_name[len("Group Makeup Calculated: "):]
        self.ignored_tags.add(calculated_name)
    
    def get_generic_tag(self, calculated_name):
        if calculated_name.startswith("Group Makeup Calculated: "):
            calculated_name = calculated_name[len("Group Makeup Calculated: "):]
        return self.mappings.get(calculated_name, (None, None))[0]
    
    def get_specific_tag(self, calculated_name):
        if calculated_name.startswith("Group Makeup Calculated: "):
            calculated_name = calculated_name[len("Group Makeup Calculated: "):]
        return self.mappings.get(calculated_name, (None, None))[1]
    
    def is_ignored(self, calculated_name):
        if calculated_name.startswith("Group Makeup Calculated: "):
            calculated_name = calculated_name[len("Group Makeup Calculated: "):]
        return calculated_name in self.ignored_tags

# Create the mapping instance with tag validation
all_tags = pl.DataFrame(stash.find_tags(fragment="id name"))
makeup_mapping = GroupMakeupMapping(all_tags)

# Add mappings for standard configurations (with both generic and specific tags)
makeup_mapping.add_mapping("1F", "Solo", "Solo Female")
makeup_mapping.add_mapping("1M", "Solo", "Solo Male")
makeup_mapping.add_mapping("1TF", "Solo", "Solo Trans")

makeup_mapping.add_mapping("1F1M", "Twosome", "Twosome (Straight)")
makeup_mapping.add_mapping("2F", "Twosome", "Twosome (Lesbian)")
makeup_mapping.add_mapping("1TF1F", "Twosome", "Twosome (Trans-Female)")
makeup_mapping.add_mapping("1TF1M", "Twosome", "Twosome (Trans-Male)")
makeup_mapping.add_mapping("2M", "Twosome", "Twosome (Gay)")
makeup_mapping.add_mapping("2TF", "Twosome", "Twosome (Trans)")
makeup_mapping.add_mapping("1TF1TM", "Twosome", "Twosome (Trans)")

# Add mappings for threesomes
makeup_mapping.add_mapping("2F1M", "Threesome", "Threesome (BGG)")
makeup_mapping.add_mapping("1F2M", "Threesome", "Threesome (BBG)")
makeup_mapping.add_mapping("3F", "Threesome", "Threesome (Lesbian)")
makeup_mapping.add_mapping("1TF2M", "Threesome", "Threesome (BBT)")
makeup_mapping.add_mapping("2TF1M", "Threesome", "Threesome (BTT)")
makeup_mapping.add_mapping("1TF1F1M", "Threesome", "Threesome (BGT)")
makeup_mapping.add_mapping("1TF2F", "Threesome", "Threesome (GGT)")
makeup_mapping.add_mapping("3TF", "Threesome", "Threesome (Trans)")
makeup_mapping.add_mapping("2TF1TM", "Threesome", "Threesome (Trans)")
makeup_mapping.add_mapping("2TF1F", "Threesome", "Threesome (GTT)")

# Add mappings for foursomes
makeup_mapping.add_mapping("2F2M", "Foursome", "Foursome (BBGG)")
makeup_mapping.add_mapping("3F1M", "Foursome", "Foursome (BGGG)")
makeup_mapping.add_mapping("1F3M", "Foursome", "Foursome (BBBG)")
makeup_mapping.add_mapping("4F", "Foursome", "Foursome (Lesbian)")
makeup_mapping.add_mapping("1TF1F2M", "Foursome", "Foursome (BBGT)")
makeup_mapping.add_mapping("1TF2F1M", "Foursome", "Foursome (BGGT)")
makeup_mapping.add_mapping("1TF3F", "Foursome", "Foursome (GGGT)")
makeup_mapping.add_mapping("1TF3M", "Foursome", "Foursome (BBBT)")
makeup_mapping.add_mapping("2TF2F", "Foursome", "Foursome (GGTT)")
makeup_mapping.add_mapping("3TF1F", "Foursome", "Foursome (GTTT)")

# Add mappings for fivesomes
makeup_mapping.add_mapping("3F2M", "Fivesome", "Fivesome (BBBGG)")
makeup_mapping.add_mapping("2F3M", "Fivesome", "Fivesome (BBBGG)")
makeup_mapping.add_mapping("5F", "Fivesome", "Fivesome (Lesbian)")
makeup_mapping.add_mapping("1TF4M", "Fivesome", "Fivesome (GGGGT)")
makeup_mapping.add_mapping("1TF5M", "Fivesome", "Fivesome (BBBBT)")


# Sixsomes
makeup_mapping.add_mapping("3F3M", "Sixsome", "Sixsome (BBBGGG)")
makeup_mapping.add_mapping("6F", "Sixsome", "Sixsome (Lesbian)")
makeup_mapping.add_mapping("1F5M", "Sixsome", "Sixsome (BBBBBG)")
makeup_mapping.add_mapping("2F4M", "Sixsome", "Sixsome (BBBBGG)")


# Add orgy mappings
makeup_mapping.add_mapping("10F8M", "Orgy", "Orgy (Mixed)")
makeup_mapping.add_mapping("12F3M", "Orgy", "Orgy (Mixed)")
makeup_mapping.add_mapping("13F6M", "Orgy", "Orgy (Mixed)")
makeup_mapping.add_mapping("8F2M", "Orgy", "Orgy (Mixed)")
makeup_mapping.add_mapping("8F3M", "Orgy", "Orgy (Mixed)")
makeup_mapping.add_mapping("8F5M", "Orgy", "Orgy (Mixed)")
makeup_mapping.add_mapping("9F7M", "Orgy", "Orgy (Mixed)")
makeup_mapping.add_mapping("9F8M", "Orgy", "Orgy (Mixed)")


makeup_mapping.add_mapping("7F", "Orgy", "Orgy (Lesbian)")
makeup_mapping.add_mapping("8F", "Orgy", "Orgy (Lesbian)")
makeup_mapping.add_mapping("12F", "Orgy", "Orgy (Lesbian)")

# Add gangbang mappings (only generic tags)
makeup_mapping.add_mapping("1F4M", "Gangbang")
makeup_mapping.add_mapping("1F6M", "Gangbang")
makeup_mapping.add_mapping("1F7M", "Gangbang")
makeup_mapping.add_mapping("1F8M", "Gangbang")
makeup_mapping.add_mapping("1F9M", "Gangbang")
makeup_mapping.add_mapping("1F10M", "Gangbang")
makeup_mapping.add_mapping("1F11M", "Gangbang")
makeup_mapping.add_mapping("1F12M", "Gangbang")
makeup_mapping.add_mapping("1F13M", "Gangbang")

# Add reverse gangbang mappings (only generic tags)
makeup_mapping.add_mapping("4F1M", "Reverse Gangbang")
makeup_mapping.add_mapping("5F1M", "Reverse Gangbang")
makeup_mapping.add_mapping("6F1M", "Reverse Gangbang")
makeup_mapping.add_mapping("7F1M", "Reverse Gangbang")
makeup_mapping.add_mapping("8F1M", "Reverse Gangbang")


# Get unique calculated tags to help with mapping
calculated_tags_df = pl.DataFrame(
    stash.find_tag("Group Makeup Calculated", fragment="id name children { id name }")["children"]
)

print("Calculated tags status:")
for tag in calculated_tags_df.sort("name").iter_rows(named=True):
    name = tag["name"].replace("Group Makeup Calculated: ", "")
    if makeup_mapping.is_ignored(name):
        # print(f"{name}: ignored")
        pass
    else:
        generic = makeup_mapping.get_generic_tag(name)
        specific = makeup_mapping.get_specific_tag(name)
        if generic is None:
            print(f"{name}: needs mapping")
        else:
            # print(f"{name}: {generic} -> {specific}")
            pass


# %%
def check_scene_tags(scene, makeup_mapping, generic_tag_ids, specific_tag_ids):
    """Check if a scene has the correct tags according to the mapping"""
    
    # Get the calculated tag if it exists
    calculated_tag = next((
        tag["name"] for tag in scene["tags"] 
        if tag["name"].startswith("Group Makeup Calculated: ")
    ), None)
    
    if not calculated_tag:
        return None  # Skip scenes without calculated tags
        
    # Get expected generic and specific tags
    expected_generic = makeup_mapping.get_generic_tag(calculated_tag)
    expected_specific = makeup_mapping.get_specific_tag(calculated_tag)
    
    # Find actual generic and specific tags
    actual_generic_tags = [
        tag["name"] for tag in scene["tags"]
        if tag["id"] in generic_tag_ids
    ]
    actual_specific_tags = [
        tag["name"] for tag in scene["tags"]
        if tag["id"] in specific_tag_ids
    ]
    
    # Check if tags match expectations
    if makeup_mapping.is_ignored(calculated_tag):
        return None
        
    issues = []
    
    # If we expect both generic and specific
    if expected_specific:
        if len(actual_generic_tags) != 1 or actual_generic_tags[0] != expected_generic:
            issues.append(f"Generic tag mismatch - Expected: {expected_generic}, Got: {actual_generic_tags}")
        if len(actual_specific_tags) != 1 or actual_specific_tags[0] != expected_specific:
            issues.append(f"Specific tag mismatch - Expected: {expected_specific}, Got: {actual_specific_tags}")
    
    # If we only expect generic
    else:
        if len(actual_generic_tags) != 1 or actual_generic_tags[0] != expected_generic:
            issues.append(f"Generic tag mismatch - Expected: {expected_generic}, Got: {actual_generic_tags}")
        if len(actual_specific_tags) > 0:
            issues.append(f"Unexpected specific tags present: {actual_specific_tags}")
    
    if issues:
        return {
            "id": scene["id"],
            "title": scene["title"],
            "calculated_tag": calculated_tag,
            "expected_generic": expected_generic,
            "expected_specific": expected_specific,
            "actual_generic": actual_generic_tags,
            "actual_specific": actual_specific_tags,
            "issues": issues
        }
    
    return None

# Get all scenes
all_scenes = pl.DataFrame(stash.find_scenes(fragment="id title tags { id name }"))

# Check each scene
issues = []
for scene in all_scenes.iter_rows(named=True):
    result = check_scene_tags(scene, makeup_mapping, group_makeup_generic_tag_ids, group_makeup_specific_tag_ids)
    if result:
        issues.append(result)

# Convert results to DataFrame for better visualization
if issues:
    issues_df = pl.DataFrame(issues)
    print(f"Found {len(issues)} scenes with incorrect tags:")
    print(issues_df)
else:
    print("All scenes have correct tags according to mappings!")

# Optional: Show detailed breakdown of issues
for issue in issues:
    print(f"\nScene {issue['id']} - {issue['title']}")
    print(f"Calculated tag: {issue['calculated_tag']}")
    for problem in issue['issues']:
        print(f"- {problem}")


# %%
ai_tagme_tag = stash.find_tag("AI_TagMe")["id"]
ai_tagme_tag

# %%
for issue in issues_df.iter_rows(named=True):
    issue_scene = stash.find_scene(issue["id"])
    existing_tags = [tag["id"] for tag in issue_scene["tags"]]
    updated_tags = existing_tags + [ai_tagme_tag]
    stash.update_scene({
        "id": issue["id"],
        "tag_ids": updated_tags 
    })
    print(issue["id"])

# %%
from libraries import browser

issues_batch = issues_df.head(10)

# Create list of full URLs
urls = [f"https://stash.chiefsclub.com/scenes/{issue['id']}" for issue in issues_batch.iter_rows(named=True)]

# Open all URLs at once
results = browser.open_or_update_tabs(urls)

# Check results
for url, success in results.items():
    if not success:
        print(f"Failed to open: {url}")

# %%
likely_missing_performer_male = issues_df.filter(pl.col("expected_generic").str.contains("Solo") & pl.col("actual_generic").list.contains("Twosome"))
likely_missing_performer_male

# %%
likely_missing_performer_male_group = stash.find_movie("Likely Missing Performer (Male)", create=True)
likely_missing_performer_male_group

# %%
for scene in likely_missing_performer_male.iter_rows(named=True):
    stash.update_scene({
        "id": scene["id"],
        "movies": [{ "movie_id": likely_missing_performer_male_group["id"] }]
    })

# %% [markdown]
# # Checking amounts

# %%
group_makeup_verified_tag_id = stash.find_tag("Group Makeup Verified")["id"]
group_makeup_calculated_parent_tag = stash.find_tag("Group Makeup Calculated", fragment="id name children { id name }")
group_makeup_calculated_tag_ids = [tag["id"] for tag in group_makeup_calculated_parent_tag["children"]]

# %%
unverified_scenes = stash.find_scenes({ "tags": { "value": [], "modifier": "INCLUDES", "excludes": [group_makeup_verified_tag_id] } }, fragment="id title date tags { id name }")

# Convert to polars DataFrame and explode tags
unverified_df = pl.DataFrame(unverified_scenes).explode("tags")

# Filter for only group makeup calculated tags
group_makeup_df = (
    unverified_df
    .filter(pl.col("tags").struct.field("id").is_in(group_makeup_calculated_tag_ids))
    .group_by("tags")
    .agg(
        pl.col("id").count().alias("scene_count")
    )
    .sort("scene_count", descending=True)
)
print(group_makeup_df.sum().select(pl.col("scene_count")))
group_makeup_df

