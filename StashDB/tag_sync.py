# %%
import polars as pl
import dotenv
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath('')))

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
stashdb_tags = stashbox_client.query_tags()





# %%
# Get tags from StashDB
df_stashdb_tags = pl.DataFrame(stashdb_tags)

df_stashdb_tags = df_stashdb_tags.with_columns(
    pl.col("category").map_elements(lambda x: x['id'] if x else None, return_dtype=pl.Utf8).alias("category_id"),
    pl.col("category").map_elements(lambda x: x['name'] if x else None, return_dtype=pl.Utf8).alias("category_name"),
    pl.col("category").map_elements(lambda x: x['description'] if x else None, return_dtype=pl.Utf8).alias("category_description"),
    pl.col("category").map_elements(lambda x: x['group'] if x else None, return_dtype=pl.Utf8).alias("category_group"),
).drop("category")

df_stashdb_tags





# %%
df_stashdb_tags.write_json("H:\\Parquet Data\\StashDB\\stashdb_tags.json")





# %%
# Get tags from Stash
stash_tags = stash.find_tags()
df_stash_tags = pl.DataFrame(stash_tags)
df_stash_tags = df_stash_tags.with_columns(
    pl.col("aliases").map_elements(
        lambda aliases: next(
            (alias[len(stashdb_id_alias_prefix):] for alias in aliases if isinstance(alias, str) and alias.startswith(stashdb_id_alias_prefix)),
            None
        ),
        return_dtype=pl.Utf8
    ).alias("stashdb_id")
)
df_stash_tags





# %%
# Merge df_stashdb_tags and df_stash_tags based on the 'name' column
merged_df = df_stashdb_tags.join(df_stash_tags, left_on='id', right_on='stashdb_id', how='full', suffix='_stash')

# Identify matching and non-matching tags
matching_tags = merged_df.filter(pl.col('id').is_not_null() & pl.col('id_stash').is_not_null())
stashdb_only_tags = merged_df.filter(pl.col('id_stash').is_null())
stash_only_tags = merged_df.filter(pl.col('id').is_null())

# Display results
print(f"Total matching tags: {len(matching_tags)}")
print(f"Tags only in StashDB: {len(stashdb_only_tags)}")
print(f"Tags only in Stash: {len(stash_only_tags)}")

merged_df





# %%
my_very_own_tags_parent_tag = stash.find_tag({ "name": "My Very Own Tags" })

df_stash_only_tags = df_stash_tags.filter(
    pl.col("id").is_in(stash_only_tags.select("id_stash").unique())
).filter(
    # Check if the tag doesn't have "My Very Own Tags" as parent
    pl.col("parents").map_elements(
        lambda parents: not any(parent.get('id') == my_very_own_tags_parent_tag['id'] for parent in parents),
        return_dtype=pl.Boolean
    )
).filter(
    ~pl.col("name").str.starts_with("Category:") & 
    ~pl.col("name").str.starts_with("Category Group:") & 
    ~pl.col("name").str.starts_with("AI_") & 
    ~pl.col("name").str.ends_with("_AI") &
    ~pl.col("name").str.starts_with("Data Quality Issue") & 
    ~pl.col("name").str.starts_with("Duplicate") & 
    ~pl.col("name").str.starts_with("Galleries") & 
    ~pl.col("name").str.starts_with("Group Makeup")
).select("id", "name", "aliases")
df_stash_only_tags





# %% [markdown]
# # Create category groups

# %%
# Get all unique category groups from StashDB tags
category_groups = df_stashdb_tags.select('category_group').drop_nulls().unique().to_series().to_list()

# Display the category groups
print("Unique category groups in StashDB:")
for group in sorted(category_groups):
    print(f"- {group}")
    tag_name = f"Category Group: {group}"
    existing_tag = stash.find_tag(tag_name)
    if existing_tag is None:
        stash.create_tag({
            "name": tag_name,
            "description": f"StashDB category group: {group}",
        })
        print(f"Created tag: {tag_name}")
    else:
        print(f"Tag already exists: {tag_name}")





# %% [markdown]
# # Create categories

# %%
# Get all unique categories from StashDB tags
unique_categories = df_stashdb_tags.select(['category_id', 'category_name', 'category_group', 'category_description']).drop_nulls().unique()

# Display the unique categories
print("Unique categories in StashDB:")
for category in unique_categories.iter_rows(named=True):
    print(f"- Name: {category['category_name'] or 'N/A'}")
    print(f"  ID: {category['category_id']}")
    print(f"  Group: {category['category_group'] or 'N/A'}")
    print(f"  Description: {category['category_description'] or 'N/A'}")
    print()

# Create tags for each unique category in Stash
for category in unique_categories.iter_rows(named=True):
    name = category['category_name']
    group = category['category_group']
    description = category['category_description']
    
    category_tag = stash.find_tag(f"Category: {name}")
    if category_tag is None:
        category_group_tag = stash.find_tag(f"Category Group: {group}")
        
        category_tag = stash.create_tag({
            "name": f"Category: {name}",
            "description": f"StashDB category: {name}",
            "parent_ids": [category_group_tag['id']] if category_group_tag else None,
        })
        print(f"Created category tag: {name}")
    else:
        aliases = ["StashDB ID: " + category['category_id']]
        stash.update_tag({ "id": category_tag['id'], "aliases": aliases })
        print(f"Updated category tag: {name}")





# %% [markdown]
# # Check if some local StashDB tags have been removed from remote StashDB

# %%
local_stashdb_ids = df_stashdb_tags.select('id').unique().to_series().to_list()
remote_stashdb_ids = df_stash_tags.select('stashdb_id').unique().to_series().to_list()

local_stashdb_tags = df_stash_tags.filter(pl.col('stashdb_id').is_in(set(local_stashdb_ids) - set(remote_stashdb_ids)))
local_stashdb_tags





# %% [markdown]
# # Update descriptions

# %%
# Create records of tags that need updates
description_update_records = []

for row in df_stash_tags.iter_rows(named=True):
    stash_tag_name = row['name']
    stashdb_tag = df_stashdb_tags.filter(pl.col('name') == stash_tag_name)
    
    if not stashdb_tag.is_empty():
        stashdb_tag = stashdb_tag.to_dicts()[0]
        
        # Check if description needs updating
        if stashdb_tag['description'] != row['description']:
            description_update_records.append({
                'tag_id': row['id'],
                'name': stash_tag_name,
                'field': 'description',
                'current_value': row['description'] or '',  # Handle None values
                'proposed_value': stashdb_tag['description'] or '',
            })
        
df_description_updates = pl.DataFrame(description_update_records).sort(['name', 'field']).filter(pl.col('current_value') != pl.col('proposed_value'))
df_description_updates




# %%
for row in df_description_updates.iter_rows(named=True):
    print(row['name'])
    print(row['current_value'])
    print(row['proposed_value'])
    print()

    update_data = {
        "id": row['tag_id'],
        "description": row['proposed_value']
    }
    try:
        stash.update_tag(update_data)
        print(f"Updated tag: {row['name']}")
    except Exception as e:
        print(f"Error updating tag {row['name']}: {e}")





# %% [markdown]
# # Update aliases
# 

# %%
# Create records of tags that need updates
alias_update_records = []

for row in df_stash_tags.iter_rows(named=True):
    stash_tag_name = row['name']
    stashdb_tag = df_stashdb_tags.filter(pl.col('name') == stash_tag_name)
    
    if not stashdb_tag.is_empty():
        stashdb_tag = stashdb_tag.to_dicts()[0]
        
        # Get current aliases and separate StashDB ID aliases
        current_aliases = set(row['aliases']) if row['aliases'] else set()
        current_stashdb_ids = {alias for alias in current_aliases 
                             if alias.startswith(stashdb_id_alias_prefix)}
        current_regular_aliases = current_aliases - current_stashdb_ids
        
        # Get proposed aliases from StashDB, excluding CJK
        proposed_aliases = {alias for alias in (stashdb_tag['aliases'] or []) 
                          if not contains_cjk(alias)}
        
        # Check if regular aliases need updating
        if current_regular_aliases != proposed_aliases:
            # Keep exactly one StashDB ID alias if it exists
            final_stashdb_id = next(iter(current_stashdb_ids)) if current_stashdb_ids else None
            
            # Combine proposed aliases with StashDB ID
            final_aliases = proposed_aliases
            if final_stashdb_id:
                final_aliases.add(final_stashdb_id)
            
            # Calculate differences for display
            to_add = proposed_aliases - current_regular_aliases
            to_remove = current_regular_aliases - proposed_aliases
            
            # Only proceed if there are changes
            if to_add or to_remove:
                # Format difference string
                diff_parts = []
                if to_add:
                    diff_parts.append(f"+ {', '.join(sorted(to_add))}")
                if to_remove:
                    diff_parts.append(f"- {', '.join(sorted(to_remove))}")
                
                alias_update_records.append({
                    'tag_id': row['id'],
                    'name': stash_tag_name,
                    'current_aliases': ', '.join(sorted(current_aliases)),
                    'proposed_aliases': ', '.join(sorted(final_aliases)),
                    'differences': ' | '.join(diff_parts),
                    'current_list': sorted(current_aliases),
                    'proposed_list': sorted(final_aliases)
                })

# Create DataFrame and sort by name
df_alias_updates = pl.DataFrame(alias_update_records).sort('name')

# Print summary
print(f"Found {len(df_alias_updates)} tags with non-CJK alias updates")
print("\nSample of proposed updates:")
print(df_alias_updates.select(['name', 'current_aliases', 'proposed_aliases', 'differences']).head())

df_alias_updates





# %%
for row in df_alias_updates.iter_rows(named=True):
    update_data = {
        "id": row['tag_id'],
        "aliases": row['proposed_list']
    }
    try:
        stash.update_tag(update_data)
        print(f"Updated tag: {row['name']}")
    except Exception as e:
        print(f"Error updating tag {row['name']}: {e}")





# %% [markdown]
# # Clean out the CJK aliases from existing tags

# %%
# First add a column with cleaned aliases
df_stash_tags = df_stash_tags.with_columns(
    pl.col('aliases').map_elements(lambda x: [alias for alias in x if not contains_cjk(alias)], return_dtype=pl.List(pl.Utf8)).alias('cleaned_aliases')
)

# Find tags where current aliases differ from cleaned aliases
tags_to_update = df_stash_tags.filter(pl.col('aliases') != pl.col('cleaned_aliases'))

print(f"Found {len(tags_to_update)} tags with CJK aliases to remove")
print("\nSample of changes to make:")
print(tags_to_update.select([
    'name',
    'aliases',
    'cleaned_aliases'
]).head())

# Optional: Apply the updates
def apply_alias_cleanup(tags_df):
    for row in tags_df.iter_rows(named=True):
        update_data = {
            'id': row['id'],
            'aliases': row['cleaned_aliases']
        }
        
        try:
            stash.update_tag(update_data)
            print(f"Updated aliases for {row['name']}")
        except Exception as e:
            print(f"Error updating {row['name']}: {e}")

tags_to_update_for_review = tags_to_update.select(['name', 'aliases', 'cleaned_aliases'])
tags_to_update_for_review



# %%
# Uncomment to apply the updates:
# apply_alias_cleanup(tags_to_update)










# %% [markdown]
# # Create new tags

# %%
stashdb_only_tags = df_stashdb_tags.filter(~pl.col('id').is_in(df_stash_tags.select('stashdb_id').to_series()))
stashdb_only_tags


# %%
# Create tags in Stash which exist in StashDB but not in Stash
stashdb_only_tags = df_stashdb_tags.filter(~pl.col('id').is_in(df_stash_tags.select('stashdb_id').to_series()))

print(f"Number of tags in StashDB but not in Stash: {len(stashdb_only_tags)}")

new_tags = []
already_existing_tags = []
for stashdb_tag in stashdb_only_tags.iter_rows(named=True):
    # Check if the tag already exists in Stash
    existing_tag = stash.find_tag(stashdb_tag['name'])
    if existing_tag:
        # Check if the tag exists due to an alias
        if stashdb_tag['name'] in existing_tag['aliases']:
            print(f"Tag already exists due to alias: {stashdb_tag['name']}")
        else:
            print(f"Tag already exists: {stashdb_tag['name']}")
            already_existing_tags.append(stashdb_tag)
        continue
    
    # Find the category tag if it exists
    category_tag = None
    if stashdb_tag['category_name']:
        category_tag = stash.find_tag(f"Category: {stashdb_tag['category_name']}")
    
    # Prepare the tag data
    tag_data = {
        "name": stashdb_tag['name'],
        "description": stashdb_tag['description'],
    }
    
    # Add aliases if they exist
    if stashdb_tag['aliases']:
        tag_data["aliases"] = stashdb_tag['aliases'] + ["StashDB ID: " + stashdb_tag['id']]
    else:
        tag_data["aliases"] = ["StashDB ID: " + stashdb_tag['id']]
    
    # Add parent category if it exists
    if category_tag:
        tag_data["parent_ids"] = [category_tag['id']]
    
    new_tags.append(tag_data)

new_tags_df = pl.DataFrame(new_tags)
new_tags_df




# %%
for tag in already_existing_tags:
    stash_tag = stash.find_tag(tag['name'])
    current_aliases = stash_tag['aliases']
    updated_aliases = current_aliases + ["StashDB ID: " + tag['id']]
    stash.update_tag({
        "id": stash_tag['id'],
        "aliases": updated_aliases
    })
    print(f"Updated \"StashDB ID: {tag['id']}\" alias for {tag['name']}")






# %%
for tag in new_tags_df.iter_rows(named=True):
    # Create the tag in Stash
    try:
        new_tag = stash.create_tag(tag)
        print(f"Created tag: {new_tag['name']}")
    except Exception as e:
        print(f"Error creating tag: {e}")

print(f"Created {len(new_tags_df)} new tags in Stash.")



