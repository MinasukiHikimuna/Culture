import json
import os
from libraries.performer_matcher import PerformerMatcher

def load_test_data(sample_file):
    """Load test data from sample files"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    with open(os.path.join(current_dir, f'data/{sample_file}')) as f:
        data = json.load(f)
        return data['culture_extractor_performers'], data['stashdb_performers']

def test_match_all_performers_sample01():
    """Test matching all performers from sample01"""
    ce_performers, stashdb_performers = load_test_data('culture_extractor_stashdb_performers.sample01.json')
    
    matches = PerformerMatcher.match_all_performers(ce_performers, stashdb_performers)
    
    # Should match all 3 performers in sample data
    assert len(matches) == 3
    assert all(match.stashdb is not None for match in matches)
    
    # Test Kyler Quinn exact match
    kyler = next(match for match in matches if match.culture_extractor['name'] == 'Kyler Quinn')
    assert kyler.stashdb['performer']['name'] == 'Kyler Quinn'
    assert kyler.confidence > 0.95  # Should be very high confidence for exact match
    
    # Test Robby Echo alias match
    robby = next(match for match in matches if match.culture_extractor['name'] == 'Robby Echo')
    assert 'Robby Echo' in robby.stashdb['performer']['aliases']
    assert robby.confidence > 0.9  # High confidence for alias match
    
    # Test Anna Claire Clouds match
    anna = next(match for match in matches if match.culture_extractor['name'] == 'Anna Claire Clouds')
    assert anna.stashdb['performer']['name'] == 'Anna Claire Clouds'
    assert anna.confidence > 0.95  # Should be very high confidence for exact match

def test_match_all_performers_sample02():
    """Test matching performers with short names from sample02"""
    ce_performers, stashdb_performers = load_test_data('culture_extractor_stashdb_performers.sample02.json')
    
    matches = PerformerMatcher.match_all_performers(ce_performers, stashdb_performers)
    
    # Should match both performers in sample data
    assert len(matches) == 2
    assert all(match.stashdb is not None for match in matches)
    
    # Test Paula match (matches to Paula Shy)
    paula = next(match for match in matches if match.culture_extractor['name'] == 'Paula')
    assert paula.stashdb['performer']['name'] == 'Paula Shy'
    assert paula.confidence > 0.5  # Should match with lower confidence due to short name
    
    # Test Dan match (matches through alias)
    dan = next(match for match in matches if match.culture_extractor['name'] == 'Dan')
    assert dan.stashdb['performer']['name'] == 'Daniel G'
    assert 'Dan' in dan.stashdb['performer']['aliases']
    assert dan.confidence > 0.9  # High confidence for exact alias match
