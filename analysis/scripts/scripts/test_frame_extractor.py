import os
import json
import shutil
from pathlib import Path
import ffmpeg
from typing import Dict
import argparse
from face_preprocessor import FacePreprocessor

class TestFrameExtractor:
    def __init__(self, output_dir: str, verbose: bool = False):
        self.base_dir = Path(output_dir) / "test_frames"
        self.verbose = verbose

    def extract_frames(self, video_path: str, scene_id: str = None):
        """
        Extract key frames from a video for performer testing

        Args:
            video_path: Path to video file
            scene_id: Optional scene ID for naming the output directory
        """
        video_path = Path(video_path)

        # Use scene_id or video filename as directory name
        if scene_id is None:
            scene_id = video_path.stem

        # Create scene directory and subdirectories
        scene_dir = self.base_dir / scene_id
        original_dir = scene_dir / "original"
        processed_dir = scene_dir / "processed"

        original_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        print(f"Extracting frames from: {video_path}")
        if self.verbose:
            print(f"Saving to: {original_dir}")

        try:
            # Extract keyframes using ffmpeg
            (
                ffmpeg
                .input(str(video_path))
                .filter("select", "eq(pict_type,I)")  # Extract I-frames only
                .filter("select", "not(mod(n,2))")    # Take every other I-frame
                .output(
                    str(original_dir / "frame_%04d.jpg"),
                    qscale=2,  # Higher quality for better face detection
                    vsync=0,
                    threads=4
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            if self.verbose:
                print(f"Successfully extracted frames to {original_dir}")

            # Count extracted frames
            frame_count = len(list(original_dir.glob("*.jpg")))
            print(f"Extracted {frame_count} frames")

            # Process faces from extracted frames
            print("\nProcessing faces from extracted frames...")

            # Initialize face preprocessor for this scene
            face_preprocessor = FacePreprocessor(
                input_dir=original_dir,
                output_dir=processed_dir,
                verbose=self.verbose
            )

            # Process each frame
            face_preprocessor.process_dataset(num_workers=4)

            # Count processed faces
            processed_count = len(list(processed_dir.glob("*.jpg")))
            print(f"Processed {processed_count} faces")

            return original_dir, processed_dir

        except Exception as e:
            print(f"Error processing scene: {str(e)}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            # Clean up on failure
            if scene_dir.exists():
                shutil.rmtree(scene_dir)
            return None, None

def main():
    parser = argparse.ArgumentParser(description="Extract and process frames from video for performer testing")
    parser.add_argument("--video", type=str, required=True,
                      help="Path to video file")
    parser.add_argument("--scene-id", type=str,
                      help="Optional scene ID for naming output directory")
    parser.add_argument("--output", type=str, default="/mnt/h/Faces",
                      help="Base output directory (default: /mnt/h/Faces)")
    parser.add_argument("--verbose", action="store_true",
                      help="Enable verbose output")

    args = parser.parse_args()

    extractor = TestFrameExtractor(args.output, verbose=args.verbose)
    original_dir, processed_dir = extractor.extract_frames(args.video, args.scene_id)

    if original_dir and processed_dir:
        print("\nProcessing completed successfully:")
        if args.verbose:
            print(f"Original frames: {original_dir}")
            print(f"Processed faces: {processed_dir}")
    else:
        print("\nProcessing failed")

if __name__ == "__main__":
    main() 