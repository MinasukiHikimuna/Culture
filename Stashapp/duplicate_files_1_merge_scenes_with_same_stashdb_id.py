# %%
import polars as pl
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath("")))

from libraries.client_stashapp import get_stashapp_client, StashAppClient

stash = get_stashapp_client()
stash_client = StashAppClient()


# %%
# Introduce functions
def compare_and_merge_scenes(scenes):
    """Compare and merge multiple scenes, returning a merged version with the most complete metadata"""

    # Helper function to format value for display
    def format_value(val):
        if isinstance(val, list):
            return f"[{len(val)} items]" if len(val) > 3 else str(val)
        return str(val) if val is not None else "None"

    # Helper function to get tag names for display
    def get_tag_names(tags):
        return sorted([t["name"] for t in tags])

    # Helper function to get performer names for display
    def get_performer_names(performers):
        return sorted([p.get("name", f"ID: {p['id']}") for p in performers])

    # Fields to compare (excluding technical details and paths)
    fields_to_compare = [
        "title",
        "code",
        "details",
        "director",
        "date",
        "rating100",
        "organized",
        "o_counter",
        "organized",
        "studio_id",
        "gallery_ids",
        "play_duration",
        "play_count",
    ]

    print("=== Scene Comparison ===\n")

    # Compare basic fields
    merged = {}
    for field in fields_to_compare:
        values = [scene.get(field) for scene in scenes]

        # For numerical fields, handle None values specially
        if field in ["o_counter", "play_count", "play_duration", "rating100"]:
            if all(v is None for v in values):
                merged[field] = None
            else:
                merged[field] = max(v or 0 for v in values)
        else:
            # Choose the first non-None value
            merged[field] = next((v for v in values if v is not None), None)

        # Only show detailed comparison if values differ
        if len(set(str(v) for v in values)) > 1:
            print(f"{field}:")
            for i, val in enumerate(values, 1):
                print(f"  Scene {i}: {format_value(val)}")
            print(f"  Merged: {format_value(merged[field])}\n")
        else:
            print(f"{field}: {format_value(values[0])}")

    print("\n=== Special Fields ===\n")

    # Handle tags
    all_tags = []
    print("tags:")
    for i, scene in enumerate(scenes, 1):
        tags = scene.get("tags", [])
        all_tags.extend(tags)
        print(f"  Scene {i}: {get_tag_names(tags)}")

    merged_tags = list({t["id"]: t for t in all_tags}.values())
    print(f"  Merged: {get_tag_names(merged_tags)}\n")
    merged["tag_ids"] = [t["id"] for t in merged_tags]

    # Handle performers
    all_performers = []
    print("performers:")
    for i, scene in enumerate(scenes, 1):
        performers = scene.get("performers", [])
        all_performers.extend(performers)
        print(f"  Scene {i}: {get_performer_names(performers)}")

    merged_performers = list({p["id"]: p for p in all_performers}.values())
    print(f"  Merged: {get_performer_names(merged_performers)}\n")
    merged["performer_ids"] = [p["id"] for p in merged_performers]

    # Handle other special fields
    special_fields = {
        "stash_ids": lambda scenes: list(
            {
                (s["endpoint"], s["stash_id"]): s
                for scene in scenes
                for s in scene.get("stash_ids", [])
            }.values()
        ),
        "scene_markers": lambda scenes: sorted(
            [m for scene in scenes for m in scene.get("scene_markers", [])],
            key=lambda m: m["seconds"],
        ),
        "o_history": lambda scenes: sorted(
            list(set([h for scene in scenes for h in scene.get("o_history", [])]))
        ),
        "play_history": lambda scenes: sorted(
            list(set([h for scene in scenes for h in scene.get("play_history", [])]))
        ),
        "urls": lambda scenes: sorted(
            list(set([u for scene in scenes for u in scene.get("urls", [])]))
        ),
    }

    for field, merge_func in special_fields.items():
        values = [scene.get(field, []) for scene in scenes]
        merged_items = merge_func(scenes)

        if any(len(v) != len(values[0]) for v in values) or len(merged_items) != len(
            values[0]
        ):
            print(f"{field}:")
            for i, items in enumerate(values, 1):
                print(
                    f"  Scene {i}: {format_value(items) if len(items) <= 3 else f'{len(items)} items'}"
                )
            print(
                f"  Merged: {format_value(merged_items) if len(merged_items) <= 3 else f'{len(merged_items)} items'}\n"
            )
        else:
            print(f"{field}: {len(values[0])} items")

        merged[field] = merged_items

    # Keep other fields from first scene that we haven't explicitly handled
    for key in scenes[0]:
        if key not in merged and key not in [
            "files",
            "paths",
            "sceneStreams",
            "tags",
            "performers",
        ]:
            merged[key] = scenes[0][key]

    return merged


# %%
# Get basic info for all scenes
all_scenes_basic_info = stash.find_scenes(
    {}, fragment="id title studio { id name } stash_ids { endpoint stash_id }"
)

# Map the data with explicit type handling
all_scenes_basic_info_mapped = [
    {
        "stashapp_id": str(scene["id"]),  # Ensure ID is string
        "stashapp_title": (
            str(scene["title"]) if scene["title"] else ""
        ),  # Handle None titles
        "stashapp_studio_id": (
            str(scene["studio"]["id"]) if scene["studio"] else None
        ),  # Ensure studio ID is string
        "stashapp_studio_name": (
            str(scene["studio"]["name"]) if scene["studio"] else None
        ),
        "stashapp_stashdb_id": next(
            (
                str(stash_id["stash_id"])
                for stash_id in scene["stash_ids"]
                if stash_id["endpoint"] == "https://stashdb.org/graphql"
            ),
            None,
        ),
    }
    for scene in all_scenes_basic_info
]

# Create DataFrame with increased schema inference length
all_scenes_basic_info_mapped_df = pl.DataFrame(
    all_scenes_basic_info_mapped,
    infer_schema_length=10000,  # Increase schema inference length
)

scenes_with_dupe_stashdb_ids_basic_info = all_scenes_basic_info_mapped_df.filter(
    pl.col("stashapp_stashdb_id").is_in(
        all_scenes_basic_info_mapped_df.group_by("stashapp_stashdb_id")
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
        .get_column("stashapp_stashdb_id")
    ),
    pl.col("stashapp_studio_id").is_not_null(),
).sort("stashapp_stashdb_id")


# %%
scenes_with_dupe_stashdb_ids_basic_info
print(
    f"Studios with duplicate scenes: {scenes_with_dupe_stashdb_ids_basic_info.select(pl.col('stashapp_studio_id')).unique().to_series().to_list()}"
)

if len(scenes_with_dupe_stashdb_ids_basic_info) > 0:
    studio_id = (
        scenes_with_dupe_stashdb_ids_basic_info.select(pl.col("stashapp_studio_id"))
        .unique()
        .to_series()
        .to_list()[0]
    )
    print(f"Studio ID: {studio_id}")

    all_scenes = stash_client.find_scenes_by_studio(studio_id)
    print(f"Number of scenes: {len(all_scenes)}")

    scenes_with_dupe_stashdb_ids = all_scenes.filter(
        pl.col("stashapp_stashdb_id").is_in(
            all_scenes.group_by("stashapp_stashdb_id")
            .agg(pl.len().alias("count"))
            .filter(pl.col("count") > 1)
            .get_column("stashapp_stashdb_id")
        )
    ).sort("stashapp_stashdb_id")
    print(
        f"Number of scenes with duplicate StashDB IDs: {len(scenes_with_dupe_stashdb_ids)}"
    )


# %%
grouped_scenes = scenes_with_dupe_stashdb_ids.group_by("stashapp_stashdb_id").agg(
    [pl.col("stashapp_id").alias("scene_ids"), pl.col("stashapp_title").alias("titles")]
)

grouped_scenes = grouped_scenes
grouped_scenes


# %%
# Merge scenes with same StashDB ID
for group in grouped_scenes.iter_rows(named=True):
    stashdb_id = group["stashapp_stashdb_id"]
    scene_ids = group["scene_ids"]
    titles = group["titles"]

    print(f"\nProcessing group with StashDB ID: {stashdb_id}")
    print(f"Scene titles: {titles[0]}")  # All titles should be the same
    print(f"Scene IDs: {scene_ids}")

    # Get full scene data for each ID in the group
    scenes = [stash.find_scene(str(scene_id)) for scene_id in scene_ids]
    if not scenes:
        raise ValueError(f"No scenes found for IDs: {scene_ids}")

    if len(scenes) < 1:
        raise ValueError(f"No scenes found for IDs: {scene_ids}")

    if len(scenes) < 2:
        raise ValueError(f"Only one scene found for IDs: {scene_ids}")

    # Sort scenes by ID to determine source and destination
    sorted_scene_ids = [
        str(scene_id) for scene_id in sorted([int(scene["id"]) for scene in scenes])
    ]
    destination_scene_id = sorted_scene_ids[0]
    source_scene_ids = sorted_scene_ids[1:]

    print(f"Merging scenes {source_scene_ids} into {destination_scene_id}")

    # Compare and merge the scenes
    merged_scene = compare_and_merge_scenes(scenes)

    # Prepare the merge input
    scene_merge_input = {
        "source": source_scene_ids,
        "destination": destination_scene_id,
        "values": {
            "id": destination_scene_id,
            "title": merged_scene["title"],
            "code": merged_scene["code"],
            "details": merged_scene["details"],
            "director": merged_scene["director"],
            "urls": merged_scene["urls"],
            "date": merged_scene["date"],
            "rating100": merged_scene["rating100"],
            "o_counter": merged_scene["o_counter"],
            "organized": merged_scene["organized"],
            "gallery_ids": (
                merged_scene["gallery_ids"]
                if "gallery_ids" in merged_scene
                and merged_scene["gallery_ids"] is not None
                else []
            ),
            "performer_ids": merged_scene["performer_ids"],
            "tag_ids": merged_scene["tag_ids"],
            "stash_ids": merged_scene["stash_ids"],
            "play_duration": merged_scene["play_duration"],
            "play_count": merged_scene["play_count"],
        },
        "play_history": True,
        "o_history": True,
    }

    # Execute the merge
    try:
        query = """
        mutation SceneMerge($merge_input: SceneMergeInput!) {
            sceneMerge(input: $merge_input) {
                id
            }
        }
        """

        result = stash.call_GQL(query, {"merge_input": scene_merge_input})
        print(f"Successfully merged scenes: {result}")
    except Exception as e:
        print(f"Error merging scenes: {e}")

    print("-" * 80)

# %%
