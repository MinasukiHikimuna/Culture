import json
import polars as pl
from libraries.performer_matcher import PerformerMatcher

def create_test_data(ce_performers, stashapp_performers):
    """Helper function to create test DataFrame"""
    return pl.DataFrame({
        'ce_downloads_performers': [ce_performers],
        'stashapp_performers': [stashapp_performers]
    })

def test_exact_name_match():
    """Test exact name matching"""
    # Create test data
    ce_performers = [
        {
            "uuid": "test-uuid-1",
            "name": "Sybil",
            "short_name": "1234",
            "url": "/model/1234"
        }
    ]
    
    stashapp_performers = [
        {
            "stashapp_performers_id": 157,
            "stashapp_performers_name": "Sybil A",
            "stashapp_performers_disambiguation": "",
            "stashapp_performers_alias_list": ["Sybil"],
            "stashapp_performers_gender": "FEMALE",
            "stashapp_performers_stash_ids": [
                {
                    "endpoint": "https://stashdb.org/graphql",
                    "stash_id": "test-stashdb-1",
                    "updated_at": "1970-01-01 00:00:00"
                }
            ],
            "stashapp_performers_custom_fields": []
        }
    ]
    
    df = create_test_data(ce_performers, stashapp_performers)
    matcher = PerformerMatcher()
    matches = matcher.match_performers(df['ce_downloads_performers'], df['stashapp_performers'])
    
    assert len(matches) == 1
    match = matches[0]
    assert match.ce_name == "Sybil"
    assert match.stashapp_name == "Sybil A"
    assert match.confidence >= 0.9

def test_scene_context_matching():
    """Test matching using scene context"""
    # Create test data with two performers
    ce_performers = [
        {
            "uuid": "test-uuid-1",
            "name": "Sybil",
            "short_name": "1234",
            "url": "/model/1234"
        },
        {
            "uuid": "test-uuid-2",
            "name": "Charlie D",  # Partial name
            "short_name": "5678",
            "url": "/model/5678"
        }
    ]
    
    stashapp_performers = [
        {
            "stashapp_performers_id": 157,
            "stashapp_performers_name": "Sybil A",
            "stashapp_performers_disambiguation": "",
            "stashapp_performers_alias_list": ["Sybil"],
            "stashapp_performers_gender": "FEMALE",
            "stashapp_performers_stash_ids": [
                {
                    "endpoint": "https://stashdb.org/graphql",
                    "stash_id": "test-stashdb-1",
                    "updated_at": "1970-01-01 00:00:00"
                }
            ],
            "stashapp_performers_custom_fields": []
        },
        {
            "stashapp_performers_id": 412,
            "stashapp_performers_name": "Charlie Dean",
            "stashapp_performers_disambiguation": "",
            "stashapp_performers_alias_list": ["Charlie"],
            "stashapp_performers_gender": "MALE",
            "stashapp_performers_stash_ids": [
                {
                    "endpoint": "https://stashdb.org/graphql",
                    "stash_id": "test-stashdb-2",
                    "updated_at": "1970-01-01 00:00:00"
                }
            ],
            "stashapp_performers_custom_fields": []
        }
    ]
    
    df = create_test_data(ce_performers, stashapp_performers)
    matcher = PerformerMatcher()
    matches = matcher.match_performers(df['ce_downloads_performers'], df['stashapp_performers'])
    
    assert len(matches) == 2, "Should match both performers"
    
    # Check high confidence match
    sybil_match = next(m for m in matches if m.ce_name == "Sybil")
    assert sybil_match.stashapp_name == "Sybil A"
    assert sybil_match.confidence >= 0.9
    
    # Check context-boosted match
    charlie_match = next(m for m in matches if m.ce_name == "Charlie D")
    assert charlie_match.stashapp_name == "Charlie Dean"
    assert "boosted by scene context" in charlie_match.reason
    assert 0.65 <= charlie_match.confidence < 0.9

def test_alias_matching():
    """Test matching through aliases"""
    ce_performers = [
        {
            "uuid": "test-uuid-1",
            "name": "Charles",  # This is an alias
            "short_name": "1234",
            "url": "/model/1234"
        }
    ]
    
    stashapp_performers = [
        {
            "stashapp_performers_id": 412,
            "stashapp_performers_name": "Charlie Dean",
            "stashapp_performers_disambiguation": "",
            "stashapp_performers_alias_list": ["Charles", "Charlie"],
            "stashapp_performers_gender": "MALE",
            "stashapp_performers_stash_ids": [
                {
                    "endpoint": "https://stashdb.org/graphql",
                    "stash_id": "test-stashdb-1",
                    "updated_at": "1970-01-01 00:00:00"
                }
            ],
            "stashapp_performers_custom_fields": []
        }
    ]
    
    df = create_test_data(ce_performers, stashapp_performers)
    matcher = PerformerMatcher()
    matches = matcher.match_performers(df['ce_downloads_performers'], df['stashapp_performers'])
    
    assert len(matches) == 1
    match = matches[0]
    assert match.ce_name == "Charles"
    assert match.stashapp_name == "Charlie Dean"
    assert match.confidence >= 0.95  # Exact alias match should have high confidence
    assert "alias match" in match.reason.lower()

def test_no_matches():
    """Test handling of no matches"""
    ce_performers = [
        {
            "uuid": "test-uuid-1",
            "name": "Completely Different Name",
            "short_name": "1234",
            "url": "/model/1234"
        }
    ]
    
    stashapp_performers = [
        {
            "stashapp_performers_id": 412,
            "stashapp_performers_name": "Charlie Dean",
            "stashapp_performers_disambiguation": "",
            "stashapp_performers_alias_list": ["Charles", "Charlie"],
            "stashapp_performers_gender": "MALE",
            "stashapp_performers_stash_ids": [
                {
                    "endpoint": "https://stashdb.org/graphql",
                    "stash_id": "test-stashdb-1",
                    "updated_at": "1970-01-01 00:00:00"
                }
            ],
            "stashapp_performers_custom_fields": []
        }
    ]
    
    df = create_test_data(ce_performers, stashapp_performers)
    matcher = PerformerMatcher()
    matches = matcher.match_performers(df['ce_downloads_performers'], df['stashapp_performers'])
    
    assert len(matches) == 0, "Should not find any matches for completely different names"

def test_custom_field_generation():
    """Test generation of custom fields"""
    ce_performers = [
        {
            "uuid": "test-uuid-1",
            "name": "Sybil",
            "short_name": "1234",
            "url": "/model/1234"
        }
    ]
    
    stashapp_performers = [
        {
            "stashapp_performers_id": 157,
            "stashapp_performers_name": "Sybil A",
            "stashapp_performers_disambiguation": "",
            "stashapp_performers_alias_list": ["Sybil"],
            "stashapp_performers_gender": "FEMALE",
            "stashapp_performers_stash_ids": [
                {
                    "endpoint": "https://stashdb.org/graphql",
                    "stash_id": "test-stashdb-1",
                    "updated_at": "1970-01-01 00:00:00"
                }
            ],
            "stashapp_performers_custom_fields": []
        }
    ]
    
    df = create_test_data(ce_performers, stashapp_performers)
    matcher = PerformerMatcher()
    matches = matcher.match_performers(df['ce_downloads_performers'], df['stashapp_performers'])
    
    assert len(matches) == 1
    match = matches[0]
    
    custom_fields = matcher.get_stashapp_custom_fields(match)
    assert len(custom_fields) == 1
    assert custom_fields[0]['key'] == "CultureExtractor.sybil"
    assert custom_fields[0]['value'] == "test-uuid-1"
