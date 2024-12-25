from dataclasses import dataclass
from typing import Optional, Dict, List

@dataclass
class SceneMatcher:
    MAX_DISTANCE: int = 16
    MAX_DURATION_DIFF_PCT: float = 10.0

    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """Calculate the Hamming distance between two hex strings."""
        bin1 = bin(int(hash1, 16))[2:].zfill(64)
        bin2 = bin(int(hash2, 16))[2:].zfill(64)
        return sum(b1 != b2 for b1, b2 in zip(bin1, bin2))

    def match_scenes(self, input_scenes: List[Dict], stashdb_scenes: List[Dict]) -> Dict[str, Optional[Dict]]:
        """
        Match input scenes to StashDB scenes using phash and duration.
        
        Args:
            input_scenes: List of scene dicts with 'phash' and optional 'duration'
            stashdb_scenes: List of StashDB scene results with 'fingerprints' and 'duration'
            
        Returns:
            Dictionary mapping input phash to matching StashDB scene (or None if no match)
        """
        phash_to_scene = {}
        
        for input_scene in input_scenes:
            matching_scene = None
            min_distance = float('inf')
            min_duration_diff = float('inf')
            input_duration = input_scene.get('duration')
            
            for stashdb_scene in stashdb_scenes:
                for fingerprint in stashdb_scene["fingerprints"]:
                    if fingerprint["algorithm"] == "PHASH":
                        distance = self._hamming_distance(input_scene["phash"], fingerprint["hash"])
                        
                        # Calculate duration difference percentage if both durations exist
                        stashdb_duration = stashdb_scene.get('duration')
                        duration_diff_pct = float('inf')
                        
                        if input_duration and stashdb_duration:
                            duration_diff_pct = abs(input_duration - stashdb_duration) / input_duration * 100
                        
                        # Only consider matches within both phash and duration thresholds
                        if distance <= self.MAX_DISTANCE and duration_diff_pct <= self.MAX_DURATION_DIFF_PCT:
                            # Update match if:
                            # 1. This is the closest phash match yet, or
                            # 2. Equal phash distance but better duration match
                            if (distance < min_distance or 
                                (distance == min_distance and duration_diff_pct < min_duration_diff)):
                                min_distance = distance
                                min_duration_diff = duration_diff_pct
                                matching_scene = stashdb_scene
            
            phash_to_scene[input_scene["phash"]] = matching_scene
            
        return phash_to_scene 