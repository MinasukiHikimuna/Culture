import os
import subprocess
import re
from pathlib import Path


def get_sidecar_file(video_path):
    """Check if a sidecar file exists for the given video file."""
    video_path = Path(video_path)
    # Look for a sidecar file with .Scenes.csv extension
    sidecar_pattern = f"{video_path.name}.Scenes.csv"
    sidecar_path = video_path.parent / sidecar_pattern

    if sidecar_path.exists():
        return str(sidecar_path)
    return None


def downscale_video(input_path):
    """Downscale video using ffmpeg with NVENC."""
    input_path = Path(input_path)
    output_path = input_path.parent / f"{input_path.stem}.540p{input_path.suffix}"

    ffmpeg_cmd = [
        "ffmpeg",
        "-hwaccel",
        "cuda",
        "-hwaccel_output_format",
        "cuda",
        "-i",
        str(input_path),
        "-vf",
        "scale_cuda=960:540",
        "-c:v",
        "h264_nvenc",
        "-preset",
        "p1",  # Fastest preset
        "-tune",
        "ll",  # Low latency
        "-rc",
        "cbr",  # Constant bitrate
        "-b:v",
        "1M",  # Low bitrate since quality doesn't matter
        "-an",
        str(output_path),
    ]

    subprocess.run(ffmpeg_cmd, check=True)
    return str(output_path)


def run_scene_detection(video_path):
    """Run scene detection on the video file."""
    video_path = Path(video_path)
    scenedetect_cmd = [
        "scenedetect",
        "--input",
        str(video_path),
        "--output",
        str(video_path.parent),
        "detect-content",
        "list-scenes",
    ]

    subprocess.run(scenedetect_cmd, check=True)


def rename_scene_csv(video_path):
    """Rename the scene CSV file to match the original filename pattern."""
    video_path = Path(video_path)

    # Find all CSV files in the directory that might be our scene file
    csv_files = list(video_path.parent.glob(f"{video_path.stem}*-Scenes.csv"))

    if not csv_files:
        # If no exact match, try to find the most recent CSV file
        # that was created after the video file
        video_mtime = video_path.stat().st_mtime
        csv_files = [
            f
            for f in video_path.parent.glob("*-Scenes.csv")
            if f.stat().st_mtime > video_mtime
        ]

    if csv_files:
        # Get the most recently modified CSV file
        latest_csv = max(csv_files, key=lambda x: x.stat().st_mtime)

        # Create new filename by removing .540p from the name
        # but preserve the original filename structure including extension
        original_name = str(video_path.name).replace(".540p", "")
        new_csv_path = video_path.parent / f"{original_name}.Scenes.csv"

        print(f"Found CSV file: {latest_csv}")
        print(f"Renaming to: {new_csv_path}")

        latest_csv.rename(new_csv_path)
        return str(new_csv_path)

    return None


def process_video(video_path):
    """Main function to process a video file."""
    video_path = Path(video_path)

    # Check if sidecar file exists
    sidecar_file = get_sidecar_file(video_path)
    if sidecar_file:
        print(f"Sidecar file already exists: {sidecar_file}")
        return

    # Downscale video
    print(f"Downscaling video: {video_path}")
    downscaled_path = downscale_video(video_path)

    try:
        # Run scene detection
        print(f"Running scene detection on: {downscaled_path}")
        run_scene_detection(downscaled_path)

        # Rename CSV file
        print("Renaming scene CSV file")
        new_csv_path = rename_scene_csv(downscaled_path)
        if new_csv_path:
            print(f"Renamed CSV file to: {new_csv_path}")
    finally:
        # Clean up downscaled video file
        print(f"Deleting downscaled video: {downscaled_path}")
        Path(downscaled_path).unlink(missing_ok=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python pyscenedetect-process.py <video_file>")
        sys.exit(1)

    video_file = sys.argv[1]
    process_video(video_file)
