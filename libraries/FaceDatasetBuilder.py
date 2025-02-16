import os
import json
import shutil
from datetime import datetime
from mtcnn import MTCNN
import cv2
import pandas as pd
from typing import Dict, List
import ffmpeg

class FaceDatasetBuilder:
    def __init__(self):
        self.detector = MTCNN()
        self.base_dir = "H:\\Faces\\dataset"
        self.structure = {
            'frames': os.path.join(self.base_dir, 'frames'),
            'faces': os.path.join(self.base_dir, 'faces'),
            'verified': os.path.join(self.base_dir, 'verified'),
            'unverified': os.path.join(self.base_dir, 'unverified'),
            'rejected': os.path.join(self.base_dir, 'rejected')
        }
        self.metadata_file = os.path.join(self.base_dir, 'metadata.json')
        self.setup_directories()
        self.load_metadata()

    def setup_directories(self):
        """Create necessary directory structure"""
        for dir_path in self.structure.values():
            os.makedirs(dir_path, exist_ok=True)

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

    def process_scene(self, video_path: str, scene_id: str, performer_ids: List[str]):
        """Process a single scene and extract faces"""
        if scene_id in self.metadata['processed_scenes']:
            print(f"Scene {scene_id} already processed, skipping...")
            return

        # Create scene-specific directories
        scene_frames_dir = os.path.join(self.structure['frames'], scene_id)
        scene_faces_dir = os.path.join(self.structure['unverified'], scene_id)
        os.makedirs(scene_frames_dir, exist_ok=True)
        os.makedirs(scene_faces_dir, exist_ok=True)

        # Extract frames (using your existing ffmpeg code)
        output_pattern = os.path.join(scene_frames_dir, 'frame_%04d.png')
        (
            ffmpeg
            .input(video_path)
            .filter('fps', fps=1/24)  # Adjust fps as needed
            .output(output_pattern)
            .run()
        )

        # Process frames and extract faces
        faces_metadata = []
        for frame_file in os.listdir(scene_frames_dir):
            if not frame_file.endswith('.png'):
                continue

            frame_path = os.path.join(scene_frames_dir, frame_file)
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
                
                face_path = os.path.join(scene_faces_dir, f"{face_id}.jpg")
                cv2.imwrite(face_path, face_img)

                # Store metadata
                faces_metadata.append({
                    'face_id': face_id,
                    'scene_id': scene_id,
                    'frame': frame_file,
                    'confidence': face['confidence'],
                    'possible_performers': performer_ids,
                    'timestamp': datetime.now().isoformat()
                })

        # Update metadata
        self.metadata['processed_scenes'][scene_id] = {
            'processed_date': datetime.now().isoformat(),
            'performer_ids': performer_ids,
            'faces_extracted': len(faces_metadata)
        }
        
        for face_meta in faces_metadata:
            self.metadata['face_entries'][face_meta['face_id']] = face_meta
            self.metadata['verification_status'][face_meta['face_id']] = 'unverified'

        self.save_metadata()
        
        # Cleanup frames to save space
        shutil.rmtree(scene_frames_dir)
        
        return len(faces_metadata)

    def verify_face(self, face_id: str, performer_id: str = None, is_rejected: bool = False):
        """Verify or reject a face"""
        if face_id not in self.metadata['face_entries']:
            raise ValueError(f"Face ID {face_id} not found")

        face_meta = self.metadata['face_entries'][face_id]
        scene_id = face_meta['scene_id']
        
        # Source and destination paths
        src_dir = os.path.join(self.structure['unverified'], scene_id)
        src_path = os.path.join(src_dir, f"{face_id}.jpg")
        
        if is_rejected:
            dst_dir = os.path.join(self.structure['rejected'], scene_id)
            status = 'rejected'
        else:
            if performer_id not in face_meta['possible_performers']:
                raise ValueError(f"Performer {performer_id} not in possible performers for this scene")
            dst_dir = os.path.join(self.structure['verified'], performer_id)
            status = 'verified'
        
        os.makedirs(dst_dir, exist_ok=True)
        dst_path = os.path.join(dst_dir, f"{face_id}.jpg")
        
        # Move file and update metadata
        shutil.move(src_path, dst_path)
        self.metadata['verification_status'][face_id] = status
        if not is_rejected:
            self.metadata['face_entries'][face_id]['verified_performer'] = performer_id
        
        self.save_metadata()
