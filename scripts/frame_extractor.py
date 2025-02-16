import os
import json
import time
import shutil
import threading
from pathlib import Path
import ffmpeg
from typing import Dict
from libraries.scene_states import SceneState

class FrameExtractor:
    def __init__(self, base_dir: str, max_per_drive: int = 2):
        self.base_dir = Path(base_dir)
        self.max_per_drive = max_per_drive
        self.drive_semaphores = {}
        
    def process_scene(self, scene_id: str, scene_data: Dict):
        video_path = scene_data['video_path']
        drive = os.path.splitdrive(video_path)[0].upper()
        
        print(f"Processing scene {scene_id} from drive {drive}")
        
        # Get/create semaphore for this drive
        if drive not in self.drive_semaphores:
            self.drive_semaphores[drive] = threading.Semaphore(self.max_per_drive)
        
        with self.drive_semaphores[drive]:
            try:
                # Move to extracting state
                scene_dir = self.base_dir / 'scenes' / SceneState.EXTRACTING_FRAMES.value / scene_id
                os.makedirs(scene_dir, exist_ok=True)
                
                print(f"Extracting frames to {scene_dir}")
                
                # Extract frames
                (
                    ffmpeg
                    .input(video_path, skip_frame='nokey')
                    .filter('select', 'not(mod(n,10))')
                    .output(
                        str(scene_dir / 'frame_%04d.jpg'),
                        qscale=3,
                        vsync=0,
                        threads=10
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
                # Move to frames extracted state
                target_dir = self.base_dir / 'scenes' / SceneState.FRAMES_EXTRACTED.value / scene_id
                shutil.move(str(scene_dir), str(target_dir))
                
                print(f"Completed processing scene {scene_id}")
                
            except Exception as e:
                print(f"Error processing scene {scene_id}: {str(e)}")
                # Move to failed state
                failed_dir = self.base_dir / 'scenes' / SceneState.FAILED.value / scene_id
                os.makedirs(failed_dir, exist_ok=True)
                with open(failed_dir / 'error.txt', 'w') as f:
                    f.write(str(e))
                if scene_dir.exists():
                    shutil.rmtree(scene_dir)

    def run(self):
        print(f"Starting frame extractor (monitoring {self.base_dir / 'scenes' / SceneState.PENDING.value})")
        while True:
            try:
                # Check pending directory for new scenes
                pending_dir = self.base_dir / 'scenes' / SceneState.PENDING.value
                if not pending_dir.exists():
                    print(f"Creating pending directory: {pending_dir}")
                    os.makedirs(pending_dir, exist_ok=True)
                
                for json_file in pending_dir.glob('*.json'):
                    try:
                        print(f"Found new scene to process: {json_file}")
                        with open(json_file, 'r') as f:
                            scene_data = json.load(f)
                        scene_id = json_file.stem
                        
                        # Process the scene
                        self.process_scene(scene_id, scene_data)
                        
                        # Remove the JSON file
                        json_file.unlink()
                        
                    except Exception as e:
                        print(f"Error processing {json_file}: {e}")
                
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