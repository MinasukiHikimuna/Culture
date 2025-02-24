# %%
import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath('')))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

stash = get_stashapp_client()
stash_client = StashAppClient()


# %%
oshash_and_duration_match_tag = stash.find_tag({ "name": "Duplicate: OSHASH And Duration Match" })
duration_match_tag = stash.find_tag({ "name": "Duplicate: Duration Match" })
scenes_with_multiple_versions = stash.find_tag({ "name": "Scene: Multiple Versions" })
duration_mismatch_tag = stash.find_tag({ "name": "Duplicate: Duration Mismatch" })




# %%
scenes_with_dupes = stash.find_scenes({ 
  "file_count": {
    "modifier": "GREATER_THAN",
    "value": 1
  },
  "tags": {
    "value": [],
    "modifier": "INCLUDES",
    "excludes": [scenes_with_multiple_versions['id']]
  }
}, fragment="id title date studio { name } files { id duration path width height size fingerprints { type value } }")





# %%
# Create a list to store all file records
file_records = []

for scene in scenes_with_dupes:
    for i, file in enumerate(scene['files']):
        # Extract fingerprints
        oshash = next((fp['value'] for fp in file['fingerprints'] if fp['type'] == 'oshash'), None)
        phash = next((fp['value'] for fp in file['fingerprints'] if fp['type'] == 'phash'), None)
        
        # Create a record for each file
        record = {
            'scene_id': scene['id'],
            'title': scene['title'],
            'date': scene['date'],
            'studio_name': scene['studio']['name'] if scene['studio'] else None,
            'file_id': file['id'],
            'file_path': file['path'],
            'resolution_width': file['width'],
            'resolution_height': file['height'],
            'size': file['size'],
            'duration': file['duration'],
            'oshash': oshash,
            'phash': phash,
            'is_primary': i == 0  # True if this is the first file in the scene's files list
        }
        file_records.append(record)

# Create Polars DataFrame
scenes_with_multiple_files_df = pl.DataFrame(file_records)
scenes_with_multiple_files_df





# %% [markdown]
# # Deleting files where OSHASH is identical to another file in the scene
# 

# %%
import os

# Filter to only show rows that have matching oshash values with other rows
duplicate_files_df = scenes_with_multiple_files_df.filter(
    pl.col('oshash').is_in(
        scenes_with_multiple_files_df.group_by('oshash')
        .agg(pl.len().alias('dupe_count'))  # Changed to use len() and a unique alias
        .filter(pl.col('dupe_count') > 1)
        .get_column('oshash')
    )
).sort(['oshash', 'file_id'])

duplicate_files_df = duplicate_files_df.with_columns(pl.col('file_path').map_elements(lambda x: os.path.exists(x), return_dtype=pl.Boolean).alias('file_path_exists'))

print("\nFiles with duplicate oshash values:")
print(duplicate_files_df)





# %%
# Group by scene_id and oshash to find duplicates within each scene
grouped_files = duplicate_files_df.group_by(['scene_id', 'oshash']).agg([
    pl.col('file_id').min().alias('keep_file_id'),  # File to keep
    pl.col('file_id').alias('all_file_ids'),        # All file IDs
    pl.col('file_path').alias('all_file_paths'),    # All file paths
    pl.col('size').alias('all_file_sizes'),         # File sizes
    pl.col('file_path_exists').alias('all_file_exists'),  # Path existence check
    pl.col('is_primary').alias('all_is_primary')    # Primary file flags
])

# Lists to store kept and deleted file information
kept_files = []
files_to_delete = []

# Print summary and collect file information
print("\nFiles to be deleted:")
for row in grouped_files.iter_rows(named=True):
    file_ids = row['all_file_ids']
    file_paths = row['all_file_paths']
    file_sizes = row['all_file_sizes']
    is_primary = row['all_is_primary']
    
    # Find primary file index if it exists
    primary_indices = [i for i, p in enumerate(is_primary) if p]
    if primary_indices:
        # Keep the primary file
        keep_index = primary_indices[0]
        keep_file_id = file_ids[keep_index]
    else:
        # If no primary file, keep the one with lowest file_id
        keep_file_id = row['keep_file_id']
        keep_index = file_ids.index(keep_file_id)
    
    kept_files.append({
        'scene_id': row['scene_id'],
        'file_id': keep_file_id,
        'file_path': file_paths[keep_index],
        'size': file_sizes[keep_index],
        'is_primary': is_primary[keep_index]
    })
    
    # Get indices of files to delete (all except kept file, never delete primary files)
    delete_indices = [i for i, (file_id, p) in enumerate(zip(file_ids, is_primary)) 
                     if file_id != keep_file_id and not p]
    
    if delete_indices:  # Only show if there are files to delete
        primary_status = " (Primary)" if is_primary[keep_index] else ""
        print(f"\nScene {row['scene_id']} - Keeping{primary_status}: {file_paths[keep_index]} (ID: {keep_file_id}, Size: {file_sizes[keep_index]:,} bytes) Exists: {os.path.exists(file_paths[keep_index])}")
        for idx in delete_indices:
            print(f"  Will delete: {file_paths[idx]} (ID: {file_ids[idx]}, Size: {file_sizes[idx]:,} bytes) Exists: {os.path.exists(file_paths[idx])}")
            files_to_delete.append({
                'scene_id': row['scene_id'],
                'file_id': file_ids[idx],
                'file_path': file_paths[idx],
                'size': file_sizes[idx],
                'is_primary': is_primary[idx]
            })

# Calculate total space that would be freed
total_space = sum(file['size'] for file in files_to_delete)
print(f"\nTotal space that would be freed: {total_space:,} bytes ({total_space/1024/1024/1024:.2f} GB)")
print(f"Number of files to delete: {len(files_to_delete)}")

# Create DataFrames for kept and deleted files
kept_files_df = pl.DataFrame(kept_files)
delete_files_df = pl.DataFrame(files_to_delete)




# %%
for row in delete_files_df.iter_rows(named=True):
    stash.destroy_files(row['file_id'])
