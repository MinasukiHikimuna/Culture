import json
import os
from pathlib import Path
from typing import Dict, List

from libraries.client_stashapp import StashAppClient, get_stashapp_client
from libraries.scene_states import SceneState


def get_stashdb_performer(performer):
    """Extract StashDB ID and name from performer data"""
    for stash_id in performer["stashapp_performers_stash_ids"]:
        if stash_id["endpoint"] == "https://stashdb.org/graphql":
            return {
                "stash_id": stash_id["stash_id"],
                "name": performer["stashapp_performers_name"]
            }
    return None

def prepare_scenes_for_performer(performer_name: str, base_dir: str, exclude_vr: bool = True):
    """
    Prepare scene JSON files for a performer's scenes.
    Returns the number of scenes queued.
    """
    stash = get_stashapp_client()
    stash_client = StashAppClient()

    # Get performer
    all_performers = stash_client.get_performers()
    performer = all_performers.filter(
        pl.col("stashapp_name").str.contains(performer_name)
    ).to_dicts()[0]

    # Get scenes
    query = {
        "performers": {
            "value": [performer["stashapp_id"]],
            "excludes": [],
            "modifier": "INCLUDES"
        }
    }

    if exclude_vr:
        vr_tag = stash.find_tag("Virtual Reality")["id"]
        query["tags"] = {
            "value": [],
            "excludes": [vr_tag],
            "modifier": "INCLUDES"
        }

    scenes = stash_client.find_scenes(query)

    # Check which scenes are already in any state directory
    processed_scenes = set()
    base_path = Path(base_dir) / "scenes"
    for state_dir in base_path.glob("*"):
        if state_dir.is_dir():
            processed_scenes.update(os.listdir(state_dir))

    # Filter out processed scenes
    unprocessed_scenes = scenes.filter(
        ~pl.col("stashapp_stashdb_id").is_in(processed_scenes)
    )

    # Create pending directory
    pending_dir = base_path / SceneState.PENDING.value
    pending_dir.mkdir(parents=True, exist_ok=True)

    # Queue scenes
    scenes_queued = 0
    for scene in unprocessed_scenes.to_dicts():
        performers = []
        for perf in scene["stashapp_performers"]:
            stashdb_info = get_stashdb_performer(perf)
            if stashdb_info:
                performers.append(f"{stashdb_info['stash_id']} - {stashdb_info['name']}")

        if performers:
            scene_id = scene["stashapp_stashdb_id"]
            scene_data = {
                "video_path": scene["stashapp_primary_file_path"],
                "performers": performers
            }

            json_path = pending_dir / f"{scene_id}.json"
            with open(json_path, "w") as f:
                json.dump(scene_data, f, indent=2)
            scenes_queued += 1

    return {
        "total_scenes": len(scenes),
        "already_processed": len(processed_scenes),
        "newly_queued": scenes_queued
    }