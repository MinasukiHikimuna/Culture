import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF logging

import json
import time
import shutil
from pathlib import Path
from libraries.scene_states import SceneState

class SceneVerifier:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        
        # Create all required directories
        for state in SceneState:
            os.makedirs(self.base_dir / 'scenes' / state.value, exist_ok=True)
        
        self.metadata_file = self.base_dir / 'metadata.json'
        self.load_metadata()
    
    def load_metadata(self):
        """Load or initialize metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {
                'processed_scenes': {},
                'face_entries': {},
                'verification_status': {}
            }
    
    def save_metadata(self):
        """Save metadata to file"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def is_scene_ready_for_verification(self, scene_dir: Path) -> bool:
        """Check if all faces have been sorted into performer directories"""
        # Get all jpg files in the scene directory
        face_files = list(scene_dir.glob('*.jpg'))
        
        # If there are any face files left in root, scene is not ready
        if face_files:
            return False
        
        # Check that at least one performer directory has faces
        has_sorted_faces = False
        for subdir in scene_dir.iterdir():
            if subdir.is_dir() and subdir.name != 'unknown':
                if list(subdir.glob('*.jpg')):
                    has_sorted_faces = True
                    break
        
        return has_sorted_faces
    
    def verify_scene(self, scene_id: str, scene_dir: Path):
        """Process a verified scene and move it to final state"""
        try:
            print(f"Verifying scene {scene_id}")
            
            # Load scene metadata
            metadata_path = self.base_dir / 'metadata' / 'scenes' / f"{scene_id}.json"
            if not metadata_path.exists():
                raise ValueError(f"No metadata found for scene {scene_id}")
            
            with open(metadata_path, 'r') as f:
                scene_data = json.load(f)
            
            # Create verified scene directory
            verified_dir = self.base_dir / 'scenes' / SceneState.VERIFIED.value / scene_id
            os.makedirs(verified_dir, exist_ok=True)
            
            # Move faces to performer directories
            performers_dir = self.base_dir / 'performers' / 'verified'
            
            for subdir in scene_dir.iterdir():
                if not subdir.is_dir() or subdir.name == 'unknown':
                    continue
                
                # subdir.name should be like "d5061b46-796b-4204-8e4f-cff4569fdea6 - Alexis Crystal"
                performer_dir = performers_dir / subdir.name
                os.makedirs(performer_dir, exist_ok=True)
                
                # Move all faces to performer directory
                for face_file in subdir.glob('*.jpg'):
                    target_path = performer_dir / face_file.name
                    shutil.move(str(face_file), str(target_path))
            
            # Move unknown faces to verified scene directory
            unknown_dir = scene_dir / 'unknown'
            if unknown_dir.exists():
                shutil.move(str(unknown_dir), str(verified_dir / 'unknown'))
            
            # Update metadata
            self.metadata['processed_scenes'][scene_id] = {
                'status': SceneState.VERIFIED.value,
                'verified': True,
                'verification_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            self.save_metadata()
            
            # Clean up original directory
            shutil.rmtree(scene_dir)
            
            print(f"Scene {scene_id} verified and faces moved to performer directories")
            
        except Exception as e:
            print(f"Error verifying scene {scene_id}: {str(e)}")
    
    def run(self):
        print(f"Starting scene verifier (monitoring {self.base_dir / 'scenes' / SceneState.FACES_EXTRACTED.value})")
        while True:
            try:
                # Check for scenes with sorted faces
                faces_dir = self.base_dir / 'scenes' / SceneState.FACES_EXTRACTED.value
                
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