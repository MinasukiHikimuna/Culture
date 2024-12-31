import json
import polars as pl
from libraries.performer_matcher import PerformerMatcher

def test_performer_matcher():
    # Load sample data
    with open("tests/data/performer_matcher.sample01.json", "r") as f:
        sample01 = json.load(f)
    with open("tests/data/performer_matcher.sample02.json", "r") as f:
        sample02 = json.load(f)
        
    # Create test data for all known Stashapp performers
    all_stashapp_performers = pl.DataFrame({
        "stashapp_id": [1, 2],
        "stashapp_name": ["Jill Kassidy", "Ryan Driller"],
        "stashapp_gender": ["FEMALE", "MALE"],
        "stashapp_stash_ids": [
            [{"endpoint": "https://stashdb.org/graphql", "stash_id": "c853319b-60af-437c-94a2-63b29d8389b6"}],
            [{"endpoint": "https://stashdb.org/graphql", "stash_id": "8a07a611-fc9d-402c-bd9d-54f501dadd21"}]
        ]
    })
    
    # Test case 1: Scene with Stashapp performers (sample01)
    # Modify Charlie Dean's name to test scene context boosting
    ce_performers = sample01[0]["ce_downloads_performers"]
    for perf in ce_performers:
        if perf["name"] == "Charlie Dean":
            perf["name"] = "Charlie D"  # Use partial name
            
    df = pl.DataFrame([{
        "ce_downloads_performers": ce_performers,
        "stashapp_performers": sample01[0]["stashapp_performers"],
        "stashdb_performers": None
    }])
    
    matcher = PerformerMatcher(all_stashapp_performers)
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )
    
    # Verify matches from Stashapp scene
    assert len(matches) == 2, "Should find matches for both performers"
    sybil_match = next(m for m in matches if m.ce_name == "Sybil")
    assert sybil_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert sybil_match.source == "stashapp_scene", "Should be matched from scene performers"
    
    charlie_match = next(m for m in matches if m.ce_name == "Charlie D")
    assert charlie_match.confidence >= 0.75, "Should have boosted confidence from scene context"
    assert charlie_match.source == "stashapp_scene", "Should be matched from scene performers"
    assert "boosted by scene context" in charlie_match.reason
    
    # Test case 2: Scene with empty Stashapp performers but StashDB data (sample02)
    df = pl.DataFrame([{
        "ce_downloads_performers": sample02[0]["ce_downloads_performers"],
        "stashapp_performers": None,
        "stashdb_performers": [
            {
                "as": None,
                "performer": {
                    "id": "c853319b-60af-437c-94a2-63b29d8389b6",
                    "name": "Jill Kassidy",
                    "aliases": ["Jill", "Jill Cassidy"],
                    "gender": "FEMALE"
                }
            },
            {
                "as": None,
                "performer": {
                    "id": "8a07a611-fc9d-402c-bd9d-54f501dadd21",
                    "name": "Ryan Driller",
                    "aliases": ["Adam Driller", "Jeremy Bilding", "Ryan"],
                    "gender": "MALE"
                }
            }
        ]
    }])
    
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )
    
    # Verify matches from StashDB
    assert len(matches) == 2, "Should find matches for both performers"
    jill_match = next(m for m in matches if m.ce_name == "Jill Kassidy")
    assert jill_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert jill_match.source == "stashdb_scene", "Should be matched from StashDB performers"
    assert jill_match.stashdb_uuid == "c853319b-60af-437c-94a2-63b29d8389b6"
    
    ryan_match = next(m for m in matches if m.ce_name == "Ryan Driller")
    assert ryan_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert ryan_match.source == "stashdb_scene", "Should be matched from StashDB performers"
    assert ryan_match.stashdb_uuid == "8a07a611-fc9d-402c-bd9d-54f501dadd21"
    
    # Test case 3: Scene with no performers but match from all known Stashapp performers
    df = pl.DataFrame([{
        "ce_downloads_performers": sample02[0]["ce_downloads_performers"],
        "stashapp_performers": None,
        "stashdb_performers": None
    }])
    
    matches = matcher.match_performers(
        df["ce_downloads_performers"],
        df["stashapp_performers"],
        df["stashdb_performers"]
    )
    
    # Verify matches from all known performers
    assert len(matches) == 2, "Should find matches for both performers"
    jill_match = next(m for m in matches if m.ce_name == "Jill Kassidy")
    assert jill_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert jill_match.source == "stashapp_all", "Should be matched from all known performers"
    assert jill_match.stashapp_id == 1
    
    ryan_match = next(m for m in matches if m.ce_name == "Ryan Driller")
    assert ryan_match.confidence >= 0.9, "Should have high confidence for exact name match"
    assert ryan_match.source == "stashapp_all", "Should be matched from all known performers"
    assert ryan_match.stashapp_id == 2
    
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
