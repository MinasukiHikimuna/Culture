import json
import os
from pathlib import Path
from libraries.scene_matcher import SceneMatcher

def load_sample_data(filename: str):
    """Load test data from sample JSON file"""
    test_dir = Path(__file__).parent
    sample_path = test_dir / "data" / filename
    with open(sample_path) as f:
        data = json.load(f)
    return data["input_scenes"], data["results"]["data"]["findScenesByFullFingerprints"]

def test_scene_matcher_sample01():
    # There are multiple results with the phash 870f040525ef8bfe
    # That phash should match to the scene with the ID 9d73eca2-569e-4c59-99b6-95543e4e678e
    matcher = SceneMatcher()
    input_scenes, stashdb_scenes = load_sample_data("phash_to_scene.sample01.json")
    result = matcher.match_scenes(input_scenes, stashdb_scenes)
    expected_scene = next(scene for scene in stashdb_scenes if scene["id"] == "9d73eca2-569e-4c59-99b6-95543e4e678e")
    assert result["870f040525ef8bfe"] == expected_scene

def test_scene_matcher_sample02():
    # There are multiple results with the phash e796ec4d1b40a28f. Most matches have different duration so we need to filter out the ones with different duration.
    matcher = SceneMatcher()
    input_scenes, stashdb_scenes = load_sample_data("phash_to_scene.sample02.json")
    result = matcher.match_scenes(input_scenes, stashdb_scenes)
    expected_scene = next(scene for scene in stashdb_scenes if scene["id"] == "005c612f-ea44-4c8b-8e7b-bf5f840de147")
    assert result["e796ec4d1b40a28f"] == expected_scene
