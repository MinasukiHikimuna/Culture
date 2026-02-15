# %%
import os
import sys

import polars as pl


sys.path.append(os.path.dirname(os.path.abspath("")))

from libraries.client_stashapp import StashAppClient, get_stashapp_client


stash = get_stashapp_client()
stash_client = StashAppClient()





# %%
def hamming_distance_hex(hash1: str, hash2: str) -> int:
    """Calculate Hamming distance between two hex strings."""
    try:
        bin1 = bin(int(hash1, 16))[2:].zfill(64)
        bin2 = bin(int(hash2, 16))[2:].zfill(64)
        return sum(b1 != b2 for b1, b2 in zip(bin1, bin2))
    except (ValueError, TypeError):
        return 0

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
    "excludes": [scenes_with_multiple_versions["id"]]
  }
}, fragment="id title date studio { name } files { id duration path width height size fingerprints { type value } }")
# Create Polars DataFrame with strict=False to handle mixed numeric types
scenes_with_dupes_df = pl.DataFrame(scenes_with_dupes, strict=False)
scenes_with_dupes_df




# %%
# Create a list to store all file records
file_records = []

for scene in scenes_with_dupes:
    for i, file in enumerate(scene["files"]):
        # Extract fingerprints
        oshash = next((fp["value"] for fp in file["fingerprints"] if fp["type"] == "oshash"), None)
        phash = next((fp["value"] for fp in file["fingerprints"] if fp["type"] == "phash"), None)

        # Create a record for each file
        record = {
            "scene_id": scene["id"],
            "title": scene["title"],
            "date": scene["date"],
            "studio_name": scene["studio"]["name"] if scene["studio"] else None,
            "file_id": file["id"],
            "file_path": file["path"],
            "resolution_width": float(file["width"]),
            "resolution_height": float(file["height"]),
            "size": float(file["size"]),
            "duration": float(file["duration"]),
            "oshash": oshash,
            "phash": phash,
            "is_primary": i == 0
        }
        file_records.append(record)

# Create DataFrame from the flattened records
files_df = pl.DataFrame(file_records, strict=False)

# Find scenes with matching durations but differing phashes
phash_mismatches = []
for scene_id, group in files_df.group_by("scene_id"):
    # Get all files for this scene
    scene_files = group.to_dicts()

    # Skip if durations don't match
    durations = set(file["duration"] for file in scene_files)
    if len(durations) > 1:
        continue

    # Compare phashes
    has_mismatch = False
    for i, file1 in enumerate(scene_files):
        for file2 in scene_files[i + 1:]:
            if hamming_distance_hex(file1["phash"], file2["phash"]) > 8:
                has_mismatch = True
                break
        if has_mismatch:
            phash_mismatches.extend(scene_files)
            break



# %%
if len(phash_mismatches) == 0:
    print("No phash mismatches found")




# %%
# Create results DataFrame
results_df = pl.DataFrame(phash_mismatches, strict=False).sort("scene_id")

# Print results
print("\nScenes with matching durations but differing phash values (>8 bits different):")
for scene_id, group in results_df.group_by("scene_id"):
    scene_files = group.to_dicts()
    print(f"\nScene {scene_id} - {scene_files[0]['title']}")

    for file in scene_files:
        primary_status = " (Primary)" if file["is_primary"] else ""
        print(f"  File{primary_status}: {file['file_path']}")
        print(f"    Duration: {file['duration']}s")
        print(f"    pHash: {file['phash']}")

        if not file["is_primary"]:
            primary_file = next(f for f in scene_files if f["is_primary"])
            hamming_dist = hamming_distance_hex(primary_file["phash"], file["phash"])
            print(f"    Hamming distance from primary: {hamming_dist} bits")

print(f"\nTotal scenes with phash mismatches: {len(set(results_df['scene_id']))}")


