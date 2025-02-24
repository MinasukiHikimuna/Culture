# %%
import polars as pl
import sys
import os

# Fix the import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

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
    "excludes": [scenes_with_multiple_versions['id']]
  }
}, fragment="id title date studio { name } files { id duration path width height size fingerprints { type value } format video_codec audio_codec }")
# Create Polars DataFrame with strict=False to handle mixed numeric types
scenes_with_dupes_df = pl.DataFrame(scenes_with_dupes, strict=False)

# Let's first examine what we're working with
print("Sample of first row files data:")
print(scenes_with_dupes_df.select('files').row(0))

# Function to select best quality file from a list of files
def select_best_quality_file(files):
    print(f"Processing files type: {type(files)}")
    
    # Convert Polars Series to list if needed
    if isinstance(files, pl.Series):
        files = files.to_list()
    
    print(f"Files after conversion type: {type(files)}")
    print(f"Files content: {files}")
    
    if not isinstance(files, list) or not files:
        print("Not a list or empty")
        return None
        
    # Convert each file to a dictionary with relevant fields
    files_data = []
    for file in files:
        try:
            file_dict = {
                'id': file['id'],
                'path': file['path'],
                'width': file['width'],
                'height': file['height'],
                'size': file['size'],
                'resolution': file['width'] * file['height'] if file['width'] and file['height'] else 0,
                'duration': file['duration'],
                'format': file['format'],
                'video_codec': file['video_codec'],
                'audio_codec': file['audio_codec'],
                'fingerprints': file['fingerprints']
            }
            files_data.append(file_dict)
        except Exception as e:
            print(f"Error processing file: {e}")
            continue
    
    if not files_data:
        print("No valid files found")
        return None
        
    # Sort by resolution (primary) and size (secondary)
    sorted_files = sorted(files_data, key=lambda x: (x['resolution'], x['size']), reverse=True)
    best_file = sorted_files[0]
    
    print(f"Selected best file: {best_file}")
    return best_file

# Add best_file column
scenes_with_dupes_df = scenes_with_dupes_df.with_columns(
    pl.col('files').map_elements(select_best_quality_file).alias('best_file')
)
scenes_with_dupes_df



# %%
scenes_with_dupes_df.schema


# %%
scenes_with_dupes_df.head(10).to_dicts()