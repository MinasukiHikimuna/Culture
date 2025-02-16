import os
import json
import shutil
from datetime import datetime
from mtcnn import MTCNN
import cv2
from typing import Dict, List, Union
import ffmpeg

class FaceDatasetBuilder:
    def __init__(self):
        self.detector = MTCNN()
        self.base_dir = "H:\\Faces\\dataset"
        self.structure = {
            'temp': os.path.join(self.base_dir, 'temp'),
            'unverified': os.path.join(self.base_dir, 'unverified'),
        }
        self.metadata_file = os.path.join(self.base_dir, 'metadata.json')
        self.setup_directories()
        self.load_metadata()

    def setup_directories(self):
        """Create necessary directory structure"""
        for dir_path in self.structure.values():
            os.makedirs(dir_path, exist_ok=True)

    def get_performer_directory_name(self, performer: Union[Dict, str]) -> str:
        """Create directory name from performer data or ID"""
        if isinstance(performer, str):
            return performer
        
        stashdb_id = None
        for stash_id in performer.get('stashapp_performers_stash_ids', []):
            if stash_id['endpoint'] == 'https://stashdb.org/graphql':
                stashdb_id = stash_id['stash_id']
                break
        
        name = performer.get('stashapp_performers_name', '')
        if stashdb_id:
            return f"{stashdb_id} - {name}"
        return name

    def process_scene(self, video_path: str, scene_id: str, performers: List[Union[Dict, str]]):
        """Process a single scene and extract faces"""
        print(f"\nProcessing scene: {scene_id}")
        
        # Create scene-specific directories
        scene_dir = os.path.join(self.structure['unverified'], scene_id)
        scene_temp_dir = os.path.join(self.structure['temp'], scene_id)
        frames_dir = os.path.join(scene_temp_dir, 'frames')
        
        # Check if scene was already processed
        if os.path.exists(scene_dir):
            print(f"Scene {scene_id} already processed, skipping...")
            return
        
        # Create necessary directories
        os.makedirs(frames_dir, exist_ok=True)
        os.makedirs(scene_dir, exist_ok=True)

        # Create performer directories under scene directory
        for performer in performers:
            dir_name = self.get_performer_directory_name(performer)
            performer_dir = os.path.join(scene_dir, dir_name)
            print(f"Creating performer directory: {performer_dir}")
            os.makedirs(performer_dir, exist_ok=True)

        # Create rejected directory
        rejected_dir = os.path.join(scene_dir, 'rejected')
        os.makedirs(rejected_dir, exist_ok=True)

        try:
            # Extract frames
            output_pattern = os.path.join(frames_dir, 'frame_%04d.png')
            (
                ffmpeg
                .input(video_path)
                .filter('fps', fps=1/24)
                .output(output_pattern)
                .run()
            )

            # Process frames and extract faces
            faces_metadata = []
            for frame_file in os.listdir(frames_dir):
                if not frame_file.endswith('.png'):
                    continue

                frame_path = os.path.join(frames_dir, frame_file)
                image = cv2.imread(frame_path)
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                faces = self.detector.detect_faces(image_rgb)
                
                for i, face in enumerate(faces):
                    if face['confidence'] < 0.95:
                        continue

                    face_id = f"{scene_id}_{frame_file[:-4]}_face_{i}"
                    
                    # Save face with margin
                    x, y, width, height = face['box']
                    margin = int(max(width, height) * 0.2)
                    face_img = image[
                        max(0, y-margin):min(image.shape[0], y+height+margin),
                        max(0, x-margin):min(image.shape[1], x+width+margin)
                    ]
                    
                    # Save face directly to scene directory
                    face_path = os.path.join(scene_dir, f"{face_id}.jpg")
                    cv2.imwrite(face_path, face_img)

                    faces_metadata.append({
                        'face_id': face_id,
                        'scene_id': scene_id,
                        'frame': frame_file,
                        'confidence': face['confidence'],
                        'possible_performers': [p if isinstance(p, str) else p.get('stashapp_performers_id') for p in performers],
                        'timestamp': datetime.now().isoformat()
                    })

            # Update metadata
            self.metadata['processed_scenes'][scene_id] = {
                'processed_date': datetime.now().isoformat(),
                'performer_ids': [p if isinstance(p, str) else p.get('stashapp_performers_id') for p in performers],
                'faces_extracted': len(faces_metadata)
            }
            
            for face_meta in faces_metadata:
                self.metadata['face_entries'][face_meta['face_id']] = face_meta
                self.metadata['verification_status'][face_meta['face_id']] = 'unverified'

            self.save_metadata()
            
            # Cleanup temp directory
            shutil.rmtree(scene_temp_dir)
            
            return len(faces_metadata)

        except Exception as e:
            print(f"Error processing scene {scene_id}: {str(e)}")
            if os.path.exists(scene_temp_dir):
                shutil.rmtree(scene_temp_dir)
            raise

    def move_to_rejected(self, face_path: str):
        """Move a face image to the rejected directory"""
        face_filename = os.path.basename(face_path)
        scene_id = face_filename.split('_')[0]  # Extract scene_id from filename
        
        rejected_dir = os.path.join(self.structure['rejected'], scene_id)
        os.makedirs(rejected_dir, exist_ok=True)
        
        rejected_path = os.path.join(rejected_dir, face_filename)
        shutil.move(face_path, rejected_path)
        
        # Update metadata
        face_id = os.path.splitext(face_filename)[0]
        if face_id in self.metadata['verification_status']:
            self.metadata['verification_status'][face_id] = 'rejected'
            self.save_metadata()

    def load_metadata(self):
        """Load or initialize metadata"""
        if os.path.exists(self.metadata_file):
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

    def verify_scene(self, scene_id: str):
        """
        Verify a scene's face assignments and organize them into performer collections.
        This method:
        1. Checks each performer directory in the scene
        2. Copies verified faces to a central performer directory
        3. Updates metadata for verified faces
        """
        scene_dir = os.path.join(self.structure['unverified'], scene_id)
        if not os.path.exists(scene_dir):
            raise ValueError(f"Scene directory not found: {scene_id}")

        # Create verified directory if it doesn't exist
        verified_base = os.path.join(self.base_dir, 'verified')
        os.makedirs(verified_base, exist_ok=True)

        # Process each subdirectory in the scene directory
        for dir_name in os.listdir(scene_dir):
            dir_path = os.path.join(scene_dir, dir_name)
            if not os.path.isdir(dir_path) or dir_name == 'rejected':
                continue

            # If this is a performer directory (not rejected or unassigned)
            if ' - ' in dir_name:  # Format: "stashdb_id - name"
                performer_id = dir_name.split(' - ')[0]
                
                # Create/get performer's collection directory
                performer_collection = os.path.join(verified_base, dir_name)
                os.makedirs(performer_collection, exist_ok=True)

                # Copy all faces from scene's performer directory to collection
                for face_file in os.listdir(dir_path):
                    if not face_file.endswith('.jpg'):
                        continue

                    # Copy face to performer's collection
                    src_path = os.path.join(dir_path, face_file)
                    dst_path = os.path.join(performer_collection, face_file)
                    shutil.copy2(src_path, dst_path)

                    # Update metadata
                    face_id = os.path.splitext(face_file)[0]
                    if face_id in self.metadata['face_entries']:
                        self.metadata['verification_status'][face_id] = 'verified'
                        self.metadata['face_entries'][face_id]['verified_performer'] = performer_id

        # Update scene metadata
        if scene_id in self.metadata['processed_scenes']:
            self.metadata['processed_scenes'][scene_id]['verified'] = True
            self.metadata['processed_scenes'][scene_id]['verification_date'] = datetime.now().isoformat()

        self.save_metadata()
        print(f"Scene {scene_id} verification completed")

    def get_performer_face_count(self, performer_id: str = None) -> Dict[str, int]:
        """
        Get count of verified faces for performers.
        If performer_id is provided, returns count for that performer only.
        """
        verified_base = os.path.join(self.base_dir, 'verified')
        counts = {}

        if performer_id:
            # Find specific performer directory
            for dir_name in os.listdir(verified_base):
                if dir_name.startswith(performer_id):
                    dir_path = os.path.join(verified_base, dir_name)
                    face_count = len([f for f in os.listdir(dir_path) if f.endswith('.jpg')])
                    counts[dir_name] = face_count
                    break
        else:
            # Count for all performers
            for dir_name in os.listdir(verified_base):
                dir_path = os.path.join(verified_base, dir_name)
                if os.path.isdir(dir_path):
                    face_count = len([f for f in os.listdir(dir_path) if f.endswith('.jpg')])
                    counts[dir_name] = face_count

        return counts
