import json
import os
import pytest
from pathlib import Path
from libraries.scene_matcher import SceneMatcher

class TestSceneMatcher:
    @pytest.fixture
    def matcher(self):
        return SceneMatcher()
    
    @pytest.fixture
    def sample_data(self):
        """Load test data from sample JSON file"""
        test_dir = Path(__file__).parent
        sample_path = test_dir / "data" / "phash_to_scene.sample.json"
        with open(sample_path) as f:
            data = json.load(f)
        return data["input_scenes"], data["results"]["data"]["findScenesByFullFingerprints"]
    
    # There are multiple results with the phash 870f040525ef8bfe. That phash should match to the scene with the ID 9d73eca2-569e-4c59-99b6-95543e4e678e.    
    def test_scene_matcher(self, matcher, sample_data):
        input_scenes, stashdb_scenes = sample_data
        result = matcher.match_scenes(input_scenes, stashdb_scenes)
        expected_scene = next(scene for scene in stashdb_scenes if scene["id"] == "9d73eca2-569e-4c59-99b6-95543e4e678e")
        assert result["870f040525ef8bfe"] == expected_scene
