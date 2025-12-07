import setup_env  # Add this at the very top
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF logging

import json
import time
import shutil
from pathlib import Path
import cv2
from mtcnn import MTCNN
import tensorflow as tf
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from libraries.scene_states import SceneState, DatasetStructure
import cProfile
import pstats
from datetime import datetime
import argparse
from facenet_pytorch import MTCNN
import torch
from PIL import Image

class FaceDetector:
    def __init__(self, base_dir: str, max_concurrent: int = 4):
        # Convert Windows path to WSL path if needed
        if base_dir.startswith(('C:', 'D:', 'E:', 'F:', 'G:', 'H:')):
            drive_letter = base_dir[0].lower()
            wsl_path = f"/mnt/{drive_letter}/{base_dir[3:].replace('\\', '/')}"
            self.base_dir = Path(wsl_path)
        else:
            self.base_dir = Path(base_dir)
        
        # GPU setup and verification
        print("\nTensorFlow GPU configuration:")
        print(f"TensorFlow version: {tf.__version__}")
        print(f"GPU devices: {tf.config.list_physical_devices('GPU')}")
        print(f"Built with CUDA: {tf.test.is_built_with_cuda()}")
        
        physical_devices = tf.config.list_physical_devices('GPU')
        if physical_devices:
            print(f"\nFound {len(physical_devices)} GPU(s):")
            for device in physical_devices:
                print(f"  {device.device_type}: {device.name}")
            
            # Configure memory growth for all GPUs
            try:
                for gpu in physical_devices:
                    tf.config.experimental.set_memory_growth(gpu, True)
                print("GPU memory growth enabled for all GPUs")
                
                # Enable mixed precision
                tf.keras.mixed_precision.set_global_policy('mixed_float16')
                print("Mixed precision enabled")
                
                # Test GPU computation
                print("\nTesting GPU computation...")
                with tf.device('/GPU:0'):
                    dummy = tf.random.normal([1000, 1000])
                    result = tf.matmul(dummy, tf.transpose(dummy))
                    print("GPU test successful")
            except RuntimeError as e:
                print(f"GPU configuration error: {e}")
        else:
            print("\nNo GPU found. Please check:")
            print("1. NVIDIA GPU drivers are installed in WSL2")
            print("2. CUDA toolkit is installed in WSL2")
            print("3. cuDNN is installed in WSL2")
            print("4. TensorFlow was installed with GPU support")
            print("\nUsing CPU for processing (will be slower)")
        
        print("\nInitializing MTCNN detector...")
        start = time.time()
        self.detector = MTCNN()
        print(f"MTCNN initialization took {time.time() - start:.2f}s")
        
        self.max_concurrent = max_concurrent
        print(f"\nInitializing with base directory: {self.base_dir}")
        self.dataset = DatasetStructure(str(self.base_dir))  # Convert Path to string
        
        # Create all required directories
        for state in SceneState:
            dir_path = self.base_dir / 'scenes' / state.value
            print(f"Creating directory: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)
        
        self.mtcnn = MTCNN(
            image_size=160,
            margin=10,
            post_process=False,
            select_largest=True,
            device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        )
    
    def preprocess_frame(self, frame):
        """Preprocess frame for faster detection"""
        # Resize large images
        max_size = 1280
        h, w = frame.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            frame = cv2.resize(frame, None, fx=scale, fy=scale)
        return frame
    
    def process_frame(self, frame_data):
        """Process a single frame"""
        frame_path, faces_dir, scene_id = frame_data
        frame_start = time.time()
        
        # Load and preprocess frame
        frame = cv2.imread(str(frame_path))
        if frame is None:
            return 0, 0, 0
        
        frame = self.preprocess_frame(frame)
        
        # Detect faces
        detect_start = time.time()
        faces = self.detector.detect_faces(frame)
        detection_time = time.time() - detect_start
        
        faces_extracted = 0
        for face_idx, face in enumerate(faces):
            if face['confidence'] < 0.95:
                continue
            
            x, y, width, height = face['box']
            margin = int(max(width, height) * 0.2)
            face_img = frame[
                max(0, y-margin):min(frame.shape[0], y+height+margin),
                max(0, x-margin):min(frame.shape[1], x+width+margin)
            ]
            
            face_id = f"{scene_id}_{frame_path.stem}_face_{face_idx}"
            face_path = faces_dir / f"{face_id}.jpg"
            cv2.imwrite(str(face_path), face_img)
            faces_extracted += 1
        
        frame_time = time.time() - frame_start
        return faces_extracted, frame_time, detection_time
    
    def process_scene(self, scene_id: str):
        scene_start = time.time()
        frame_times = []
        detection_times = []
        working_dir = None
        
        try:
            # State and metadata checks
            if self.dataset.is_scene_processed(scene_id) and \
               self.dataset.info['processed_scenes'][scene_id] in [
                   SceneState.FACES_EXTRACTED.value,
                   SceneState.VERIFIED.value,
                   SceneState.NO_FACES_FOUND.value
               ]:
                print(f"Skipping {scene_id} - already processed")
                return
            
            metadata_start = time.time()
            metadata_path = self.dataset.scene_data / f"{scene_id}.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    scene_data = json.load(f)
                    performers = scene_data.get('performers', [])
            else:
                print(f"Warning: No metadata found for scene {scene_id}")
                performers = []
            print(f"Metadata loading took {time.time() - metadata_start:.2f}s")
            
            # Directory setup
            setup_start = time.time()
            source_dir = Path(str(self.dataset.scenes[SceneState.FRAMES_EXTRACTED.value] / scene_id))
            working_dir = Path(str(self.dataset.scenes[SceneState.EXTRACTING_FACES.value] / scene_id))
            faces_dir = working_dir / 'faces'
            
            if not source_dir.exists():
                raise FileNotFoundError(f"Source directory not found: {source_dir}")
            
            shutil.move(str(source_dir), str(working_dir))
            os.makedirs(faces_dir, exist_ok=True)
            print(f"Directory setup took {time.time() - setup_start:.2f}s")
            
            print(f"Processing scene {scene_id}")
            
            # Face detection with parallel frame processing
            frame_files = list(working_dir.glob('*.jpg'))
            print(f"Found {len(frame_files)} frames to process")
            
            total_faces = 0
            frame_data = [(f, faces_dir, scene_id) for f in frame_files]
            
            # Process frames in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(self.process_frame, frame_data))
            
            # Collect results
            for i, (faces, frame_time, detection_time) in enumerate(results):
                total_faces += faces
                frame_times.append(frame_time)
                detection_times.append(detection_time)
                
                if i % 10 == 0:
                    avg_frame = sum(frame_times[-10:]) / min(10, len(frame_times))
                    avg_detect = sum(detection_times[-10:]) / min(10, len(detection_times))
                    print(f"Frame {i}/{len(frame_files)} - "
                          f"Avg frame: {avg_frame:.2f}s, "
                          f"Avg detection: {avg_detect:.2f}s, "
                          f"Faces so far: {total_faces}")
            
            print(f"Final face count for scene {scene_id}: {total_faces}")
            
            # Handle case where no faces were found
            if total_faces == 0:
                print(f"No faces found in scene {scene_id} - marking as NO_FACES_FOUND")
                self.dataset.update_scene_state(scene_id, SceneState.NO_FACES_FOUND)
                if working_dir and working_dir.exists():
                    print(f"Cleaning up working directory: {working_dir}")
                    shutil.rmtree(working_dir)
                return
            
            # Move to final location if faces found
            move_start = time.time()
            output_dir = self.dataset.scenes[SceneState.FACES_EXTRACTED.value] / scene_id
            print(f"\nMoving files for scene {scene_id}")
            print(f"Total faces to move: {total_faces}")
            print(f"Source directory (faces_dir): {faces_dir}")
            print(f"Target directory (output_dir): {output_dir}")
            
            # List files before moving
            face_files = list(faces_dir.glob('*.jpg'))
            print(f"Files found in faces_dir: {len(face_files)}")
            for file in face_files[:5]:  # Show first 5 files as sample
                print(f"  - {file}")
            if len(face_files) > 5:
                print(f"  ... and {len(face_files)-5} more files")
            
            os.makedirs(output_dir, exist_ok=True)
            
            # Create performer directories
            for performer in performers:
                performer_dir = output_dir / performer
                os.makedirs(performer_dir, exist_ok=True)
                print(f"Created performer directory: {performer_dir}")
            
            os.makedirs(output_dir / 'unknown', exist_ok=True)
            
            # Move face files to the root of the scene directory
            moved_count = 0
            for face_file in faces_dir.glob('*.jpg'):
                target_path = output_dir / face_file.name
                print(f"Moving {face_file} to {target_path}")
                try:
                    shutil.move(str(face_file), str(target_path))
                    moved_count += 1
                except Exception as e:
                    print(f"Error moving file {face_file}: {str(e)}")
            
            print(f"Successfully moved {moved_count} files")
            
            # Verify files after moving
            final_files = list(output_dir.glob('*.jpg'))
            print(f"Files found in output_dir after move: {len(final_files)}")
            
            print(f"Moving files took {time.time() - move_start:.2f}s")
            
            self.dataset.update_scene_state(scene_id, SceneState.FACES_EXTRACTED)
            
            # Cleanup
            cleanup_start = time.time()
            shutil.rmtree(working_dir)
            print(f"Cleanup took {time.time() - cleanup_start:.2f}s")
            
            # Final stats
            total_time = time.time() - scene_start
            print(f"\nScene {scene_id} completed:")
            print(f"Total time: {total_time:.2f}s")
            print(f"Average frame time: {sum(frame_times)/len(frame_times):.2f}s")
            print(f"Average detection time: {sum(detection_times)/len(detection_times):.2f}s")
            print(f"Faces extracted: {total_faces}")
            
        except Exception as e:
            print(f"Error processing scene {scene_id}: {str(e)}")
            failed_dir = self.dataset.scenes[SceneState.FAILED.value] / scene_id
            os.makedirs(failed_dir, exist_ok=True)
            with open(failed_dir / 'error.txt', 'w') as f:
                f.write(str(e))
            if working_dir and working_dir.exists():
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

    def detect_and_align(self, image):
        """Detect faces and align them using eye landmarks"""
        # Detect faces and landmarks
        boxes, probs, landmarks = self.mtcnn.detect(image, landmarks=True)
        
        aligned_faces = []
        if boxes is not None:
            for i, (box, landmark) in enumerate(zip(boxes, landmarks)):
                # Extract face using box
                face = image.crop(box)
                
                # Align face using landmarks
                aligned_face = align_face(face, landmark)
                
                # Resize to standard size
                aligned_face = aligned_face.resize((160, 160), Image.Resampling.LANCZOS)
                
                aligned_faces.append(aligned_face)
        
        return aligned_faces

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Face Detector for WSL2')
    parser.add_argument('--base-dir', type=str, required=True,
                       help='Base directory for dataset (Windows or WSL2 path)')
    args = parser.parse_args()
    
    # Setup profiler
    pr = cProfile.Profile()
    pr.enable()
    
    detector = FaceDetector(args.base_dir)
    try:
        detector.run()
    except KeyboardInterrupt:
        print("\nStopping profiler and saving stats...")
        pr.disable()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = f"face_detector_profile_{timestamp}.stats"
        with open(stats_file, 'w') as f:
            stats = pstats.Stats(pr, stream=f)
            stats.sort_stats('cumulative')
            stats.print_stats()
        print(f"Profile stats saved to {stats_file}") 