import json
import os
import time
from enum import Enum
from pathlib import Path


class SceneState(Enum):
    PENDING = "1_pending"  # JSON files waiting to be processed
    EXTRACTING_FRAMES = "2_extracting_frames"  # Currently extracting frames
    FRAMES_EXTRACTED = "3_frames_extracted"  # Frames ready for face detection
    EXTRACTING_FACES = "4_extracting_faces"  # Currently detecting faces
    FACES_EXTRACTED = "5_faces_extracted"  # Faces extracted, ready for verification
    VERIFIED = "6_verified"  # Faces have been verified and sorted
    FAILED = "7_failed"
    NO_FACES_FOUND = "8_no_faces_found"  # Add this line

class DatasetStructure:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

        # Scene processing states
        self.scenes = {state.value: self.base_dir / "scenes" / state.value
                      for state in SceneState}

        # Permanent metadata storage
        self.metadata = self.base_dir / "metadata"
        self.scene_data = self.metadata / "scenes"  # Individual scene JSON files
        self.dataset_info = self.metadata / "dataset.json"  # Global dataset info

        # Create all directories
        for dir in self.scenes.values():
            dir.mkdir(parents=True, exist_ok=True)
        self.scene_data.mkdir(parents=True, exist_ok=True)

        # Load or initialize dataset info
        self.load_dataset_info()

    def load_dataset_info(self):
        """Load or initialize dataset info tracking processed scenes"""
        if self.dataset_info.exists():
            with open(self.dataset_info, "r") as f:
                self.info = json.load(f)
        else:
            self.info = {
                "processed_scenes": {},  # scene_id -> current_state
                "last_updated": None
            }
            self.save_dataset_info()

    def save_dataset_info(self):
        """Save dataset info"""
        self.info["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.dataset_info, "w") as f:
            json.dump(self.info, f, indent=2)

    def is_scene_processed(self, scene_id: str) -> bool:
        """Check if scene has been processed before"""
        return scene_id in self.info["processed_scenes"]

    def update_scene_state(self, scene_id: str, state: SceneState):
        """Update scene's processing state"""
        self.info["processed_scenes"][scene_id] = state.value
        self.save_dataset_info()