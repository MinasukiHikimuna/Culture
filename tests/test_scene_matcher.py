import json
import pytest
from libraries.scene_matcher import SceneMatcher

class TestSceneMatcher:
    @pytest.fixture
    def matcher(self):
        return SceneMatcher()
    
    @pytest.fixture
    def sample_data(self):
        with open("phash_to_scene.sample.json") as f:
            data = json.load(f)
        return data["input_scenes"], data["results"]["data"]["findScenesByFullFingerprints"]
    
    def test_exact_phash_match(self, matcher, sample_data):
        input_scenes, stashdb_scenes = sample_data
        # Test with a known exact match from your data
        result = matcher.match_scenes([input_scenes[0]], [stashdb_scenes[0]])
        assert result[input_scenes[0]["phash"]] is not None
    
    def test_close_phash_match(self, matcher):
        # Test with slightly different phashes
        input_scene = {"phash": "f85c3c1c1c1c1c1c", "duration": 300}
        stashdb_scene = {
            "fingerprints": [{"algorithm": "PHASH", "hash": "f85c3c1c1c1c1c1d"}],
            "duration": 301
        }
        result = matcher.match_scenes([input_scene], [stashdb_scene])
        assert result[input_scene["phash"]] is not None
    
    def test_duration_mismatch(self, matcher):
        # Test that scenes with matching phash but very different durations don't match
        input_scene = {"phash": "f85c3c1c1c1c1c1c", "duration": 300}
        stashdb_scene = {
            "fingerprints": [{"algorithm": "PHASH", "hash": "f85c3c1c1c1c1c1c"}],
            "duration": 500  # >10% difference
        }
        result = matcher.match_scenes([input_scene], [stashdb_scene])
        assert result[input_scene["phash"]] is None 