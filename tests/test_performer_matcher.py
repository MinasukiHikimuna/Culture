import json
import polars as pl
import pytest
from libraries.performer_matcher import PerformerMatcher

@pytest.fixture
def all_stashapp_performers():
    return pl.DataFrame({
        "stashapp_id": [1, 2],
        "stashapp_name": ["Jill Kassidy", "Ryan Driller"],
        "stashapp_gender": ["FEMALE", "MALE"],
        "stashapp_stash_ids": [
            [{"endpoint": "https://stashdb.org/graphql", "stash_id": "c853319b-60af-437c-94a2-63b29d8389b6"}],
            [{"endpoint": "https://stashdb.org/graphql", "stash_id": "8a07a611-fc9d-402c-bd9d-54f501dadd21"}]
        ],
        "stashapp_alias_list": [[], []]  # Empty alias lists for both performers
    }).with_columns(pl.col("stashapp_alias_list").cast(pl.List(pl.Utf8)))

@pytest.fixture
def sample01():
    with open("tests/data/performer_matcher.sample01.json", "r") as f:
        return json.load(f)

@pytest.fixture
def sample02():
    with open("tests/data/performer_matcher.sample02.json", "r") as f:
        return json.load(f)

@pytest.fixture
def sample03():
    with open("tests/data/performer_matcher.sample03.json", "r") as f:
        return json.load(f)

@pytest.fixture
def samples(sample01, sample02, sample03):
    return {
        "sample01": sample01,
        "sample02": sample02,
        "sample03": sample03
    }

def test_stashapp_scene_matching(all_stashapp_performers, samples):
    # Modify Charlie Dean's name to test scene context boosting
    ce_performers = samples["sample01"][0]["ce_downloads_performers"]
    for perf in ce_performers:
        if perf["name"] == "Charlie Dean":
            perf["name"] = "Charlie D"  # Use partial name

    df = pl.DataFrame([{
        "ce_downloads_performers": ce_performers,
        "stashapp_performers": samples["sample01"][0]["stashapp_performers"],
        "stashdb_performers": None
    }])

    matcher = PerformerMatcher(all_stashapp_performers)
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )

    assert len(matches) == 2, "Should find matches for both performers"

    sybil_match = next(m for m in matches if m.ce_name == "Sybil")
    assert sybil_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert sybil_match.source == "stashapp_scene", "Should be matched from scene performers"

    charlie_match = next(m for m in matches if m.ce_name == "Charlie D")
    assert charlie_match.confidence >= 0.75, "Should have boosted confidence from scene context"
    assert charlie_match.source == "stashapp_scene", "Should be matched from scene performers"
    assert "boosted by scene context" in charlie_match.reason

def test_stashdb_scene_matching(all_stashapp_performers, samples):
    df = pl.DataFrame([{
        "ce_downloads_performers": samples["sample02"][0]["ce_downloads_performers"],
        "stashapp_performers": None,
        "stashdb_performers": [
            {
                "as": None,
                "performer": {
                    "id": "c853319b-60af-437c-94a2-63b29d8389b6",
                    "name": "Jill Kassidy",
                    "disambiguation": "2016-",
                    "aliases": ["Jill", "Jill Cassidy"],
                    "gender": "FEMALE"
                }
            },
            {
                "as": None,
                "performer": {
                    "id": "8a07a611-fc9d-402c-bd9d-54f501dadd21",
                    "name": "Ryan Driller",
                    "disambiguation": "2008-",
                    "aliases": ["Adam Driller", "Jeremy Bilding", "Ryan"],
                    "gender": "MALE"
                }
            }
        ]
    }])

    matcher = PerformerMatcher(all_stashapp_performers)
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )

    assert len(matches) == 2, "Should find matches for both performers"

    jill_match = next(m for m in matches if m.ce_name == "Jill Kassidy")
    assert jill_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert jill_match.source == "stashdb_scene", "Should be matched from StashDB performers"
    assert jill_match.stashdb_uuid == "c853319b-60af-437c-94a2-63b29d8389b6"
    assert jill_match.stashapp_id != -1, "Should not have placeholder Stashapp ID"
    assert jill_match.stashapp_id == 1, "Should have valid Stashapp ID from all_stashapp_performers"
    assert jill_match.stashdb_name == "Jill Kassidy", "Should use StashDB name without disambiguation"

    ryan_match = next(m for m in matches if m.ce_name == "Ryan Driller")
    assert ryan_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert ryan_match.source == "stashdb_scene", "Should be matched from StashDB performers"
    assert ryan_match.stashdb_uuid == "8a07a611-fc9d-402c-bd9d-54f501dadd21"
    assert ryan_match.stashapp_id != -1, "Should not have placeholder Stashapp ID"
    assert ryan_match.stashdb_name == "Ryan Driller", "Should use StashDB name without disambiguation"

def test_all_known_performers_matching(all_stashapp_performers, samples):
    df = pl.DataFrame([{
        "ce_downloads_performers": samples["sample02"][0]["ce_downloads_performers"],
        "stashapp_performers": None,
        "stashdb_performers": None
    }])

    matcher = PerformerMatcher(all_stashapp_performers)
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )

    assert len(matches) == 2, "Should find matches for both performers"

    jill_match = next(m for m in matches if m.ce_name == "Jill Kassidy")
    assert jill_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert jill_match.source == "stashapp_all", "Should be matched from all known performers"
    assert jill_match.stashapp_id == 1

    ryan_match = next(m for m in matches if m.ce_name == "Ryan Driller")
    assert ryan_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert ryan_match.source == "stashapp_all", "Should be matched from all known performers"
    assert ryan_match.stashapp_id == 2

def test_match_utilities(all_stashapp_performers, samples):
    df = pl.DataFrame([{
        "ce_downloads_performers": samples["sample02"][0]["ce_downloads_performers"],
        "stashapp_performers": None,
        "stashdb_performers": None
    }])

    matcher = PerformerMatcher(all_stashapp_performers)
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )

    jill_match = next(m for m in matches if m.ce_name == "Jill Kassidy")

    # Test custom fields generation
    custom_fields = matcher.get_stashapp_custom_fields(jill_match)
    assert len(custom_fields) == 1
    assert custom_fields[0]["key"] == "CultureExtractor.jillkassidy"
    assert custom_fields[0]["value"] == jill_match.ce_uuid

    # Test match formatting
    formatted = matcher.format_match_for_review(jill_match)
    assert "Jill Kassidy" in formatted
    assert jill_match.ce_uuid in formatted
    assert str(jill_match.stashapp_id) in formatted
    assert jill_match.stashdb_uuid in formatted
    assert f"{jill_match.confidence:.2f}" in formatted
    assert jill_match.source in formatted
    assert jill_match.reason in formatted

def test_alias_matching(all_stashapp_performers, samples):
    df = pl.DataFrame([{
        "ce_downloads_performers": samples["sample03"][0]["ce_downloads_performers"],
        "stashapp_performers": None,
        "stashdb_performers": samples["sample03"][0]["performers"]
    }])

    matcher = PerformerMatcher(all_stashapp_performers)
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )

    assert len(matches) == 1, "Should find match for the performer"

    simona_match = matches[0]
    assert simona_match.ce_name == "Simona", "Should match the CE name"
    assert simona_match.confidence >= 0.75, "Should have good confidence for alias match"
    assert simona_match.source == "stashdb_scene", "Should be matched from StashDB performers"
    assert simona_match.stashdb_uuid == "97695d2a-4ec4-4349-8402-c171ebb9e220", "Should match to Silvie Deluxe's UUID"
    assert "alias" in simona_match.reason.lower(), "Reason should mention alias matching"

def test_all_known_performers_should_use_aliases(all_stashapp_performers):
    # Create test data with a performer that should match via alias
    df = pl.DataFrame([{
        "ce_downloads_performers": [{
            "uuid": "test-uuid",
            "name": "Jill"  # This should match "Jill Kassidy" via alias
        }],
        "stashapp_performers": None,
        "stashdb_performers": None
    }])

    # Add a performer with aliases to all_stashapp_performers
    test_performers = pl.DataFrame({
        "stashapp_id": [123],
        "stashapp_name": ["Jill Kassidy"],
        "stashapp_gender": ["FEMALE"],
        "stashapp_stash_ids": [[]],
        "stashapp_alias_list": [["Jill", "Jill K"]]  # Add alias list with correct type
    }).with_columns(pl.col("stashapp_alias_list").cast(pl.List(pl.Utf8)))

    # Combine the test performers with existing ones
    all_performers = pl.concat([all_stashapp_performers, test_performers])

    # Create the matcher with our test data
    matcher = PerformerMatcher(all_performers)
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )

    # We should find one match with high confidence
    assert len(matches) == 1
    assert matches[0].confidence > 0.9  # High confidence match via alias
    assert matches[0].stashapp_id == 123  # Should match our test performer

def test_stashdb_scene_matching_without_stashapp(all_stashapp_performers):
    """Test matching a performer from StashDB that doesn't exist in Stashapp yet"""
    df = pl.DataFrame([{
        "ce_downloads_performers": [{
            "uuid": "test-uuid",
            "name": "New Performer",
            "short_name": "1234",
            "url": "/model/profile/1234/new-performer"
        }],
        "stashapp_performers": None,
        "stashdb_performers": [
            {
                "as": None,
                "performer": {
                    "id": "new-performer-uuid",
                    "name": "New Performer",
                    "aliases": ["Alternative Name"],
                    "gender": "FEMALE"
                }
            }
        ]
    }])

    matcher = PerformerMatcher(all_stashapp_performers)  # Using existing Stashapp performers without the new one
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )

    assert len(matches) == 1, "Should find the match from StashDB"

    match = matches[0]
    assert match.source == "stashdb_scene", "Should be matched from StashDB performers"
    assert match.stashdb_uuid == "new-performer-uuid", "Should have StashDB UUID"
    assert match.stashdb_name == "New Performer", "Should have StashDB name"
    assert match.stashapp_id == -1, "Should have placeholder Stashapp ID since performer doesn't exist in Stashapp"
    assert match.stashapp_name == "", "Should have empty Stashapp name since performer doesn't exist in Stashapp"
    assert match.confidence >= 0.9, "Should have high confidence for exact name match"
