from dataclasses import dataclass
from typing import List, Optional, Dict
import polars as pl

@dataclass
class PerformerMatch:
    ce_uuid: str  # Culture Extractor UUID
    ce_name: str  # Culture Extractor name
    stashapp_id: int  # Stashapp ID
    stashapp_name: str  # Stashapp name
    stashdb_uuid: str  # StashDB UUID
    stashdb_name: str  # StashDB name
    confidence: float  # Match confidence score
    reason: str  # Reason for the match/confidence

class PerformerMatcher:
    def __init__(self):
        self.matches: List[PerformerMatch] = []
        
    def match_performers(self, 
                        ce_performers: pl.Series, 
                        stashapp_performers: pl.Series) -> List[PerformerMatch]:
        """
        Match performers between Culture Extractor and Stashapp/StashDB
        
        Args:
            ce_performers: Series of Culture Extractor performers (List[struct])
            stashapp_performers: Series of Stashapp performers (List[struct])
            
        Returns:
            List of PerformerMatch objects
        """
        matches = []
        
        # Iterate through each row (scene)
        for ce_list, stashapp_list in zip(ce_performers, stashapp_performers):
            if ce_list is None or stashapp_list is None or len(ce_list) == 0 or len(stashapp_list) == 0:
                continue
                
            # First pass: Find high confidence matches
            high_conf_matches = []
            remaining_ce = []
            remaining_stash = list(stashapp_list)
            
            for ce_perf in ce_list:
                match = self._find_best_match(ce_perf, remaining_stash)
                if match and match.confidence >= 0.9:  # High confidence threshold for first pass
                    high_conf_matches.append(match)
                    # Remove matched performer from remaining list
                    remaining_stash = [p for p in remaining_stash 
                                     if p["stashapp_performers_id"] != match.stashapp_id]
                else:
                    remaining_ce.append(ce_perf)
            
            # Second pass: Use scene context to match remaining performers
            if high_conf_matches and remaining_ce:
                for ce_perf in remaining_ce:
                    match = self._find_best_match(
                        ce_perf, 
                        remaining_stash,
                        context_confidence_boost=0.15  # Boost confidence if we have other matches
                    )
                    if match and match.confidence >= 0.65:  # Lower threshold for context-boosted matches
                        match.reason += f" (boosted by scene context with {', '.join(m.ce_name for m in high_conf_matches)})"
                        high_conf_matches.append(match)
                        remaining_stash = [p for p in remaining_stash 
                                         if p["stashapp_performers_id"] != match.stashapp_id]
            
            matches.extend(high_conf_matches)
            
        # Deduplicate matches
        unique_matches = self._deduplicate_matches(matches)
        self.matches = unique_matches
        return unique_matches
    
    def _find_best_match(self, 
                        ce_perf: Dict, 
                        stashapp_performers: List[Dict],
                        context_confidence_boost: float = 0.0) -> Optional[PerformerMatch]:
        """Find the best matching Stashapp performer for a CE performer"""
        best_match = None
        best_confidence = 0.0
        
        for stash_perf in stashapp_performers:
            # Get StashDB UUID from stash_ids
            stashdb_uuid = None
            stashdb_name = None
            for stash_id in stash_perf["stashapp_performers_stash_ids"]:
                if stash_id["endpoint"] == "https://stashdb.org/graphql":
                    stashdb_uuid = stash_id["stash_id"]
                    break
            
            if not stashdb_uuid:
                continue
            
            # Calculate match confidence
            confidence, reason = self._calculate_match_confidence(
                ce_perf["name"],
                stash_perf["stashapp_performers_name"],
                stash_perf["stashapp_performers_alias_list"]
            )
            
            # Apply context boost if provided
            confidence += context_confidence_boost
            confidence = min(confidence, 1.0)  # Cap at 1.0
            
            if confidence > best_confidence:
                best_match = PerformerMatch(
                    ce_uuid=ce_perf["uuid"],
                    ce_name=ce_perf["name"],
                    stashapp_id=stash_perf["stashapp_performers_id"],
                    stashapp_name=stash_perf["stashapp_performers_name"],
                    stashdb_uuid=stashdb_uuid,
                    stashdb_name=stashdb_name,
                    confidence=confidence,
                    reason=reason
                )
                best_confidence = confidence
        
        return best_match if best_match and best_confidence >= 0.65 else None
    
    def _calculate_match_confidence(self,
                                  ce_name: str,
                                  stash_name: str,
                                  aliases: List[str]) -> tuple[float, str]:
        """Calculate match confidence between performer names"""
        # Normalize names
        ce_name = ce_name.lower().strip()
        stash_name = stash_name.lower().strip()
        aliases = [alias.lower().strip() for alias in aliases]
        
        # Exact name match
        if ce_name == stash_name:
            return 1.0, "Exact name match"
            
        # Alias match
        if ce_name in aliases:
            return 0.95, f"Exact alias match: {ce_name}"
            
        # Partial name match
        if ce_name in stash_name or stash_name in ce_name:
            # If one name is fully contained in the other
            if ce_name in stash_name:
                shorter, longer = ce_name, stash_name
            else:
                shorter, longer = stash_name, ce_name
                
            # Calculate what portion of the longer name matches
            ratio = len(shorter) / len(longer)
            confidence = 0.6 + (ratio * 0.1)  # Score between 0.6 and 0.7
            return confidence, f"Partial name match: {ce_name} vs {stash_name}"
            
        # Partial alias match
        for alias in aliases:
            if ce_name in alias or alias in ce_name:
                if ce_name in alias:
                    shorter, longer = ce_name, alias
                else:
                    shorter, longer = alias, ce_name
                    
                ratio = len(shorter) / len(longer)
                confidence = 0.5 + (ratio * 0.1)  # Score between 0.5 and 0.6
                return confidence, f"Partial alias match: {ce_name} vs {alias}"
                
        return 0.0, "No match"
    
    def _deduplicate_matches(self, matches: List[PerformerMatch]) -> List[PerformerMatch]:
        """Remove duplicate matches, keeping highest confidence match for each CE UUID"""
        unique_matches = {}
        
        for match in matches:
            if match.ce_uuid not in unique_matches or \
               match.confidence > unique_matches[match.ce_uuid].confidence:
                unique_matches[match.ce_uuid] = match
                
        return list(unique_matches.values())
    
    def get_stashapp_custom_fields(self, match: PerformerMatch) -> List[Dict[str, str]]:
        """Generate Stashapp custom fields for a match"""
        return [
            {
                "key": f"CultureExtractor.{match.ce_name.lower().replace(' ', '')}",
                "value": match.ce_uuid
            }
        ]
    
    def format_match_for_review(self, match: PerformerMatch) -> str:
        """Format a match for manual review"""
        return (
            f"CE: {match.ce_name} ({match.ce_uuid})\n"
            f"Stashapp: {match.stashapp_name} (ID: {match.stashapp_id})\n"
            f"StashDB: {match.stashdb_uuid}\n"
            f"Confidence: {match.confidence:.2f}\n"
            f"Reason: {match.reason}\n"
        )
