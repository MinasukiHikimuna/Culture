#!/usr/bin/env python3
"""
Pornhub Data Extractor - Python Version

This script extracts audio/video files and metadata from Pornhub using yt-dlp.
It downloads files, extracts metadata, and organizes data similar to other extractors.

Usage: uv run python pornhub_extractor.py <url>
"""

import argparse
import sys
from pathlib import Path

import yt_dlp


class YtDlpLogger:
    """Custom logger for yt-dlp that uses emoji prefixes."""

    def debug(self, msg: str) -> None:
        # yt-dlp passes both debug and info through debug
        if msg.startswith("[debug] "):
            pass  # Skip debug messages
        else:
            self.info(msg)

    def info(self, msg: str) -> None:
        print(msg)

    def warning(self, msg: str) -> None:
        print(f"⚠️  {msg}")

    def error(self, msg: str) -> None:
        print(f"❌ {msg}")


class PornhubExtractor:
    def __init__(self, output_dir: str = "pornhub_data"):
        self.output_dir = Path(output_dir).resolve()

    def _progress_hook(self, d: dict) -> None:
        """Progress hook for yt-dlp downloads."""
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                percent = downloaded / total * 100
                speed = d.get("speed")
                speed_str = f"{speed / 1024 / 1024:.1f}MiB/s" if speed else "N/A"
                print(f"\r📥 Downloading: {percent:.1f}% at {speed_str}", end="")
        elif d["status"] == "finished":
            print("\n✅ Download complete, post-processing...")

    def extract_from_url(self, url: str) -> dict:
        """Extract content from Pornhub URL using yt-dlp."""
        print(f"🎯 Processing: {url}")
        print("🚀 Starting yt-dlp extraction...")
        print(f"📂 Output directory: {self.output_dir}")

        output_template = str(
            self.output_dir
            / "%(uploader)s"
            / "%(upload_date>%Y-%m-%d)s - %(id)s - %(fulltitle)s.%(ext)s"
        )

        ydl_opts = {
            "outtmpl": output_template,
            "writeinfojson": True,
            "logger": YtDlpLogger(),
            "progress_hooks": [self._progress_hook],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])

        if error_code:
            raise RuntimeError(f"yt-dlp failed with error code {error_code}")

        print("✅ yt-dlp extraction completed successfully")
        return {"success": True}


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

    try:
        extractor.extract_from_url(args.url)
        print("\n✅ Extraction completed successfully")
        return 0
    except Exception as error:
        print(f"\n❌ Extraction failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
