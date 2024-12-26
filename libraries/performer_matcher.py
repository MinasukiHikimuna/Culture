from typing import List, Dict, Optional, Tuple, NamedTuple
import difflib
from dataclasses import dataclass
from operator import attrgetter

class PerformerMatch(NamedTuple):
    """Represents a match between Culture Extractor and StashDB performers"""
    culture_extractor: Dict
    stashdb: Optional[Dict]
    confidence: float

@dataclass
class PotentialMatch:
    """Internal class for tracking potential matches during matching process"""
    ce_performer: Dict
    stashdb_performer: Dict
    confidence: float

class PerformerMatcher:
    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize a name for comparison"""
        return name.lower().strip()

    @staticmethod
    def _calculate_name_similarity(name1: str, name2: str) -> float:
        """Calculate similarity score between two names"""
        # For very short names, we want to be more strict about matching
        if len(name1) <= 4 or len(name2) <= 4:
            return 1.0 if PerformerMatcher._normalize_name(name1) == PerformerMatcher._normalize_name(name2) else 0.0
            
        return difflib.SequenceMatcher(None, 
                                     PerformerMatcher._normalize_name(name1),
                                     PerformerMatcher._normalize_name(name2)).ratio()

    @staticmethod
    def _check_alias_match(ce_name: str, stashdb_performer: Dict) -> Tuple[bool, float]:
        """Check if name matches any aliases"""
        if 'aliases' not in stashdb_performer['performer']:
            return False, 0.0
            
        best_score = 0.0
        for alias in stashdb_performer['performer']['aliases']:
            similarity = PerformerMatcher._calculate_name_similarity(ce_name, alias)
            if similarity > best_score:
                best_score = similarity
                
        return best_score > 0.9, best_score

    @staticmethod
    def _find_potential_matches(ce_performer: Dict, stashdb_performers: List[Dict]) -> List[PotentialMatch]:
        """Find all potential matches for a Culture Extractor performer with confidence scores"""
        potential_matches = []
        ce_name = ce_performer['name']
        
        for stashdb_entry in stashdb_performers:
            stashdb_performer = stashdb_entry['performer']
            
            # Check exact name match
            name_similarity = PerformerMatcher._calculate_name_similarity(ce_name, stashdb_performer['name'])
            
            # Check alias matches
            alias_match, alias_score = PerformerMatcher._check_alias_match(ce_name, stashdb_entry)
            
            # Use the higher score between name and alias matches
            score = max(name_similarity, alias_score)
            
            if score > 0.5:  # Only consider matches above threshold
                potential_matches.append(PotentialMatch(ce_performer, stashdb_entry, score))
                
        return potential_matches

    @staticmethod
    def match_all_performers(culture_extractor_performers: List[Dict], stashdb_performers: List[Dict]) -> List[PerformerMatch]:
        """
        Match all performers between Culture Extractor and StashDB
        
        Args:
            culture_extractor_performers: List of performers from Culture Extractor
            stashdb_performers: List of performers from StashDB
            
        Returns:
            List of PerformerMatch objects containing match results and confidence scores
        """
        # Find all potential matches for each performer
        all_potential_matches = []
        for ce_performer in culture_extractor_performers:
            potential_matches = PerformerMatcher._find_potential_matches(ce_performer, stashdb_performers)
            all_potential_matches.extend(potential_matches)
            
        # Sort by confidence score in descending order
        all_potential_matches.sort(key=attrgetter('confidence'), reverse=True)
        
        # Track which performers have been matched
        matched_ce_performers = set()
        matched_stashdb_performers = set()
        final_matches = {}
        
        # Assign matches starting with highest confidence
        for potential_match in all_potential_matches:
            ce_id = potential_match.ce_performer['uuid']
            stashdb_id = potential_match.stashdb_performer['performer']['id']
            
            if ce_id not in matched_ce_performers and stashdb_id not in matched_stashdb_performers:
                matched_ce_performers.add(ce_id)
                matched_stashdb_performers.add(stashdb_id)
                final_matches[ce_id] = PerformerMatch(
                    culture_extractor=potential_match.ce_performer,
                    stashdb=potential_match.stashdb_performer,
                    confidence=potential_match.confidence
                )
        
        # Create final list of matches, including unmatched performers
        result = []
        for ce_performer in culture_extractor_performers:
            if ce_performer['uuid'] in final_matches:
                result.append(final_matches[ce_performer['uuid']])
            else:
                result.append(PerformerMatch(
                    culture_extractor=ce_performer,
                    stashdb=None,
                    confidence=0.0
                ))
                
        return result
