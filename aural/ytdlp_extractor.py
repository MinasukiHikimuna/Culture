#!/usr/bin/env python3
"""
yt-dlp Extractor - Platform-Agnostic Video Downloader & Indexer

This script extracts video files and metadata from any yt-dlp-supported site
(YouTube, Pornhub, and 1000+ others). Designed for audio-focused content that
is distributed as video files (static image + audio track).

Usage:
    uv run python ytdlp_extractor.py download <url>
    uv run python ytdlp_extractor.py info <url>
    uv run python ytdlp_extractor.py index <url> --max-videos 50
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

import config as aural_config


class YtDlpLogger:
    """Custom logger for yt-dlp with emoji prefixes."""

    # ANSI escape: clear from cursor to end of line
    CLEAR_LINE = "\033[K"

    def __init__(self) -> None:
        self._in_progress = False

    def debug(self, msg: str) -> None:
        # yt-dlp passes both debug and info through debug
        if msg.startswith("[debug] "):
            pass  # Skip debug messages
        else:
            self.info(msg)

    def info(self, msg: str) -> None:
        if msg.startswith("[download]"):
            # Print progress on single updating line, clear to end of line
            print(f"\r{msg}{self.CLEAR_LINE}", end="", flush=True)
            self._in_progress = True
        else:
            # Print newline first if we were showing progress
            if self._in_progress:
                print()
                self._in_progress = False
            print(msg)

    def warning(self, msg: str) -> None:
        if self._in_progress:
            print()
            self._in_progress = False
        print(f"⚠️  {msg}")

    def error(self, msg: str) -> None:
        if self._in_progress:
            print()
            self._in_progress = False
        print(f"❌ {msg}")


class YtDlpExtractor:
    """Platform-agnostic video extractor using yt-dlp."""

    # Base options applied to all yt-dlp calls
    BASE_OPTS = {
        # Enable remote components for JS challenge solving (YouTube)
        # See: https://github.com/yt-dlp/yt-dlp/wiki/EJS
        "remote_components": ["ejs:github"],
        # Prefer best quality in mp4 container
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
    }

    def __init__(self, output_dir: str | None = None, use_cache: bool = True):
        self.output_dir = Path(output_dir).resolve() if output_dir else aural_config.YTDLP_DIR
        self.cache_dir = self.output_dir / "cache"
        self.use_cache = use_cache
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create output directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        return self.cache_dir / f"{self._get_cache_key(url)}.json"

    def _load_from_cache(self, url: str) -> dict | None:
        """Load cached metadata for URL."""
        if not self.use_cache:
            return None

        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                print(f"📂 Loaded from cache: {url}")
                return data
            except json.JSONDecodeError:
                return None
        return None

    def _save_to_cache(self, url: str, data: dict) -> None:
        """Save metadata to cache."""
        if not self.use_cache:
            return

        cache_path = self._get_cache_path(url)
        cache_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"💾 Cached metadata for: {url}")

    def _get_uploader_url(self, info: dict) -> str:
        """Get uploader URL, constructing it for platforms that don't provide it."""
        # Use provided URL if available
        uploader_url = info.get("uploader_url") or info.get("channel_url")
        if uploader_url:
            return uploader_url

        # Construct URL for known platforms
        extractor = (info.get("extractor_key") or "").lower()
        uploader_id = info.get("uploader_id") or info.get("uploader")

        if extractor == "pornhub" and uploader_id:
            # uploader_id may be path-style (/pornstar/xxx) or just username
            if uploader_id.startswith("/"):
                return f"https://www.pornhub.com{uploader_id}"
            return f"https://www.pornhub.com/model/{uploader_id}"

        return ""

    def _extract_performers(self, title: str, uploader: str) -> dict:
        """Extract performer information from title and uploader."""
        performers = {
            "primary": uploader,
            "detected": [],
        }

        # Patterns to find performers in title
        patterns = [
            r"featuring\s+([^,|\]]+)",
            r"with\s+([^,|\]]+)",
            r"starring\s+([^,|\]]+)",
            r"ft\.?\s+([^,|\]]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            for match in matches:
                name = match.strip()
                if name and name not in performers["detected"]:
                    performers["detected"].append(name)

        return performers

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _build_output_schema(self, info: dict, file_path: Path | None = None) -> dict:
        """Build platform-agnostic output schema from yt-dlp info."""
        title = info.get("title", "")
        uploader = info.get("uploader", "")

        result = {
            "video": {
                "sourceUrl": info.get("webpage_url") or info.get("url"),
                "filePath": str(file_path) if file_path else None,
                "format": info.get("ext"),
                "fileSize": file_path.stat().st_size if file_path else None,
                "checksum": (
                    {"sha256": self._calculate_checksum(file_path)}
                    if file_path
                    else None
                ),
            },
            "metadata": {
                "title": title,
                "author": uploader,
                "description": info.get("description", ""),
                "tags": info.get("tags") or [],
                "duration": info.get("duration"),
                "platform": {
                    "name": info.get("extractor_key", "").lower(),
                    "url": self._get_uploader_url(info),
                },
                "performers": self._extract_performers(title, uploader),
            },
            "platformData": {
                "id": info.get("id"),
                "uploader_id": info.get("uploader_id"),
                "upload_date": info.get("upload_date"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "duration_string": info.get("duration_string"),
                "thumbnail": info.get("thumbnail"),
            },
            "backupFiles": {
                "metadata": None,  # Set by caller
            },
            "extractedAt": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }

        return result

    def download(self, url: str) -> dict:
        """Download video and extract metadata."""
        print(f"🎯 Processing: {url}")
        print("🚀 Starting download...")
        print(f"📂 Output directory: {self.output_dir}")

        output_template = str(
            self.output_dir
            / "%(uploader)s"
            / "%(upload_date>%Y-%m-%d)s - %(id)s - %(fulltitle)s.%(ext)s"
        )

        ydl_opts = {
            **self.BASE_OPTS,
            "outtmpl": output_template,
            "writeinfojson": True,
            "noplaylist": True,  # Only download single video, not playlist
            "logger": YtDlpLogger(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            info = ydl.sanitize_info(info)

        # Find the downloaded file
        file_path = None
        if info.get("requested_downloads"):
            file_path = Path(info["requested_downloads"][0]["filepath"])
        elif info.get("_filename"):
            file_path = Path(info["_filename"])

        # Build output schema
        result = self._build_output_schema(info, file_path)

        # Find and set the .info.json path
        if file_path:
            info_json_path = file_path.with_suffix(".info.json")
            if info_json_path.exists():
                result["backupFiles"]["metadata"] = str(info_json_path)

        # Cache the result for duplicate detection
        self._save_to_cache(url, result)

        print("✅ Download completed successfully")
        return result

    def extract_info(self, url: str) -> dict:
        """Extract metadata only (no download)."""
        # Check cache first
        cached = self._load_from_cache(url)
        if cached:
            return cached

        print(f"🎯 Extracting info: {url}")

        ydl_opts = {
            **self.BASE_OPTS,
            "noplaylist": True,  # Only extract single video, not playlist
            "logger": YtDlpLogger(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            info = ydl.sanitize_info(info)

        result = self._build_output_schema(info)

        # Cache the result
        self._save_to_cache(url, result)

        print("✅ Info extraction completed")
        return result

    def _normalize_pornhub_url(self, url: str) -> str:
        """Normalize Pornhub URLs to get all uploaded videos.

        Pornhub pornstar/model pages show only featured videos by default.
        Appending /videos/upload returns all uploaded videos.
        """
        # Match pornstar or model pages without /videos/upload suffix
        pattern = r"^(https?://(?:www\.)?pornhub\.com/(?:pornstar|model)/[^/]+)(?:/videos)?/?$"
        match = re.match(pattern, url)
        if match:
            base_url = match.group(1)
            normalized = f"{base_url}/videos/upload"
            print(f"📝 Normalized Pornhub URL: {normalized}")
            return normalized
        return url

    def index_playlist(self, url: str, max_videos: int | None = None) -> list[dict]:
        """Index all videos in a playlist/channel."""
        # Normalize Pornhub URLs to get all videos
        url = self._normalize_pornhub_url(url)
        print(f"📋 Indexing playlist/channel: {url}")

        ydl_opts = {
            **self.BASE_OPTS,
            "extract_flat": "in_playlist",
            "logger": YtDlpLogger(),
        }

        if max_videos:
            ydl_opts["playlistend"] = max_videos

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            info = ydl.sanitize_info(info)

        if not info:
            print("❌ Failed to extract playlist info")
            return []

        entries = info.get("entries", [])

        # Handle single video vs playlist
        if not entries:
            # Single video, just extract its info
            return [self.extract_info(url)]
        print(f"🔍 Found {len(entries)} videos")

        results = []
        for i, entry in enumerate(entries):
            if not entry:
                continue

            video_url = entry.get("url") or entry.get("webpage_url")
            if not video_url:
                continue

            # Build minimal result from flat entry (no full extraction)
            result = {
                "video": {
                    "sourceUrl": video_url,
                    "filePath": None,
                    "format": None,
                    "fileSize": None,
                    "checksum": None,
                },
                "metadata": {
                    "title": entry.get("title", ""),
                    "author": entry.get("uploader", info.get("uploader", "")),
                    "description": "",
                    "tags": [],
                    "duration": entry.get("duration"),
                    "platform": {
                        "name": info.get("extractor", ""),
                        "url": "",
                    },
                    "performers": {
                        "primary": entry.get("uploader", info.get("uploader", "")),
                        "additional": [],
                    },
                },
                "platformData": {
                    "id": entry.get("id", ""),
                    "upload_date": entry.get("upload_date"),
                },
                "playlist_info": {
                    "title": info.get("title"),
                    "id": info.get("id"),
                    "uploader": info.get("uploader"),
                    "index": i + 1,
                },
            }
            results.append(result)

        return results

    def generate_summary(self, data: list[dict]) -> dict:
        """Generate summary report from indexed data."""
        if not data:
            return {}

        summary = {
            "total_videos": len(data),
            "extraction_date": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "uploaders": {},
            "platforms": {},
            "total_duration": 0,
            "total_views": 0,
        }

        for video in data:
            metadata = video.get("metadata", {})
            platform_data = video.get("platformData", {})

            # Count uploaders
            uploader = metadata.get("author", "unknown")
            summary["uploaders"][uploader] = summary["uploaders"].get(uploader, 0) + 1

            # Count platforms
            platform = metadata.get("platform", {}).get("name", "unknown")
            summary["platforms"][platform] = summary["platforms"].get(platform, 0) + 1

            # Accumulate stats
            duration = metadata.get("duration")
            if duration:
                summary["total_duration"] += duration

            views = platform_data.get("view_count")
            if views:
                summary["total_views"] += views

        return summary

    def save_index(self, data: list[dict], filename: str) -> None:
        """Save indexed data to JSON file."""
        if not data:
            print("⚠️  No data to save")
            return

        filepath = self.output_dir / filename
        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"💾 Saved {len(data)} entries to {filepath}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract video/metadata from yt-dlp-supported sites"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Download subcommand
    download_parser = subparsers.add_parser(
        "download", help="Download video and metadata"
    )
    download_parser.add_argument("url", help="Video URL to download")
    download_parser.add_argument(
        "--output-dir", "-o", default=None, help=f"Output directory (default: {aural_config.YTDLP_DIR})"
    )

    # Info subcommand
    info_parser = subparsers.add_parser(
        "info", help="Extract metadata only (no download)"
    )
    info_parser.add_argument("url", help="Video URL to extract info from")
    info_parser.add_argument(
        "--output-dir", "-o", default=None, help=f"Output directory (default: {aural_config.YTDLP_DIR})"
    )
    info_parser.add_argument("--no-cache", action="store_true", help="Skip cache")

    # Index subcommand
    index_parser = subparsers.add_parser(
        "index", help="Index playlist/channel metadata"
    )
    index_parser.add_argument("url", help="Playlist/channel URL to index")
    index_parser.add_argument(
        "--output-dir", "-o", default=None, help=f"Output directory (default: {aural_config.YTDLP_DIR})"
    )
    index_parser.add_argument(
        "--max-videos", "-n", type=int, help="Maximum videos to index"
    )
    index_parser.add_argument("--no-cache", action="store_true", help="Skip cache")

    args = parser.parse_args()

    use_cache = not getattr(args, "no_cache", False)
    extractor = YtDlpExtractor(output_dir=args.output_dir, use_cache=use_cache)

    try:
        if args.command == "download":
            result = extractor.download(args.url)
            print(f"\n✅ Downloaded: {result['metadata']['title']}")
            if result["video"]["filePath"]:
                print(f"📁 File: {result['video']['filePath']}")

        elif args.command == "info":
            result = extractor.extract_info(args.url)
            print(f"\n✅ Title: {result['metadata']['title']}")
            print(f"👤 Author: {result['metadata']['author']}")
            print(f"⏱️  Duration: {result['metadata']['duration']}s")

        elif args.command == "index":
            results = extractor.index_playlist(args.url, args.max_videos)

            if results:
                # Generate filename from URL
                timestamp = datetime.now().strftime("%Y-%m-%d")
                filename = f"index_{timestamp}.json"
                extractor.save_index(results, filename)

                # Generate and print summary
                summary = extractor.generate_summary(results)
                print(f"\n📈 Indexed {summary['total_videos']} videos")
                print(f"⏱️  Total duration: {summary['total_duration'] // 60} minutes")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
