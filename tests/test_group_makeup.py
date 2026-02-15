import json
import pytest
from libraries.GroupMakeup import GroupMakeup

@pytest.fixture
def group_makeup_tags():
    with open("tests/data/group_makeup.tags.json", "r") as f:
        return json.load(f)

@pytest.fixture
def sample_scene():
    with open("tests/data/group_makeup.sample01.json", "r") as f:
        return json.load(f)[0]

def test_get_performer_makeup(sample_scene):
    gm = GroupMakeup(tags=[])  # Tags not needed for this test
    makeup = gm.get_performer_makeup(sample_scene["performers"])
    assert makeup == "G"

def test_get_expected_group_tags_solo_female(group_makeup_tags, sample_scene):
    gm = GroupMakeup(tags=group_makeup_tags)
    expected_tags = gm.get_expected_group_tags(sample_scene["performers"])
    
    # Should recommend both "Solo" and "Solo Female" tags
    expected_tag_names = {tag["name"] for tag in expected_tags}
    assert "Solo" in expected_tag_names
    assert "Solo Female" in expected_tag_names
    assert len(expected_tags) == 2

def test_get_scene_group_makeup_issues(group_makeup_tags, sample_scene):
    gm = GroupMakeup(tags=group_makeup_tags)
    issues = gm.get_scene_group_makeup_issues(sample_scene)
    
    assert issues is not None
    assert issues["scene_id"] == 2
    assert "Missing tags: Solo, Solo Female" in issues["issues"]
    assert len(issues["expected_tags"]) == 2
    assert len(issues["actual_group_tags"]) == 0
