import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF logging

import json
import time
import shutil
from pathlib import Path
import cv2
from mtcnn import MTCNN
import tensorflow as tf
from libraries.scene_states import SceneState, DatasetStructure

class FaceDetector:
    def __init__(self, base_dir: str, max_concurrent: int = 4):
        self.base_dir = Path(base_dir)
        self.detector = MTCNN()
        self.max_concurrent = max_concurrent
        
        # Initialize dataset structure
        self.dataset = DatasetStructure(base_dir)
        
        # Enable GPU growth
        physical_devices = tf.config.list_physical_devices('GPU')
        if physical_devices:
            tf.config.experimental.set_memory_growth(physical_devices[0], True)
        
        # Create all required directories
        for state in SceneState:
            os.makedirs(self.base_dir / 'scenes' / state.value, exist_ok=True)
    
    def process_scene(self, scene_id: str):
        # Check current state
        if self.dataset.is_scene_processed(scene_id) and \
           self.dataset.info['processed_scenes'][scene_id] in [
               SceneState.FACES_EXTRACTED.value,
               SceneState.VERIFIED.value
           ]:
            print(f"Skipping {scene_id} - already processed faces")
            return
        
        try:
            # Load scene data from permanent storage
            metadata_path = self.base_dir / 'metadata' / 'scenes' / f"{scene_id}.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    scene_data = json.load(f)
                    performers = scene_data.get('performers', [])
            else:
                print(f"Warning: No metadata found for scene {scene_id}")
                performers = []
            
            # Move to extracting faces state
            source_dir = self.base_dir / 'scenes' / SceneState.FRAMES_EXTRACTED.value / scene_id
            working_dir = self.base_dir / 'scenes' / SceneState.EXTRACTING_FACES.value / scene_id
            shutil.move(str(source_dir), str(working_dir))
            
            # Create output directory structure
            output_dir = self.base_dir / 'scenes' / SceneState.FACES_EXTRACTED.value / scene_id
            os.makedirs(output_dir, exist_ok=True)  # Faces will go directly here
            
            # Create performer directories for manual sorting
            for performer in performers:
                performer_dir = output_dir / performer
                os.makedirs(performer_dir, exist_ok=True)
            
            # Create unknown directory
            os.makedirs(output_dir / 'unknown', exist_ok=True)
            
            print(f"Processing scene {scene_id}")
            
            # Process frames
            faces_extracted = 0
            for frame_file in working_dir.glob('*.jpg'):
                frame = cv2.imread(str(frame_file))
                if frame is None:
                    continue
                
                faces = self.detector.detect_faces(frame)
                for face_idx, face in enumerate(faces):
                    if face['confidence'] < 0.95:
                        continue
                    
                    x, y, width, height = face['box']
                    margin = int(max(width, height) * 0.2)
                    face_img = frame[
                        max(0, y-margin):min(frame.shape[0], y+height+margin),
                        max(0, x-margin):min(frame.shape[1], x+width+margin)
                    ]
                    
                    face_id = f"{scene_id}_{frame_file.stem}_face_{face_idx}"
                    face_path = output_dir / f"{face_id}.jpg"  # Save directly to scene directory
                    cv2.imwrite(str(face_path), face_img)
                    faces_extracted += 1
            
            print(f"Completed scene {scene_id} - extracted {faces_extracted} faces")
            
            # Clean up frames
            shutil.rmtree(working_dir)
            
            # Update scene state after successful processing
            self.dataset.update_scene_state(scene_id, SceneState.FACES_EXTRACTED)
            
        except Exception as e:
            print(f"Error processing scene {scene_id}: {str(e)}")
            # Move to failed state
            failed_dir = self.base_dir / 'scenes' / SceneState.FAILED.value / scene_id
            os.makedirs(failed_dir, exist_ok=True)
            with open(failed_dir / 'error.txt', 'w') as f:
                f.write(str(e))
            if working_dir.exists():
                shutil.rmtree(working_dir)
    
    def run(self):
        print(f"Starting face detector (monitoring {self.base_dir / 'scenes' / SceneState.FRAMES_EXTRACTED.value})")
        while True:
            try:
                # Check for scenes with extracted frames
                frames_dir = self.base_dir / 'scenes' / SceneState.FRAMES_EXTRACTED.value
                for scene_dir in frames_dir.iterdir():
                    if scene_dir.is_dir():
                        self.process_scene(scene_dir.name)
            
                time.sleep(1)  # Wait before checking again
            
            except KeyboardInterrupt:
                print("Shutting down face detector")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    detector = FaceDetector("H:\\Faces\\dataset")
    detector.run() 