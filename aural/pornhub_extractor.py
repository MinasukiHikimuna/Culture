#!/usr/bin/env python3
"""
Pornhub Data Extractor - Python Version

This script extracts audio/video files and metadata from Pornhub using yt-dlp.
It downloads files, extracts metadata, and organizes data similar to other extractors.

Usage: uv run python pornhub_extractor.py <url>

Requirements:
1. Install yt-dlp: https://github.com/yt-dlp/yt-dlp
"""

import argparse
import subprocess
import sys
from pathlib import Path


class PornhubExtractor:
    def __init__(self, output_dir: str = "pornhub_data"):
        self.output_dir = Path(output_dir).resolve()

    def ensure_output_dir(self, uploader_dir: Path) -> None:
        """Create output directory if it doesn't exist."""
        if not uploader_dir.exists():
            uploader_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created output directory: {uploader_dir}")

    def check_yt_dlp(self) -> bool:
        """Check if yt-dlp is available."""
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                print("✅ yt-dlp is available")
                return True
            else:
                print("❌ yt-dlp not found. Please install yt-dlp:")
                print("   https://github.com/yt-dlp/yt-dlp")
                return False
        except FileNotFoundError:
            print("❌ yt-dlp not found. Please install yt-dlp:")
            print("   https://github.com/yt-dlp/yt-dlp")
            return False

    def extract_from_url(self, url: str) -> dict:
        """Extract content from Pornhub URL using yt-dlp."""
        print(f"🎯 Processing: {url}")

        # yt-dlp command with the exact format specified
        output_template = str(
            self.output_dir
            / "%(uploader)s"
            / "%(upload_date>%Y-%m-%d)s - %(id)s - %(fulltitle)s.%(ext)s"
        )

        args = [
            "yt-dlp",
            "--output",
            output_template,
            "--write-info-json",
            url,
        ]

        print("🚀 Starting yt-dlp extraction...")
        print(f"📂 Output directory: {self.output_dir}")

        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout_lines = []
        stderr_lines = []

        # Stream stdout in real-time
        for line in process.stdout:
            stdout_lines.append(line)
            # Show yt-dlp progress
            if "[download]" in line or "[info]" in line:
                print(line, end="")

        # Capture stderr
        for line in process.stderr:
            stderr_lines.append(line)

        return_code = process.wait()

        if return_code == 0:
            print("✅ yt-dlp extraction completed successfully")
            return {"success": True, "stdout": "".join(stdout_lines)}
        else:
            stderr = "".join(stderr_lines)
            print(f"❌ yt-dlp failed with code {return_code}")
            print(f"STDERR: {stderr}")
            raise RuntimeError(f"yt-dlp failed: {stderr}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract video/audio from Pornhub using yt-dlp"
    )
    parser.add_argument("url", nargs="?", help="Pornhub URL to extract")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="pornhub_data",
        help="Output directory (default: pornhub_data)",
    )

    args = parser.parse_args()

    if not args.url:
        print("Usage: uv run python pornhub_extractor.py <url>")
        print(
            "Example: uv run python pornhub_extractor.py "
            "https://www.pornhub.com/view_video.php?viewkey=123456"
        )
        return 1

    extractor = PornhubExtractor(output_dir=args.output_dir)

    if not extractor.check_yt_dlp():
        return 1

    try:
        extractor.extract_from_url(args.url)
        print("\n✅ Extraction completed successfully")
        return 0
    except Exception as error:
        print(f"\n❌ Extraction failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
