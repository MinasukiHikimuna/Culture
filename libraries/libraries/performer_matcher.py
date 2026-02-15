from dataclasses import dataclass
from typing import Optional

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

@dataclass
class UnmatchedPerformerMatch:
    ce_uuid: str  # Culture Extractor UUID
    ce_name: str  # Culture Extractor name
    stashapp_id: int  # Stashapp ID
    stashapp_name: str  # Stashapp name
    confidence: float  # Match confidence score
    reason: str  # Reason for the match/confidence

class PerformerMatcher:
    def __init__(self, all_stashapp_performers: Optional[pl.DataFrame] = None):
        self.matches: list[PerformerMatch] = []
        self.all_stashapp_performers = all_stashapp_performers

    def match_performers(self,
                        ce_performers: pl.Series,
                        stashapp_performers: pl.Series,
                        stashdb_performers: Optional[pl.Series] = None) -> list[PerformerMatch]:
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
                # Convert StashDB performers to a format for matching
                stashdb_performers_converted = []
                for p in stashdb_list:
                    performer = p["performer"]
                    stashdb_performers_converted.append({
                        "id": performer["id"],
                        "name": performer["name"],
                        "aliases": performer.get("aliases", []) + ([p["as"]] if p["as"] else []),
                        "gender": performer["gender"]
                    })

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
                              ce_performers: list[dict],
                              performers: list[dict],
                              source: str,
                              min_confidence: float = 0.65) -> list[PerformerMatch]:
        """Match performers within a single scene"""
        matches = []
        remaining_ce = list(ce_performers)
        remaining_performers = list(performers)

        # First pass: Find high confidence matches
        high_conf_matches = []

        for ce_perf in ce_performers:
            match = self._find_best_match(ce_perf, remaining_performers, source)
            if match and match.confidence >= 0.9:  # High confidence threshold for first pass
                high_conf_matches.append(match)
                # Remove matched performer from remaining list
                if source == "stashdb_scene":
                    remaining_performers = [p for p in remaining_performers
                                         if p["id"] != match.stashdb_uuid]
                else:
                    remaining_performers = [p for p in remaining_performers
                                         if p["stashapp_performers_id"] != match.stashapp_id]
                remaining_ce = [p for p in remaining_ce
                              if p["uuid"] != match.ce_uuid]

        # Second pass: Use scene context to match remaining performers
        if high_conf_matches and remaining_ce:
            for ce_perf in remaining_ce:
                match = self._find_best_match(
                    ce_perf,
                    remaining_performers,
                    source,
                    context_confidence_boost=0.15  # Boost confidence if we have other matches
                )
                if match and match.confidence >= min_confidence:
                    match.reason += f" (boosted by scene context with {', '.join(m.ce_name for m in high_conf_matches)})"
                    high_conf_matches.append(match)
                    if source == "stashdb_scene":
                        remaining_performers = [p for p in remaining_performers
                                             if p["id"] != match.stashdb_uuid]
                    else:
                        remaining_performers = [p for p in remaining_performers
                                             if p["stashapp_performers_id"] != match.stashapp_id]

        return high_conf_matches

    def _find_best_match(self,
                        ce_perf: dict,
                        performers: list[dict],
                        source: str,
                        context_confidence_boost: float = 0.0) -> Optional[PerformerMatch]:
        """Find the best matching performer for a CE performer"""
        best_match = None
        best_confidence = 0.0

        for perf in performers:
            # Calculate match confidence based on source
            if source == "stashdb_scene":
                confidence, reason = self._calculate_match_confidence(
                    ce_perf["name"],
                    perf["name"],
                    perf["aliases"]
                )
            else:  # stashapp_scene or stashapp_all
                confidence, reason = self._calculate_match_confidence(
                    ce_perf["name"],
                    perf["stashapp_performers_name"],
                    perf["stashapp_performers_alias_list"]
                )

            # Apply context boost if provided
            confidence += context_confidence_boost
            confidence = min(confidence, 1.0)  # Cap at 1.0

            if confidence > best_confidence:
                if source == "stashdb_scene":
                    stashdb_uuid = perf["id"]
                    stashdb_name = perf["name"]
                    stashapp_id = -1
                    stashapp_name = ""

                    # Try to find matching Stashapp performer
                    if self.all_stashapp_performers is not None:
                        for row in self.all_stashapp_performers.iter_rows(named=True):
                            for stash_id in row["stashapp_stash_ids"]:
                                if (stash_id["endpoint"] == "https://stashdb.org/graphql" and
                                    stash_id["stash_id"] == stashdb_uuid):
                                    stashapp_id = row["stashapp_id"]
                                    stashapp_name = row["stashapp_name"]
                                    break
                else:
                    stashapp_id = perf["stashapp_performers_id"]
                    stashapp_name = perf["stashapp_performers_name"]
                    stashdb_uuid = ""
                    stashdb_name = ""
                    # Get StashDB UUID from stash_ids if available
                    for stash_id in perf["stashapp_performers_stash_ids"]:
                        if stash_id["endpoint"] == "https://stashdb.org/graphql":
                            stashdb_uuid = stash_id["stash_id"]
                            stashdb_name = perf["stashapp_performers_name"]
                            break

                best_match = PerformerMatch(
                    ce_uuid=ce_perf["uuid"],
                    ce_name=ce_perf["name"],
                    stashapp_id=stashapp_id,
                    stashapp_name=stashapp_name,
                    stashdb_uuid=stashdb_uuid,
                    stashdb_name=stashdb_name,
                    confidence=confidence,
                    reason=reason,
                    source=source
                )
                best_confidence = confidence

        return best_match if best_match and best_confidence >= 0.65 else None

    def _calculate_match_confidence(self,
                                  ce_name: str,
                                  stash_name: str,
                                  aliases: list[str]) -> tuple[float, str]:
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

    def _deduplicate_matches(self, matches: list[PerformerMatch]) -> list[PerformerMatch]:
        """Remove duplicate matches, keeping highest confidence match for each CE UUID"""
        unique_matches = {}

        for match in matches:
            if match.ce_uuid not in unique_matches or \
               match.confidence > unique_matches[match.ce_uuid].confidence:
                unique_matches[match.ce_uuid] = match

        return list(unique_matches.values())

    def get_stashapp_custom_fields(self, match: PerformerMatch) -> list[dict[str, str]]:
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

    def match_unmatched_performers(self, unmatched_performers: pl.DataFrame) -> list[UnmatchedPerformerMatch]:
        """
        Try to match previously unmatched performers against all Stashapp performers

        Args:
            unmatched_performers: DataFrame with columns 'performer_uuid' and 'performer_name'

        Returns:
            List of UnmatchedPerformerMatch objects for any new matches found
        """
        if self.all_stashapp_performers is None:
            return []

        matches = []

        # Convert all Stashapp performers to list format for matching
        all_performers_list = [
            {
                "stashapp_performers_id": row["stashapp_id"],
                "stashapp_performers_name": row["stashapp_name"],
                "stashapp_performers_alias_list": row["stashapp_alias_list"],
            }
            for row in self.all_stashapp_performers.iter_rows(named=True)
        ]

        # Try to match each unmatched performer
        for row in unmatched_performers.iter_rows(named=True):
            ce_performer = {
                "uuid": row["performer_uuid"],
                "name": row["performer_name"]
            }

            best_match = None
            best_confidence = 0.5  # Minimum confidence threshold for unmatched performers

            for perf in all_performers_list:
                confidence, reason = self._calculate_match_confidence(
                    ce_performer["name"],
                    perf["stashapp_performers_name"],
                    perf["stashapp_performers_alias_list"]
                )

                if confidence > best_confidence:
                    best_match = UnmatchedPerformerMatch(
                        ce_uuid=ce_performer["uuid"],
                        ce_name=ce_performer["name"],
                        stashapp_id=perf["stashapp_performers_id"],
                        stashapp_name=perf["stashapp_performers_name"],
                        confidence=confidence,
                        reason=reason
                    )
                    best_confidence = confidence

            if best_match:
                matches.append(best_match)

        return matches

    def format_unmatched_match_for_review(self, match: UnmatchedPerformerMatch) -> str:
        """Format an unmatched performer match for manual review"""
        return (
            f"CE: {match.ce_name} ({match.ce_uuid})\n"
            f"Stashapp: {match.stashapp_name} (ID: {match.stashapp_id})\n"
            f"Confidence: {match.confidence:.2f}\n"
            f"Reason: {match.reason}\n"
        )