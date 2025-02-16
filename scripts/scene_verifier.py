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
            
            # Create verified scene directory
            verified_dir = self.base_dir / 'scenes' / SceneState.VERIFIED.value / scene_id
            os.makedirs(verified_dir, exist_ok=True)
            
            # Move the entire directory structure
            shutil.move(str(scene_dir), str(verified_dir))
            
            # Update metadata
            self.metadata['processed_scenes'][scene_id] = {
                'status': SceneState.VERIFIED.value,
                'verified': True,
                'verification_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            self.save_metadata()
            
            print(f"Scene {scene_id} verified and moved to {SceneState.VERIFIED.value}")
            
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