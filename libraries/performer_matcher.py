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
    source: str  # Where the match came from: "stashapp_scene", "stashdb_scene", or "stashapp_all"

class PerformerMatcher:
    def __init__(self, all_stashapp_performers: Optional[pl.DataFrame] = None):
        self.matches: List[PerformerMatch] = []
        self.all_stashapp_performers = all_stashapp_performers
        
    def match_performers(self, 
                        ce_performers: pl.Series, 
                        stashapp_performers: pl.Series,
                        stashdb_performers: Optional[pl.Series] = None) -> List[PerformerMatch]:
        """
        Match performers between Culture Extractor and Stashapp/StashDB
        
        Args:
            ce_performers: Series of Culture Extractor performers (List[struct])
            stashapp_performers: Series of Stashapp performers (List[struct])
            stashdb_performers: Optional Series of StashDB performers (List[struct])
            
        Returns:
            List of PerformerMatch objects
        """
        matches = []
        
        # Iterate through each row (scene)
        for ce_list, stashapp_list, stashdb_list in zip(
            ce_performers, 
            stashapp_performers, 
            stashdb_performers if stashdb_performers is not None else [None] * len(ce_performers)
        ):
            if ce_list is None or len(ce_list) == 0:
                continue
                
            scene_matches = []
            remaining_ce = list(ce_list)
            
            # First try: Match with scene's Stashapp performers
            if stashapp_list is not None and len(stashapp_list) > 0:
                scene_matches.extend(
                    self._match_scene_performers(remaining_ce, stashapp_list, "stashapp_scene")
                )
                # Remove matched performers
                matched_uuids = {m.ce_uuid for m in scene_matches}
                remaining_ce = [p for p in remaining_ce if p["uuid"] not in matched_uuids]
            
            # Second try: Match remaining with StashDB performers if available
            if remaining_ce and stashdb_list is not None and len(stashdb_list) > 0:
                # Convert StashDB performers to Stashapp format for matching
                stashdb_performers_converted = [
                    {
                        "stashapp_performers_id": -1,  # Placeholder
                        "stashapp_performers_name": p["performer"]["name"],
                        "stashapp_performers_alias_list": p["performer"].get("aliases", []) + ([p["as"]] if p["as"] else []),  # Include both aliases and "as" name
                        "stashapp_performers_gender": p["performer"]["gender"],
                        "stashapp_performers_stash_ids": [
                            {
                                "endpoint": "https://stashdb.org/graphql",
                                "stash_id": p["performer"]["id"],
                                "updated_at": None
                            }
                        ]
                    }
                    for p in stashdb_list
                ]
                
                stashdb_matches = self._match_scene_performers(
                    remaining_ce, 
                    stashdb_performers_converted,
                    "stashdb_scene"
                )
                scene_matches.extend(stashdb_matches)
                # Remove matched performers
                matched_uuids = {m.ce_uuid for m in scene_matches}
                remaining_ce = [p for p in remaining_ce if p["uuid"] not in matched_uuids]
            
            # Third try: Match remaining with all known Stashapp performers
            if remaining_ce and self.all_stashapp_performers is not None:
                all_performers_list = [
                    {
                        "stashapp_performers_id": row["stashapp_id"],
                        "stashapp_performers_name": row["stashapp_name"],
                        "stashapp_performers_alias_list": row["stashapp_alias_list"],
                        "stashapp_performers_gender": row["stashapp_gender"],
                        "stashapp_performers_stash_ids": row["stashapp_stash_ids"]
                    }
                    for row in self.all_stashapp_performers.iter_rows(named=True)
                ]
                
                global_matches = self._match_scene_performers(
                    remaining_ce, 
                    all_performers_list,
                    "stashapp_all",
                    min_confidence=0.9  # Higher threshold for global matches
                )
                scene_matches.extend(global_matches)
            
            matches.extend(scene_matches)
            
        # Deduplicate matches
        unique_matches = self._deduplicate_matches(matches)
        self.matches = unique_matches
        return unique_matches
    
    def _match_scene_performers(self, 
                              ce_performers: List[Dict], 
                              stashapp_performers: List[Dict],
                              source: str,
                              min_confidence: float = 0.65) -> List[PerformerMatch]:
        """Match performers within a single scene"""
        matches = []
        remaining_ce = list(ce_performers)
        remaining_stash = list(stashapp_performers)
        
        # First pass: Find high confidence matches
        high_conf_matches = []
        
        for ce_perf in ce_performers:
            match = self._find_best_match(ce_perf, remaining_stash, source)
            if match and match.confidence >= 0.9:  # High confidence threshold for first pass
                high_conf_matches.append(match)
                # Remove matched performer from remaining list
                remaining_stash = [p for p in remaining_stash 
                                 if (source == "stashdb_scene" and p["stashapp_performers_stash_ids"][0]["stash_id"] != match.stashdb_uuid) or
                                    (source != "stashdb_scene" and p["stashapp_performers_id"] != match.stashapp_id)]
                remaining_ce = [p for p in remaining_ce 
                              if p["uuid"] != match.ce_uuid]
        
        # Second pass: Use scene context to match remaining performers
        if high_conf_matches and remaining_ce:
            for ce_perf in remaining_ce:
                match = self._find_best_match(
                    ce_perf, 
                    remaining_stash,
                    source,
                    context_confidence_boost=0.15  # Boost confidence if we have other matches
                )
                if match and match.confidence >= min_confidence:
                    match.reason += f" (boosted by scene context with {', '.join(m.ce_name for m in high_conf_matches)})"
                    high_conf_matches.append(match)
                    remaining_stash = [p for p in remaining_stash 
                                     if (source == "stashdb_scene" and p["stashapp_performers_stash_ids"][0]["stash_id"] != match.stashdb_uuid) or
                                        (source != "stashdb_scene" and p["stashapp_performers_id"] != match.stashapp_id)]
        
        return high_conf_matches

    def _find_best_match(self, 
                        ce_perf: Dict, 
                        stashapp_performers: List[Dict],
                        source: str,
                        context_confidence_boost: float = 0.0) -> Optional[PerformerMatch]:
        """Find the best matching Stashapp performer for a CE performer"""
        best_match = None
        best_confidence = 0.0
        
        for stash_perf in stashapp_performers:
            # Get StashDB UUID from stash_ids
            stashdb_uuid = None
            for stash_id in stash_perf["stashapp_performers_stash_ids"]:
                if stash_id["endpoint"] == "https://stashdb.org/graphql":
                    stashdb_uuid = stash_id["stash_id"]
                    break
            
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
                stashapp_id = stash_perf["stashapp_performers_id"]
                stashapp_name = stash_perf["stashapp_performers_name"]
                if source == "stashdb_scene" and stashapp_id == -1 and self.all_stashapp_performers is not None and stashdb_uuid:
                    for row in self.all_stashapp_performers.iter_rows(named=True):
                        for stash_id in row["stashapp_stash_ids"]:
                            if (stash_id["endpoint"] == "https://stashdb.org/graphql" and 
                                stash_id["stash_id"] == stashdb_uuid):
                                stashapp_id = row["stashapp_id"]
                                stashapp_name = row["stashapp_name"]
                                break

                best_match = PerformerMatch(
                    ce_uuid=ce_perf["uuid"],
                    ce_name=ce_perf["name"],
                    stashapp_id=stashapp_id,
                    stashapp_name=stashapp_name,
                    stashdb_uuid=stashdb_uuid or "",
                    stashdb_name=stash_perf["stashapp_performers_name"],  # Use Stashapp name as fallback
                    confidence=confidence,
                    reason=reason,
                    source=source
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
            f"Source: {match.source}\n"
            f"Reason: {match.reason}\n"
        )