from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime

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
        """
        phash_to_scene = {}
        
        for input_scene in input_scenes:
            matching_scene = None
            min_distance = float("inf")
            max_quality_score = 0.0  # Higher score = better match
            input_duration = input_scene.get("duration")
            
            for stashdb_scene in stashdb_scenes:
                phash_fingerprints = [f for f in stashdb_scene["fingerprints"] 
                                    if f["algorithm"] == "PHASH"]
                
                # Calculate quality score for this scene
                quality_score = 0
                min_scene_distance = float("inf")
                
                for fingerprint in phash_fingerprints:
                    distance = self._hamming_distance(input_scene["phash"], fingerprint["hash"])
                    min_scene_distance = min(min_scene_distance, distance)
                    
                    # Only consider fingerprints within MAX_DISTANCE
                    if distance <= self.MAX_DISTANCE:
                        fingerprint_duration = fingerprint.get("duration")
                        duration_diff = float("inf")
                        
                        if input_duration and fingerprint_duration:
                            duration_diff = abs(input_duration - fingerprint_duration)
                        
                        if duration_diff <= self.MAX_DURATION_DIFF_SECS:
                            # Weight the fingerprint based on how close it matches
                            # Distance 0 = weight 1.0
                            # Distance MAX_DISTANCE = weight close to 0
                            weight = 1.0 - (distance / (self.MAX_DISTANCE + 1))
                            quality_score += weight
                
                # Normalize quality score by number of fingerprints
                if phash_fingerprints:
                    quality_score = quality_score / len(phash_fingerprints)
                    
                    # Update match if:
                    # 1. This is the closest phash match yet, or
                    # 2. Equal min distance but better quality score
                    if (min_scene_distance < min_distance or
                        (min_scene_distance == min_distance and quality_score > max_quality_score)):
                        min_distance = min_scene_distance
                        max_quality_score = quality_score
                        matching_scene = stashdb_scene
            
            phash_to_scene[input_scene["phash"]] = matching_scene
            
        return phash_to_scene 