from typing import List, Dict, Optional, Tuple
import difflib

class PerformerMatcher:
    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize a name for comparison"""
        return name.lower().strip()

    @staticmethod
    def _calculate_name_similarity(name1: str, name2: str) -> float:
        """Calculate similarity score between two names"""
        return difflib.SequenceMatcher(None, 
                                     PerformerMatcher._normalize_name(name1),
                                     PerformerMatcher._normalize_name(name2)).ratio()

    @staticmethod
    def _check_alias_match(ce_name: str, stashdb_performer: Dict) -> Tuple[bool, float]:
        """Check if name matches any aliases"""
        if 'aliases' not in stashdb_performer['performer']:
            return False, 0.0
            
        for alias in stashdb_performer['performer']['aliases']:
            similarity = PerformerMatcher._calculate_name_similarity(ce_name, alias)
            if similarity > 0.9:  # High confidence threshold for aliases
                return True, similarity
        return False, 0.0

    @staticmethod
    def _match_performer(ce_performer: Dict, stashdb_performers: List[Dict]) -> Optional[Dict]:
        """
        Match a single Culture Extractor performer to StashDB performer
        
        Args:
            ce_performer: Culture Extractor performer dict
            stashdb_performers: List of StashDB performers
            
        Returns:
            Matched StashDB performer or None if no match
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
        
        if best_score > 0.8:  # Confidence threshold
            return best_match
        return None

    @staticmethod
    def match_all_performers(culture_extractor_performers: List[Dict], stashdb_performers: List[Dict]) -> List[Tuple[Dict, Optional[Dict]]]:
        """
        Match all performers between Culture Extractor and StashDB
        
        Args:
            culture_extractor_performers: List of performers from Culture Extractor
            stashdb_performers: List of performers from StashDB
            
        Returns:
            List of tuples containing (CE performer, matched StashDB performer or None)
        """
        return [(ce_performer, PerformerMatcher._match_performer(ce_performer, stashdb_performers))
                for ce_performer in culture_extractor_performers]
