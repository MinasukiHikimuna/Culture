import json
import os
from libraries.performer_matcher import PerformerMatcher

def load_test_data():
    """Load test data from sample files"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    with open(os.path.join(current_dir, 'data/culture_extractor_stashdb_performers.sample01.json')) as f:
        data = json.load(f)
        return data['culture_extractor_performers'], data['stashdb_performers']

def test_match_all_performers():
    """Test matching all performers"""
    ce_performers, stashdb_performers = load_test_data()
    
    matches = PerformerMatcher.match_all_performers(ce_performers, stashdb_performers)
    
    # Should match all 3 performers in sample data
    assert len(matches) == 3
    
    # Test Kyler Quinn exact match
    kyler = next(match for match in matches if match[0]['name'] == 'Kyler Quinn')
    assert kyler[1] is not None
    assert kyler[1]['performer']['name'] == 'Kyler Quinn'
    
    # Test Robby Echo alias match
    robby = next(match for match in matches if match[0]['name'] == 'Robby Echo')
    assert robby[1] is not None
    assert 'Robby Echo' in robby[1]['performer']['aliases']
    
    # Test Anna Claire Clouds match
    anna = next(match for match in matches if match[0]['name'] == 'Anna Claire Clouds')
    assert anna[1] is not None
    assert anna[1]['performer']['name'] == 'Anna Claire Clouds'
