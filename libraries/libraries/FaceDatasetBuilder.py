import concurrent.futures
import json
import os
import queue as thread_queue
from pathlib import Path
import shutil
import subprocess
import threading
from datetime import datetime
from multiprocessing import cpu_count
from typing import Dict, List, Union

import cv2
import ffmpeg
import tensorflow as tf
from mtcnn import MTCNN

from libraries.scene_states import SceneState


class FaceDatasetBuilder:
    def __init__(self, max_concurrent_scenes=4):
        # Enable GPU growth to avoid taking all memory
        physical_devices = tf.config.list_physical_devices("GPU")
        if physical_devices:
            tf.config.experimental.set_memory_growth(physical_devices[0], True)

        self.detector = MTCNN()
        self.base_dir = "H:\\Faces\\dataset"
        base = Path(self.base_dir)
        self.structure = {
            "scenes": {
                SceneState.PENDING.value: str(base / "scenes" / SceneState.PENDING.value),
                SceneState.EXTRACTING_FRAMES.value: str(base / "scenes" / SceneState.EXTRACTING_FRAMES.value),
                SceneState.FRAMES_EXTRACTED.value: str(base / "scenes" / SceneState.FRAMES_EXTRACTED.value),
                SceneState.EXTRACTING_FACES.value: str(base / "scenes" / SceneState.EXTRACTING_FACES.value),
                SceneState.FACES_EXTRACTED.value: str(base / "scenes" / SceneState.FACES_EXTRACTED.value),
                SceneState.VERIFIED.value: str(base / "scenes" / SceneState.VERIFIED.value),
                SceneState.FAILED.value: str(base / "scenes" / SceneState.FAILED.value),
            },
            "performers": {
                "verified": str(base / "performers" / "verified"),
            }
        }
        self.metadata_file = str(base / "metadata.json")
        self.setup_directories()
        self.load_metadata()
        self.max_concurrent_scenes = max_concurrent_scenes
        self.max_per_drive = 2  # Maximum concurrent processes per drive
        self.drive_semaphores = {}  # Semaphores to limit concurrent access per drive
        self.scene_queue = thread_queue.Queue()
        self.results = thread_queue.Queue()

    def setup_directories(self):
        """Create necessary directory structure"""
        # Create scene status directories
        for status_dir in self.structure["scenes"].values():
            Path(status_dir).mkdir(parents=True, exist_ok=True)

        # Create performer directories
        for performer_dir in self.structure["performers"].values():
            Path(performer_dir).mkdir(parents=True, exist_ok=True)

    def get_performer_directory_name(self, performer: Union[dict, str]) -> str:
        """Create directory name from performer data or ID"""
        if isinstance(performer, str):
            return performer

        stashdb_id = None
        for stash_id in performer.get("stashapp_performers_stash_ids", []):
            if stash_id["endpoint"] == "https://stashdb.org/graphql":
                stashdb_id = stash_id["stash_id"]
                break

        name = performer.get("stashapp_performers_name", "")
        if stashdb_id:
            return f"{stashdb_id} - {name}"
        return name

    def process_frame(self, frame_path: str, scene_dir: str, scene_id: str, performers: list) -> list:
        """Process a single frame for faces"""
        # Read image
        image = cv2.imread(frame_path)
        if image is None:
            return []

        # Resize image for faster processing (adjust size as needed)
        scale = 0.5
        small_image = cv2.resize(image, None, fx=scale, fy=scale)
        image_rgb = cv2.cvtColor(small_image, cv2.COLOR_BGR2RGB)

        # Detect faces
        faces = self.detector.detect_faces(image_rgb)
        faces_metadata = []

        frame_file = os.path.basename(frame_path)

        for i, face in enumerate(faces):
            if face["confidence"] < 0.95:
                continue

            face_id = f"{scene_id}_{frame_file[:-4]}_face_{i}"

            # Scale coordinates back to original size
            x, y, width, height = [int(coord/scale) for coord in face["box"]]
            margin = int(max(width, height) * 0.2)

            # Extract face from original image
            face_img = image[
                max(0, y-margin):min(image.shape[0], y+height+margin),
                max(0, x-margin):min(image.shape[1], x+width+margin)
            ]

            # Save face
            face_path = str(Path(scene_dir) / f"{face_id}.jpg")
            cv2.imwrite(face_path, face_img)

            faces_metadata.append({
                "face_id": face_id,
                "scene_id": scene_id,
                "frame": frame_file,
                "confidence": face["confidence"],
                "possible_performers": [p if isinstance(p, str) else p.get("stashapp_performers_id") for p in performers],
                "timestamp": datetime.now().isoformat()
            })

        return faces_metadata

    def process_frame_batch(self, frame_paths: list[str], scene_dir: str, scene_id: str, performers: list) -> list:
        """Process a batch of frames for faces"""
        faces_metadata = []

        # Pre-allocate lists
        images = []
        image_info = []

        # Read all images in batch
        for frame_path in frame_paths:
            try:
                # Read image in color mode
                image = cv2.imread(frame_path)
                if image is not None:
                    # Resize image for faster processing
                    scale = 0.5
                    small_image = cv2.resize(image, None, fx=scale, fy=scale)
                    # Convert to RGB for MTCNN
                    image_rgb = cv2.cvtColor(small_image, cv2.COLOR_BGR2RGB)
                    images.append(image_rgb)
                    image_info.append((frame_path, image, scale))
            except Exception as e:
                print(f"Error reading {frame_path}: {str(e)}")
                continue

        if not images:
            return []

        # Process each image
        for idx, (frame_path, original_image, scale) in enumerate(image_info):
            try:
                faces = self.detector.detect_faces(images[idx])
                if not faces:
                    continue

                frame_file = os.path.basename(frame_path)

                for i, face in enumerate(faces):
                    try:
                        if face["confidence"] < 0.95:
                            continue

                        face_id = f"{scene_id}_{frame_file[:-4]}_face_{i}"

                        # Scale coordinates back to original size
                        x, y, width, height = [int(coord/scale) for coord in face["box"]]
                        margin = int(max(width, height) * 0.2)

                        # Extract face from original image with bounds checking
                        y_start = max(0, y-margin)
                        y_end = min(original_image.shape[0], y+height+margin)
                        x_start = max(0, x-margin)
                        x_end = min(original_image.shape[1], x+width+margin)

                        if y_end <= y_start or x_end <= x_start:
                            print(f"Invalid face coordinates in {frame_file}")
                            continue

                        face_img = original_image[y_start:y_end, x_start:x_end]

                        # Save face
                        face_path = str(Path(scene_dir) / f"{face_id}.jpg")
                        cv2.imwrite(face_path, face_img, [cv2.IMWRITE_JPEG_QUALITY, 95])

                        faces_metadata.append({
                            "face_id": face_id,
                            "scene_id": scene_id,
                            "frame": frame_file,
                            "confidence": face["confidence"],
                            "possible_performers": performers,
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception as e:
                        print(f"Error processing face {i} in {frame_file}: {str(e)}")
                        continue

            except Exception as e:
                print(f"Error processing frame {frame_path}: {str(e)}")
                continue

        return faces_metadata

    def process_multiple_scenes(self, scenes: list[dict]) -> list[dict]:
        """Process multiple scenes in parallel, balanced across drives"""
        results = []

        # Group scenes by drive
        drive_scenes = {}
        for scene in scenes:
            video_path = scene.get("video_path", scene.get("stashapp_primary_file_path"))
            drive = os.path.splitdrive(video_path)[0].upper()
            if drive not in drive_scenes:
                drive_scenes[drive] = []
                # Create semaphore for this drive if it doesn't exist
                if drive not in self.drive_semaphores:
                    self.drive_semaphores[drive] = threading.Semaphore(self.max_per_drive)
            drive_scenes[drive].append(scene)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_scenes) as executor:
            # Submit scenes for processing, using drive semaphores
            future_to_scene = {}
            for drive, drive_scene_list in drive_scenes.items():
                for scene in drive_scene_list:
                    future = executor.submit(self._process_scene_with_semaphore,
                                          scene,
                                          self.drive_semaphores[drive])
                    future_to_scene[future] = scene

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_scene):
                scene = future_to_scene[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "scene_id": scene.get("stashapp_stashdb_id"),
                        "error": str(e),
                        "status": "error"
                    })

        return results

    def _process_scene_with_semaphore(self, scene: dict, drive_semaphore: threading.Semaphore) -> dict:
        """Process a scene while respecting drive semaphore"""
        with drive_semaphore:
            return self._process_scene_wrapper(scene)

    def _process_scene_wrapper(self, scene: dict) -> dict:
        """Wrapper method to handle scene processing for parallel execution"""
        scene_id = scene.get("stashapp_stashdb_id")
        video_path = scene.get("video_path", scene.get("stashapp_primary_file_path"))
        performers = scene.get("performers", [])

        if not all([scene_id, video_path, performers]):
            return {"scene_id": scene_id, "error": "Missing required scene data", "status": "error"}

        # Create scene directory in extracting_frames
        scene_frames_dir = str(Path(self.structure["scenes"][SceneState.EXTRACTING_FRAMES.value]) / scene_id)
        Path(scene_frames_dir).mkdir(parents=True, exist_ok=True)

        try:
            # Extract frames using ffmpeg
            try:
                (
                    ffmpeg
                    .input(video_path, skip_frame="nokey")
                    .filter("select", "not(mod(n,10))")
                    .output(
                        str(Path(scene_frames_dir) / "frame_%04d.jpg"),
                        qscale=3,
                        vsync=0,
                        threads=10
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error as e:
                print(f"ffmpeg stderr:\n{e.stderr.decode()}")
                raise

            # Move to extracting_faces state
            scene_faces_dir = str(Path(self.structure["scenes"][SceneState.EXTRACTING_FACES.value]) / scene_id)
            shutil.move(scene_frames_dir, scene_faces_dir)

            # Process frames and detect faces
            frame_files = sorted([str(Path(scene_faces_dir) / f)
                                for f in os.listdir(scene_faces_dir)
                                if f.endswith(".jpg")])

            # Create unverified directory structure
            scene_unverified_dir = str(Path(self.structure["scenes"][SceneState.FACES_EXTRACTED.value]) / scene_id)
            Path(scene_unverified_dir).mkdir(parents=True, exist_ok=True)

            # Create directories for each performer
            for performer in performers:
                performer_dir = str(Path(scene_unverified_dir) / performer)
                Path(performer_dir).mkdir(parents=True, exist_ok=True)

            # Create unknown directory
            unknown_dir = str(Path(scene_unverified_dir) / "unknown")
            Path(unknown_dir).mkdir(parents=True, exist_ok=True)

            # Process frames and detect faces
            faces_extracted = 0
            for frame_path in frame_files:
                frame = cv2.imread(frame_path)
                if frame is None:
                    continue

                faces = self.detector.detect_faces(frame)
                for face_idx, face in enumerate(faces):
                    if face["confidence"] < 0.95:
                        continue

                    x, y, width, height = face["box"]
                    margin = int(max(width, height) * 0.2)
                    face_img = frame[
                        max(0, y-margin):min(frame.shape[0], y+height+margin),
                        max(0, x-margin):min(frame.shape[1], x+width+margin)
                    ]

                    frame_number = os.path.splitext(os.path.basename(frame_path))[0].split("_")[1]
                    face_id = f"{scene_id}_{frame_number}_face_{face_idx}"
                    face_path = str(Path(scene_unverified_dir) / f"{face_id}.jpg")
                    cv2.imwrite(face_path, face_img)
                    faces_extracted += 1

            # Clean up frames directory
            shutil.rmtree(scene_faces_dir)

            # Update metadata
            self.metadata["processed_scenes"][scene_id] = {
                "performers": performers,
                "faces_extracted": faces_extracted,
                "state": SceneState.FACES_EXTRACTED.value,
                "verified": False,
                "timestamp": datetime.now().isoformat()
            }
            self._save_metadata()

            return {
                "scene_id": scene_id,
                "faces_extracted": faces_extracted,
                "status": "success"
            }

        except Exception as e:
            # Clean up any leftover directories in case of error
            for state_dir in [SceneState.EXTRACTING_FRAMES.value, SceneState.EXTRACTING_FACES.value]:
                error_dir = str(Path(self.structure["scenes"][state_dir]) / scene_id)
                if Path(error_dir).exists():
                    shutil.rmtree(error_dir)
            return {
                "scene_id": scene_id,
                "error": str(e),
                "status": "error"
            }

    def move_to_rejected(self, face_path: str):
        """Move a face image to the rejected directory"""
        face_filename = os.path.basename(face_path)
        scene_id = face_filename.split("_")[0]  # Extract scene_id from filename

        rejected_dir = str(Path(self.structure["scenes"][SceneState.FACES_EXTRACTED.value]) / scene_id)
        Path(rejected_dir).mkdir(parents=True, exist_ok=True)

        rejected_path = str(Path(rejected_dir) / face_filename)
        shutil.move(face_path, rejected_path)

        # Update metadata
        face_id = os.path.splitext(face_filename)[0]
        if face_id in self.metadata["verification_status"]:
            self.metadata["verification_status"][face_id] = "rejected"
            self.save_metadata()

    def load_metadata(self):
        """Load or initialize metadata"""
        if Path(self.metadata_file).exists():
            with open(self.metadata_file, "r") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {
                "processed_scenes": {},  # Now includes 'status' field
                "face_entries": {},
                "verification_status": {}
            }

    def save_metadata(self):
        """Save metadata to file"""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def get_scene_status(self, scene_id: str) -> str:
        """Get the current status of a scene"""
        for status, directory in self.structure["scenes"].items():
            if (Path(directory) / scene_id).exists():
                return status
        return None

    def move_scene_to_status(self, scene_id: str, new_status: str):
        """Move a scene directory to a new status"""
        if new_status not in self.structure["scenes"]:
            raise ValueError(f"Invalid status: {new_status}")

        current_status = self.get_scene_status(scene_id)
        if not current_status:
            raise ValueError(f"Scene not found: {scene_id}")

        current_path = str(Path(self.structure["scenes"][current_status]) / scene_id)
        new_path = str(Path(self.structure["scenes"][new_status]) / scene_id)

        # Move the directory
        shutil.move(current_path, new_path)

        # Update metadata
        if scene_id in self.metadata["processed_scenes"]:
            self.metadata["processed_scenes"][scene_id]["status"] = new_status
            self.metadata["processed_scenes"][scene_id]["status_updated"] = datetime.now().isoformat()
            self.save_metadata()

    def verify_scene(self, scene_id: str):
        """
        Verify a scene's face assignments and organize them into performer collections.
        """
        current_status = self.get_scene_status(scene_id)
        if not current_status:
            raise ValueError(f"Scene not found: {scene_id}")

        if current_status == SceneState.VERIFIED.value:
            print(f"Scene {scene_id} is already verified")
            return

        scene_dir = str(Path(self.structure["scenes"][current_status]) / scene_id)

        # Process each face in the scene directory
        for face_file in os.listdir(scene_dir):
            if not face_file.endswith(".jpg"):
                continue

            # Update metadata
            face_id = os.path.splitext(face_file)[0]
            if face_id in self.metadata["face_entries"]:
                self.metadata["verification_status"][face_id] = "verified"

        # Move scene to verified status
        self.move_scene_to_status(scene_id, SceneState.VERIFIED.value)
        print(f"Scene {scene_id} verification completed")

    def get_performer_face_count(self, performer_id: str = None) -> dict[str, int]:
        """
        Get count of verified faces for performers.
        """
        verified_base = self.structure["performers"]["verified"]
        counts = {}

        if performer_id:
            # Find specific performer directory
            for dir_name in os.listdir(verified_base):
                if dir_name.startswith(performer_id):
                    dir_path = str(Path(verified_base) / dir_name)
                    face_count = len([f for f in os.listdir(dir_path) if f.endswith(".jpg")])
                    counts[dir_name] = face_count
                    break
        else:
            # Count for all performers
            for dir_name in os.listdir(verified_base):
                dir_path = str(Path(verified_base) / dir_name)
                if os.path.isdir(dir_path):
                    face_count = len([f for f in os.listdir(dir_path) if f.endswith(".jpg")])
                    counts[dir_name] = face_count

        return counts
