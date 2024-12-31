import json
import polars as pl
from libraries.performer_matcher import PerformerMatcher

def test_performer_matcher():
    # Load sample data
    with open('tests/data/performer_matcher.sample01.json', 'r') as f:
        sample_data = json.load(f)
    
    # Modify one performer name to test context matching
    sample_data[0]['ce_downloads_performers'][1]['name'] = 'Charlie D'  # Changed from "Charlie Dean"
        
    # Convert sample data to polars DataFrame
    df = pl.DataFrame({
        'ce_downloads_performers': [sample_data[0]['ce_downloads_performers']],
        'stashapp_performers': [sample_data[0]['stashapp_performers']]
    })
    
    # Create matcher
    matcher = PerformerMatcher()
    
    # Run matching
    matches = matcher.match_performers(
        df['ce_downloads_performers'],
        df['stashapp_performers']
    )
    
    # Verify matches
    assert len(matches) == 2, "Should find matches for both performers"
    
    # Check Sybil match (should be high confidence)
    sybil_match = next(m for m in matches if m.ce_name == "Sybil")
    assert sybil_match.stashapp_name == "Sybil A"
    assert sybil_match.confidence >= 0.9, "Should be high confidence match"
    
    # Check Charlie Dean match (should be context-boosted)
    charlie_match = next(m for m in matches if m.ce_name == "Charlie D")
    assert charlie_match.stashapp_name == "Charlie Dean"
    assert "boosted by scene context" in charlie_match.reason, "Should indicate context boost from Sybil match"
    assert 0.65 <= charlie_match.confidence < 0.9, "Should have boosted but not high confidence"
    
    # Test custom field generation
    custom_fields = matcher.get_stashapp_custom_fields(sybil_match)
    assert len(custom_fields) == 1
    assert custom_fields[0]['key'].startswith('CultureExtractor.')
    assert custom_fields[0]['value'] == sybil_match.ce_uuid
    
    # Test match formatting
    formatted = matcher.format_match_for_review(sybil_match)
    assert "CE: Sybil" in formatted
    assert "Stashapp: Sybil A" in formatted
    assert str(sybil_match.stashapp_id) in formatted
    assert sybil_match.stashdb_uuid in formatted
