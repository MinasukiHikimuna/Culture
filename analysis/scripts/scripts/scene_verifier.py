import os


os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # Suppress TF logging

import json
import shutil
import time
from pathlib import Path

from libraries.scene_states import DatasetStructure, SceneState


class SceneVerifier:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

        # Initialize dataset structure
        self.dataset = DatasetStructure(base_dir)

    def is_scene_ready_for_verification(self, scene_dir: Path) -> bool:
        """Check if all faces have been sorted into performer directories"""
        # Get all jpg files in the scene directory
        face_files = list(scene_dir.glob("*.jpg"))

        # If there are any face files left in root, scene is not ready
        if face_files:
            return False

        # Check that at least one performer directory has faces
        has_sorted_faces = False
        for subdir in scene_dir.iterdir():
            if subdir.is_dir() and subdir.name != "unknown":
                if list(subdir.glob("*.jpg")):
                    has_sorted_faces = True
                    break

        return has_sorted_faces

    def verify_scene(self, scene_id: str, scene_dir: Path):
        """Process a verified scene and move it to final state"""
        # Check if already verified
        if self.dataset.is_scene_processed(scene_id) and \
           self.dataset.info["processed_scenes"][scene_id] == SceneState.VERIFIED.value:
            print(f"Skipping {scene_id} - already verified")
            return

        try:
            print(f"Verifying scene {scene_id}")

            # Load scene metadata
            metadata_path = self.dataset.scene_data / f"{scene_id}.json"
            if not metadata_path.exists():
                raise ValueError(f"No metadata found for scene {scene_id}")

            with metadata_path.open("r") as f:
                scene_data = json.load(f)

            # Create verified scene directory
            verified_dir = self.dataset.scenes[SceneState.VERIFIED.value] / scene_id
            verified_dir.mkdir(parents=True, exist_ok=True)

            # Move faces to performer directories
            performers_dir = self.base_dir / "performers" / "verified"

            for subdir in scene_dir.iterdir():
                if not subdir.is_dir() or subdir.name == "unknown":
                    continue

                # subdir.name should be like "d5061b46-796b-4204-8e4f-cff4569fdea6 - Alexis Crystal"
                performer_dir = performers_dir / subdir.name
                performer_dir.mkdir(parents=True, exist_ok=True)

                # Move all faces to performer directory
                for face_file in subdir.glob("*.jpg"):
                    target_path = performer_dir / face_file.name
                    shutil.move(str(face_file), str(target_path))

            # Move unknown faces to verified scene directory
            unknown_dir = scene_dir / "unknown"
            if unknown_dir.exists():
                shutil.move(str(unknown_dir), str(verified_dir / "unknown"))

            # Clean up original directory
            shutil.rmtree(scene_dir)

            # Update scene state after successful verification
            self.dataset.update_scene_state(scene_id, SceneState.VERIFIED)

            print(f"Scene {scene_id} verified and faces moved to performer directories")

        except Exception as e:
            print(f"Error verifying scene {scene_id}: {str(e)}")

    def run(self):
        print(f"Starting scene verifier (monitoring {self.dataset.scenes[SceneState.FACES_EXTRACTED.value]})")
        while True:
            try:
                # Check for scenes with sorted faces
                faces_dir = self.dataset.scenes[SceneState.FACES_EXTRACTED.value]

                for scene_dir in faces_dir.iterdir():
                    if not scene_dir.is_dir():
                        continue

                    scene_id = scene_dir.name
                    if self.is_scene_ready_for_verification(scene_dir):
                        self.verify_scene(scene_id, scene_dir)

                time.sleep(1)  # Wait before checking again

            except KeyboardInterrupt:
                print("Shutting down scene verifier")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    verifier = SceneVerifier("H:\\Faces\\dataset")
    verifier.run()