from typing import List, Dict, Optional, Tuple, NamedTuple
import difflib

class PerformerMatch(NamedTuple):
    """Represents a match between Culture Extractor and StashDB performers"""
    culture_extractor: Dict
    stashdb: Optional[Dict]
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
    def _match_performer(ce_performer: Dict, stashdb_performers: List[Dict]) -> PerformerMatch:
        """
        Match a single Culture Extractor performer to StashDB performer
        
        Args:
            ce_performer: Culture Extractor performer dict
            stashdb_performers: List of StashDB performers
            
        Returns:
            PerformerMatch with matched StashDB performer and confidence score
        """
        best_match = None
        best_score = 0.0
        
        ce_name = ce_performer['name']
        
        for stashdb_entry in stashdb_performers:
            stashdb_performer = stashdb_entry['performer']
            
            # Check exact name match
            name_similarity = PerformerMatcher._calculate_name_similarity(ce_name, stashdb_performer['name'])
            
            # Check alias matches
            alias_match, alias_score = PerformerMatcher._check_alias_match(ce_name, stashdb_entry)
            
            # Use the higher score between name and alias matches
            score = max(name_similarity, alias_score)
            
            if score > best_score:
                best_score = score
                best_match = stashdb_entry
        
        return PerformerMatch(
            culture_extractor=ce_performer,
            stashdb=best_match if best_score > 0.5 else None,  # Lower threshold but return None for very low confidence
            confidence=best_score
        )

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
        return [PerformerMatcher._match_performer(ce_performer, stashdb_performers)
                for ce_performer in culture_extractor_performers]
