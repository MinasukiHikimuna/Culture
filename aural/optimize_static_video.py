#!/usr/bin/env python3
"""
Optimize static image videos by repackaging with efficient video encoding.

Videos downloaded from Pornhub often contain static images with audio content.
These store redundant video frames (e.g., 68,094 frames for 38 min at 30fps)
when a single looped image would suffice.

This script extracts a single frame and repackages with the original audio
(losslessly copied) to achieve ~90% space savings.

Usage:
    uv run python optimize_static_video.py <file.mp4>
    uv run python optimize_static_video.py --dry-run <file.mp4>
    uv run python optimize_static_video.py --backup <file.mp4>
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def analyze_video(file_path: Path) -> dict:
    """Analyze video file with ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def extract_frame_png(video_path: Path, output_path: Path, timestamp: float) -> bool:
    """Extract a single frame from video as lossless PNG."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-c:v", "png",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path.exists()
    except subprocess.CalledProcessError as e:
        print(f"  Frame extraction failed: {e}")
        return False


def repackage_video(
    original_path: Path,
    frame_path: Path,
    output_path: Path,
    duration: float,
) -> bool:
    """Create optimized video from static frame and original audio."""
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(frame_path),
        "-i", str(original_path),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-crf", "28",
        "-preset", "slower",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-t", str(duration),
        "-shortest",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path.exists()
    except subprocess.CalledProcessError as e:
        print(f"  Repackaging failed: {e}")
        print(f"  stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
        return False


def verify_output(output_path: Path) -> tuple[bool, str]:
    """Verify output file has valid audio and video streams."""
    if not output_path.exists():
        return False, "Output file does not exist"

    if output_path.stat().st_size < 1000:
        return False, "Output file too small (likely corrupt)"

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", str(output_path)],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])

        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        if not has_video:
            return False, "Output missing video stream"
        if not has_audio:
            return False, "Output missing audio stream"

        return True, "OK"
    except Exception as e:
        return False, f"Verification failed: {e}"


def format_size(size_bytes: int) -> str:
    """Format bytes as human readable size."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} bytes"


def parse_frame_rate(frame_rate_str: str) -> float:
    """Parse ffprobe frame rate string like '30/1' to float."""
    if "/" in frame_rate_str:
        num, denom = frame_rate_str.split("/")
        return float(num) / float(denom) if float(denom) != 0 else 0.0
    return float(frame_rate_str)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Optimize static image video by repackaging with efficient encoding"
    )
    parser.add_argument("file", type=Path, help="Video file to optimize")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--backup", action="store_true", help="Keep original file with .original.mp4 suffix"
    )
    parser.add_argument(
        "--frame-at",
        type=float,
        default=None,
        help="Timestamp (seconds) to extract frame from (default: middle of video)",
    )
    return parser.parse_args()


def print_video_info(
    original_size: int,
    duration: float,
    video_stream: dict,
    audio_stream: dict,
) -> int:
    """Print video info and return audio bitrate."""
    video_bitrate = int(video_stream.get("bit_rate", 0))
    audio_bitrate = int(audio_stream.get("bit_rate", 0))
    width = video_stream.get("width", 0)
    height = video_stream.get("height", 0)
    fps = parse_frame_rate(video_stream.get("r_frame_rate", "0/1"))

    print(f"  Size: {format_size(original_size)}")
    print(f"  Duration: {duration:.1f}s ({duration/60:.1f} min)")
    print(f"  Video: {width}x{height} @ {fps:.0f}fps, {video_bitrate/1000:.0f} kbps")
    print(f"  Audio: {audio_stream.get('codec_name', 'unknown')} @ {audio_bitrate/1000:.0f} kbps")
    print()
    return audio_bitrate


def print_estimated_savings(original_size: int, audio_bitrate: int, duration: float) -> None:
    """Print estimated savings."""
    estimated_video_bitrate = 20000  # 20 kbps for stillimage
    estimated_new_size = int((estimated_video_bitrate + audio_bitrate) * duration / 8)
    estimated_savings = original_size - estimated_new_size
    estimated_savings_pct = (estimated_savings / original_size) * 100
    print(f"Estimated savings: {format_size(estimated_savings)} ({estimated_savings_pct:.0f}%)")
    print()


def process_video(
    file_path: Path,
    cover_path: Path,
    duration: float,
    original_size: int,
    backup: bool,
) -> bool:
    """Process video: repackage, verify, and replace original."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "optimized.mp4"

        print("Repackaging video...")
        if not repackage_video(file_path, cover_path, output_path, duration):
            print("ERROR: Failed to repackage video")
            return False

        print("Verifying output...")
        valid, msg = verify_output(output_path)
        if not valid:
            print(f"ERROR: {msg}")
            return False

        new_size = output_path.stat().st_size
        actual_savings = original_size - new_size
        actual_savings_pct = (actual_savings / original_size) * 100

        print()
        print("=" * 50)
        print("RESULTS")
        print("=" * 50)
        print(f"  Original: {format_size(original_size)}")
        print(f"  New:      {format_size(new_size)}")
        print(f"  Saved:    {format_size(actual_savings)} ({actual_savings_pct:.1f}%)")
        print()

        if backup:
            backup_path = file_path.with_suffix(".original.mp4")
            print(f"Backing up to: {backup_path.name}")
            shutil.move(file_path, backup_path)
        else:
            print("Removing original...")
            file_path.unlink()

        print("Moving optimized file...")
        shutil.move(output_path, file_path)

        print()
        print("Done! Run a Stashapp scan to update metadata.")
    return True


def extract_cover_and_process(
    file_path: Path,
    duration: float,
    original_size: int,
    frame_at: float | None,
    backup: bool,
) -> bool:
    """Extract cover image and process video."""
    frame_timestamp = frame_at if frame_at is not None else duration / 2
    cover_path = file_path.with_suffix(".cover.png")

    print(f"Extracting cover image at {frame_timestamp:.1f}s...")
    if not extract_frame_png(file_path, cover_path, frame_timestamp):
        print("ERROR: Failed to extract cover image")
        return False
    print(f"  Cover saved: {cover_path.name} ({format_size(cover_path.stat().st_size)})")

    return process_video(file_path, cover_path, duration, original_size, backup)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    file_path = args.file.resolve()

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return 1

    print(f"File: {file_path.name}")
    print(f"Path: {file_path.parent}")
    print()

    print("Analyzing video...")
    try:
        data = analyze_video(file_path)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to analyze video: {e}")
        return 1

    format_info = data.get("format", {})
    streams = data.get("streams", [])
    duration = float(format_info.get("duration", 0))
    original_size = int(format_info.get("size", 0))

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream or not audio_stream:
        print("ERROR: File must have both video and audio streams")
        return 1

    audio_bitrate = print_video_info(original_size, duration, video_stream, audio_stream)
    print_estimated_savings(original_size, audio_bitrate, duration)

    if args.dry_run:
        print("[DRY-RUN] Would optimize this file")
        return 0

    success = extract_cover_and_process(
        file_path, duration, original_size, args.frame_at, args.backup
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
