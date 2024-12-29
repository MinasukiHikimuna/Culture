from dataclasses import dataclass
from typing import Optional, Dict, List

@dataclass
class SceneMatcher:
    MAX_DISTANCE: int = 16
    MAX_DURATION_DIFF_SECS: int = 60

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
                scene_duration = stashdb_scene.get('duration')
                
                for fingerprint in stashdb_scene["fingerprints"]:
                    if fingerprint["algorithm"] == "PHASH":
                        distance = self._hamming_distance(input_scene["phash"], fingerprint["hash"])
                        
                        if distance > self.MAX_DISTANCE:
                            continue
                            
                        fingerprint_duration = fingerprint.get('duration')
                        duration_diff = float('inf')
                        scene_duration_diff = float('inf')
                        
                        if input_duration and fingerprint_duration:
                            duration_diff = abs(input_duration - fingerprint_duration)
                            
                        if input_duration and scene_duration:
                            scene_duration_diff = abs(input_duration - scene_duration)
                        
                        if duration_diff > self.MAX_DURATION_DIFF_SECS:
                            continue
                            
                        # Update match if:
                        # 1. This is the closest phash match yet, or
                        # 2. Equal phash distance but scene duration matches better
                        if (distance < min_distance or
                            (distance == min_distance and scene_duration_diff < min_duration_diff)):
                            min_distance = distance
                            min_duration_diff = scene_duration_diff
                            matching_scene = stashdb_scene
            
            phash_to_scene[input_scene["phash"]] = matching_scene
            
        return phash_to_scene 