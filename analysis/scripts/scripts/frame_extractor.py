import json
import os
import shutil
import threading
import time
from pathlib import Path

import ffmpeg

from libraries.scene_states import DatasetStructure, SceneState


class FrameExtractor:
    def __init__(self, base_dir: str, max_per_drive: int = 2):
        self.base_dir = Path(base_dir)
        self.max_per_drive = max_per_drive
        self.drive_semaphores = {}

        # Initialize dataset structure
        self.dataset = DatasetStructure(base_dir)

    def process_scene(self, scene_id: str, scene_data: dict):
        # Check if already processed
        if self.dataset.is_scene_processed(scene_id):
            print(f"Skipping {scene_id} - already processed")
            return

        # Store scene metadata permanently
        with (self.dataset.scene_data / f"{scene_id}.json").open("w") as f:
            json.dump(scene_data, f, indent=2)

        video_path = scene_data["video_path"]
        drive = os.path.splitdrive(video_path)[0].upper()

        print(f"[{drive}] {scene_id}: Starting frame extraction...")

        # Get/create semaphore for this drive
        if drive not in self.drive_semaphores:
            self.drive_semaphores[drive] = threading.Semaphore(self.max_per_drive)

        with self.drive_semaphores[drive]:
            try:
                # Move to extracting state
                scene_dir = self.dataset.scenes[SceneState.EXTRACTING_FRAMES.value] / scene_id
                scene_dir.mkdir(parents=True, exist_ok=True)

                # Extract frames
                (
                    ffmpeg
                    .input(video_path, skip_frame="nokey")
                    .filter("select", "not(mod(n,10))")
                    .output(
                        str(scene_dir / "frame_%04d.jpg"),
                        qscale=3,
                        vsync=0,
                        threads=10
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )

                # Move to frames extracted state
                target_dir = self.dataset.scenes[SceneState.FRAMES_EXTRACTED.value] / scene_id
                shutil.move(str(scene_dir), str(target_dir))

                print(f"[{drive}] {scene_id}: Completed frame extraction")

                # Update scene state after successful processing
                self.dataset.update_scene_state(scene_id, SceneState.FRAMES_EXTRACTED)

            except Exception as e:
                print(f"[{drive}] {scene_id}: Failed - {str(e)}")
                # Move to failed state
                failed_dir = self.dataset.scenes[SceneState.FAILED.value] / scene_id
                failed_dir.mkdir(parents=True, exist_ok=True)
                with (failed_dir / "error.txt").open("w") as f:
                    f.write(str(e))
                if scene_dir.exists():
                    shutil.rmtree(scene_dir)

    def run(self):
        print(f"Starting frame extractor (monitoring {self.dataset.scenes[SceneState.PENDING.value]})")
        while True:
            try:
                # Check for pending scenes with JSON data
                pending_dir = self.dataset.scenes[SceneState.PENDING.value]
                for json_file in pending_dir.glob("*.json"):
                    scene_id = json_file.stem

                    # Load scene data
                    with json_file.open("r") as f:
                        scene_data = json.load(f)

                    # Process the scene
                    self.process_scene(scene_id, scene_data)

                    # Remove JSON file after processing
                    json_file.unlink()

                time.sleep(1)  # Wait before checking again

            except KeyboardInterrupt:
                print("Shutting down frame extractor")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    extractor = FrameExtractor("H:\\Faces\\dataset")
    extractor.run()
