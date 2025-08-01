#!/usr/bin/env python3
"""
GWASI Reddit Audio Data Extractor

This script extracts data from gwasi.com, which indexes Reddit audio content.
It fetches the JSON data sources and processes them to extract comprehensive
metadata about Reddit audio posts for further analysis with PRAW.

Data sources:
- https://gwasi.com/delta.json (recent updates)
- https://gwasi.com/base_*.json (main dataset)
"""

import requests
import json
import csv
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
from urllib.parse import urlparse, parse_qs


class GwasiExtractor:
    def __init__(
        self, output_dir: str = "extracted_data", consecutive_404_limit: int = 5
    ):
        self.base_url = "https://gwasi.com"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.consecutive_404_limit = consecutive_404_limit

        # Create subdirectories for intermediate files
        self.raw_data_dir = self.output_dir / "raw_json"
        self.raw_data_dir.mkdir(exist_ok=True)

        # Track current base version (will be set when discovered)
        self.current_base_version = None
        self.current_base_dir = None
        self.version_file = self.output_dir / "current_base_version.txt"

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def get_base_version_from_delta(self, delta_data: Dict) -> Optional[str]:
        """
        Extract base version from delta.json data.
        Returns: base version string (e.g., "37997ef38e")
        """
        if not delta_data:
            return None

        base_version = delta_data.get("base")
        if base_version:
            print(f"📁 Found base version in delta.json: {base_version}")
            return base_version
        else:
            print("⚠️  No 'base' field found in delta.json")
            return None

    def download_and_process_base_files(
        self, base_dir_url: str, use_cache: bool = True, max_files: Optional[int] = None
    ) -> List[Dict]:
        """
        Download and process base files sequentially until consecutive 404 limit is reached.
        Returns all entries from successfully downloaded files.
        """
        print(
            f"🔍 Downloading base files (will stop after {self.consecutive_404_limit} consecutive 404s)..."
        )

        all_entries = []
        current_number = 1
        consecutive_404s = 0
        last_successful_file = 0

        while consecutive_404s < self.consecutive_404_limit:
            if max_files and current_number > max_files:
                print(f"📊 Reached max files limit ({max_files})")
                break

            file_url = f"{base_dir_url}/{current_number}.json"
            print(f"📥 Attempting to download file {current_number}...")

            try:
                base_data = self.fetch_json_data(file_url, use_cache)
                if base_data and "entries" in base_data:
                    # Successfully got data
                    base_entries = [
                        self.parse_entry(entry) for entry in base_data["entries"]
                    ]
                    base_entries = [
                        e for e in base_entries if e
                    ]  # Remove empty entries
                    all_entries.extend(base_entries)
                    last_successful_file = current_number
                    consecutive_404s = 0  # Reset counter on successful file
                    print(
                        f"✅ Downloaded file {current_number}: {len(base_entries)} entries"
                    )
                else:
                    # File exists but has no entries or invalid JSON
                    consecutive_404s += 1
                    print(
                        f"⚠️  File {current_number} exists but has no valid entries (consecutive 404s: {consecutive_404s}/{self.consecutive_404_limit})"
                    )

            except requests.RequestException as e:
                if "404" in str(e) or "Not Found" in str(e):
                    consecutive_404s += 1
                    print(
                        f"❌ 404 for file {current_number} (consecutive: {consecutive_404s}/{self.consecutive_404_limit})"
                    )
                else:
                    # Other network errors, treat as 404
                    consecutive_404s += 1
                    print(
                        f"🌐 Network error for file {current_number}: {e} (consecutive 404s: {consecutive_404s}/{self.consecutive_404_limit})"
                    )
            except json.JSONDecodeError:
                # Invalid JSON, treat as 404
                consecutive_404s += 1
                print(
                    f"📄 Invalid JSON for file {current_number} (consecutive 404s: {consecutive_404s}/{self.consecutive_404_limit})"
                )

            current_number += 1
            # Small delay to be respectful
            time.sleep(0.1)

        print(
            f"📊 Downloaded {last_successful_file} base files with {len(all_entries)} total entries"
        )
        print(f"📊 Stopped after {consecutive_404s} consecutive 404s")
        return all_entries

    def get_current_base_version(self) -> Optional[str]:
        """
        Get the currently cached base version.
        """
        if self.version_file.exists():
            try:
                with open(self.version_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except IOError:
                pass
        return None

    def save_base_version(self, version: str):
        """
        Save the current base version to file.
        """
        try:
            with open(self.version_file, "w", encoding="utf-8") as f:
                f.write(version)
            print(f"📝 Saved base version: {version}")
        except IOError as e:
            print(f"⚠️  Warning: Could not save base version: {e}")

    def setup_base_directory(self, base_dir_name: str):
        """
        Setup directory structure for a specific base version.
        """
        self.current_base_version = base_dir_name
        self.current_base_dir = self.raw_data_dir / base_dir_name
        self.current_base_dir.mkdir(exist_ok=True)
        print(f"📁 Using base directory: {self.current_base_dir}")

    def needs_full_base_download(self, current_base_dir: str) -> bool:
        """
        Determine if we need to download all base files or just delta.
        Note: setup_base_directory should be called before this method.
        """
        if not current_base_dir or not self.current_base_dir:
            return False

        cached_version = self.get_current_base_version()

        if not cached_version:
            print(f"📊 No cached base version found, will download all base files")
            return True

        if cached_version != current_base_dir:
            print(f"🔄 Base version changed: {cached_version} → {current_base_dir}")
            print(f"📊 Will download all base files for new version")
            return True

        # Check if base files exist for this version
        existing_files = list(self.current_base_dir.glob("*.json"))
        if not existing_files:
            print(
                f"📊 No cached base files found for {current_base_dir}, will download all"
            )
            return True

        print(
            f"✅ Base version unchanged ({current_base_dir}), found {len(existing_files)} cached files"
        )
        print(f"📊 Will only update with delta.json")
        return False

    def get_local_filename(self, url: str) -> Tuple[Path, str]:
        """
        Generate a local directory and filename for a URL.
        Returns: (directory_path, filename)
        """
        # Extract filename from URL
        if url.endswith("/delta.json"):
            return self.raw_data_dir, "delta.json"
        elif "/base_" in url:
            # Extract file number from URL (e.g., "1.json", "2.json")
            filename = url.split("/")[-1]  # Get the last part (e.g., "1.json")
            return self.current_base_dir, filename

        # Fallback: use last part of URL in main raw_data_dir
        filename = url.split("/")[-1]
        return self.raw_data_dir, filename

    def save_intermediate_file(self, data: Dict, directory: Path, filename: str):
        """
        Save JSON data to intermediate file.
        """
        filepath = directory / filename
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(
                f"💾 Saved intermediate file: {filepath.relative_to(self.output_dir)}"
            )
        except IOError as e:
            print(f"⚠️  Warning: Could not save intermediate file {filename}: {e}")

    def load_intermediate_file(self, directory: Path, filename: str) -> Optional[Dict]:
        """
        Load JSON data from intermediate file if it exists.
        """
        filepath = directory / filename
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"📂 Loaded cached file: {filepath.relative_to(self.output_dir)}")
                return data
            except (IOError, json.JSONDecodeError) as e:
                print(f"⚠️  Warning: Could not load cached file {filename}: {e}")
        return None

    def fetch_json_data(self, url: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Fetch JSON data from URL with error handling and caching.
        """
        directory, filename = self.get_local_filename(url)

        # Try to load from cache first
        if use_cache:
            cached_data = self.load_intermediate_file(directory, filename)
            if cached_data:
                return cached_data

        # Fetch from network
        try:
            print(f"📥 Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()
            print(f"✅ Successfully fetched {len(str(data))} characters of data")

            # Save to cache
            self.save_intermediate_file(data, directory, filename)

            return data

        except requests.RequestException as e:
            print(f"❌ Network error fetching {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error for {url}: {e}")
            return None

    def parse_entry(self, entry: List) -> Dict:
        """
        Parse a single entry from the JSON data.

        Based on analysis, entries appear to be arrays with:
        [0] - Post ID
        [1] - Subreddit
        [2] - Username
        [3] - Post type/title
        [4] - Full title with tags
        [5] - Timestamp
        [6] - Comments count
        [7] - Score
        [8] - Additional info (optional)
        """
        try:
            parsed = {
                "post_id": entry[0] if len(entry) > 0 else None,
                "subreddit": entry[1] if len(entry) > 1 else None,
                "username": entry[2] if len(entry) > 2 else None,
                "post_type": entry[3] if len(entry) > 3 else None,
                "full_title": entry[4] if len(entry) > 4 else None,
                "timestamp": entry[5] if len(entry) > 5 else None,
                "comments": entry[6] if len(entry) > 6 else None,
                "score": entry[7] if len(entry) > 7 else None,
                "additional_info": entry[8] if len(entry) > 8 else None,
            }

            # Convert timestamp to readable date
            if parsed["timestamp"]:
                try:
                    parsed["date"] = datetime.fromtimestamp(
                        parsed["timestamp"]
                    ).isoformat()
                except (ValueError, TypeError):
                    parsed["date"] = None
            else:
                parsed["date"] = None

            # Extract Reddit URL
            if parsed["post_id"]:
                parsed["reddit_url"] = (
                    f"https://www.reddit.com/r/{parsed['subreddit']}/comments/{parsed['post_id']}/"
                )
            else:
                parsed["reddit_url"] = None

            # Extract tags from full title
            if parsed["full_title"]:
                tags = re.findall(r"\[([^\]]+)\]", parsed["full_title"])
                parsed["tags"] = tags
                parsed["tag_string"] = ", ".join(tags)
            else:
                parsed["tags"] = []
                parsed["tag_string"] = ""

            # Determine content type
            parsed["content_type"] = self.determine_content_type(
                parsed["post_type"], parsed["tags"]
            )

            # Extract duration if available
            parsed["duration"] = self.extract_duration(parsed["full_title"] or "")

            return parsed

        except (IndexError, TypeError) as e:
            print(f"⚠️  Warning: Error parsing entry {entry}: {e}")
            return {}

    def determine_content_type(self, post_type: str, tags: List[str]) -> str:
        """Determine if content is audio, script, or other."""
        if not post_type:
            return "unknown"

        post_type_lower = post_type.lower()
        tags_lower = [tag.lower() for tag in tags]

        if "script" in post_type_lower or any("script" in tag for tag in tags_lower):
            return "script"
        elif any(
            keyword in post_type_lower for keyword in ["audio", "ramblefap", "fill"]
        ):
            return "audio"
        elif "verification" in post_type_lower:
            return "verification"
        else:
            return "other"

    def extract_duration(self, title: str) -> Optional[str]:
        """Extract duration from title (e.g., '15m', '1h23m')."""
        if not title:
            return None

        # Look for patterns like 15m, 1h23m, 23:45, etc.
        duration_patterns = [
            r"(\d+h\d+m)",  # 1h23m
            r"(\d+h)",  # 1h
            r"(\d+m)",  # 23m
            r"(\d+:\d+)",  # 23:45
        ]

        for pattern in duration_patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1)

        return None

    def save_to_csv(self, data: List[Dict], filename: str):
        """Save extracted data to CSV file."""
        if not data:
            print("⚠️  No data to save")
            return

        filepath = self.output_dir / filename

        # Define CSV columns
        columns = [
            "post_id",
            "subreddit",
            "username",
            "post_type",
            "full_title",
            "date",
            "timestamp",
            "comments",
            "score",
            "content_type",
            "duration",
            "reddit_url",
            "tag_string",
            "additional_info",
        ]

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=columns)
                writer.writeheader()

                for item in data:
                    # Only write columns that exist in our column list
                    row = {col: item.get(col, "") for col in columns}
                    writer.writerow(row)

            print(f"💾 Saved {len(data)} entries to {filepath}")

        except IOError as e:
            print(f"❌ Error saving to CSV: {e}")

    def save_to_json(self, data: List[Dict], filename: str):
        """Save extracted data to JSON file."""
        if not data:
            print("⚠️  No data to save")
            return

        filepath = self.output_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as jsonfile:
                json.dump(data, jsonfile, indent=2, ensure_ascii=False)

            print(f"💾 Saved {len(data)} entries to {filepath}")

        except IOError as e:
            print(f"❌ Error saving to JSON: {e}")

    def load_from_cache_only(self) -> List[Dict]:
        """
        Load and process data from cached intermediate files only.
        """
        print("🚀 Loading data from cached files...")

        all_entries = []

        # Load delta data
        delta_data = self.load_intermediate_file(self.raw_data_dir, "delta.json")
        if delta_data and "entries" in delta_data:
            delta_entries = [self.parse_entry(entry) for entry in delta_data["entries"]]
            delta_entries = [e for e in delta_entries if e]
            all_entries.extend(delta_entries)
            print(f"✅ Loaded {len(delta_entries)} delta entries from cache")

        # Find all base version directories
        base_version_dirs = [
            d
            for d in self.raw_data_dir.iterdir()
            if d.is_dir() and d.name.startswith("base_")
        ]

        if not base_version_dirs:
            print("⚠️  No base version directories found in cache")
        else:
            # Use the most recent version (lexicographically last)
            latest_base_dir = sorted(base_version_dirs)[-1]
            print(f"📁 Using latest base version: {latest_base_dir.name}")

            # Load base files from that version
            base_files = list(latest_base_dir.glob("*.json"))
            base_files.sort(key=lambda x: int(x.stem) if x.stem.isdigit() else 0)

            for filepath in base_files:
                filename = filepath.name
                base_data = self.load_intermediate_file(latest_base_dir, filename)
                if base_data and "entries" in base_data:
                    base_entries = [
                        self.parse_entry(entry) for entry in base_data["entries"]
                    ]
                    base_entries = [e for e in base_entries if e]
                    all_entries.extend(base_entries)
                    print(
                        f"✅ Loaded {len(base_entries)} entries from {latest_base_dir.name}/{filename}"
                    )

        # Remove duplicates
        print("\n🔄 Removing duplicates...")
        seen_ids = set()
        unique_entries = []
        for entry in all_entries:
            post_id = entry.get("post_id")
            if post_id and post_id not in seen_ids:
                seen_ids.add(post_id)
                unique_entries.append(entry)

        print(f"✅ Final dataset: {len(unique_entries)} unique entries from cache")
        return unique_entries

    def extract_all_data(
        self,
        save_format: str = "both",
        max_files: Optional[int] = None,
        use_cache: bool = True,
        force_full_download: bool = False,
    ) -> List[Dict]:
        """
        Main extraction method. Fetches and processes all available data.

        Args:
            save_format: 'csv', 'json', or 'both'

        Returns:
            List of parsed entries
        """
        print("🚀 Starting GWASI data extraction...")

        all_entries = []

        # Step 1: Fetch delta data to get base version and recent updates
        print("\n📊 Fetching delta data...")
        delta_url = f"{self.base_url}/delta.json"
        delta_data = self.fetch_json_data(delta_url, use_cache)

        if not delta_data:
            print("❌ Failed to fetch delta.json - cannot proceed")
            return []

        # Extract base version from delta.json
        base_version = self.get_base_version_from_delta(delta_data)
        if not base_version:
            print("❌ No base version found in delta.json - cannot proceed")
            return []

        # Process delta entries
        if "entries" in delta_data:
            delta_entries = [self.parse_entry(entry) for entry in delta_data["entries"]]
            delta_entries = [e for e in delta_entries if e]  # Remove empty entries
            all_entries.extend(delta_entries)
            print(f"✅ Processed {len(delta_entries)} delta entries")

        # Step 2: Setup base directory and determine if we need to download base files
        base_dir_name = f"base_{base_version}"
        base_dir_url = f"{self.base_url}/{base_dir_name}"
        print(f"🔍 Base version: {base_version}")
        print(f"🔍 Base directory URL: {base_dir_url}")

        # Always setup the base directory first
        self.setup_base_directory(base_dir_name)

        needs_full_download = self.needs_full_base_download(base_dir_name)

        # Step 3: Handle base files
        if needs_full_download or max_files or force_full_download:
            print(f"\n📊 Fetching base data...")
            print(
                f"🔧 Debug: needs_full_download={needs_full_download}, max_files={max_files}, force_full_download={force_full_download}"
            )

            # Download and process base files in one go
            base_entries = self.download_and_process_base_files(
                base_dir_url, use_cache, max_files
            )
            all_entries.extend(base_entries)
            print(f"✅ Added {len(base_entries)} base entries to dataset")

            # Save the base version after successful download
            self.save_base_version(base_dir_name)

        else:
            # Load base data from cache since version hasn't changed
            print(f"\n📂 Loading base data from cache...")
            print(f"🔧 Debug: Looking for files in {self.current_base_dir}")
            base_files = list(self.current_base_dir.glob("*.json"))
            print(f"🔧 Debug: Found {len(base_files)} cached files")
            base_files.sort(key=lambda x: int(x.stem) if x.stem.isdigit() else 0)

            for filepath in base_files:
                filename = filepath.name
                base_data = self.load_intermediate_file(self.current_base_dir, filename)
                if base_data and "entries" in base_data:
                    base_entries = [
                        self.parse_entry(entry) for entry in base_data["entries"]
                    ]
                    base_entries = [e for e in base_entries if e]
                    all_entries.extend(base_entries)
                    print(
                        f"✅ Loaded {len(base_entries)} entries from cached {base_dir_name}/{filename}"
                    )

            print(f"✅ Loaded base data from {len(base_files)} cached files")

        # Step 4: Remove duplicates based on post_id
        print("\n🔄 Removing duplicates...")
        seen_ids = set()
        unique_entries = []
        for entry in all_entries:
            post_id = entry.get("post_id")
            if post_id and post_id not in seen_ids:
                seen_ids.add(post_id)
                unique_entries.append(entry)

        print(f"✅ Final dataset: {len(unique_entries)} unique entries")

        # Step 5: Save data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if save_format in ["csv", "both"]:
            self.save_to_csv(unique_entries, f"gwasi_data_{timestamp}.csv")

        if save_format in ["json", "both"]:
            self.save_to_json(unique_entries, f"gwasi_data_{timestamp}.json")

        # Generate summary report
        self.generate_summary(unique_entries, timestamp)

        return unique_entries

    def generate_summary(self, data: List[Dict], timestamp: str):
        """Generate a summary report of the extracted data."""
        if not data:
            return

        summary = {
            "total_entries": len(data),
            "extraction_date": datetime.now().isoformat(),
            "subreddits": {},
            "content_types": {},
            "date_range": {"earliest": None, "latest": None},
        }

        # Analyze data
        dates = []
        for entry in data:
            # Count subreddits
            subreddit = entry.get("subreddit", "unknown")
            summary["subreddits"][subreddit] = (
                summary["subreddits"].get(subreddit, 0) + 1
            )

            # Count content types
            content_type = entry.get("content_type", "unknown")
            summary["content_types"][content_type] = (
                summary["content_types"].get(content_type, 0) + 1
            )

            # Collect dates
            if entry.get("date"):
                dates.append(entry["date"])

        # Date range
        if dates:
            dates.sort()
            summary["date_range"]["earliest"] = dates[0]
            summary["date_range"]["latest"] = dates[-1]

        # Save summary
        summary_path = self.output_dir / f"summary_{timestamp}.json"
        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            print(f"📈 Summary saved to {summary_path}")
        except IOError as e:
            print(f"❌ Error saving summary: {e}")

        # Print summary to console
        print(f"\n📈 EXTRACTION SUMMARY")
        print(f"{'='*50}")
        print(f"Total entries: {summary['total_entries']:,}")
        print(
            f"Date range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}"
        )
        print(f"\nTop subreddits:")
        for sub, count in sorted(
            summary["subreddits"].items(), key=lambda x: x[1], reverse=True
        )[:10]:
            print(f"  {sub}: {count:,}")
        print(f"\nContent types:")
        for ctype, count in sorted(
            summary["content_types"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {ctype}: {count:,}")


def main():
    parser = argparse.ArgumentParser(description="Extract data from gwasi.com")
    parser.add_argument(
        "--output",
        "-o",
        default="extracted_data",
        help="Output directory (default: extracted_data)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["csv", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--max-files",
        "-m",
        type=int,
        help="Maximum number of base files to download (for testing)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching, always fetch fresh data",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Only use cached data, do not fetch from network",
    )
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="Force download of all base files even if version unchanged",
    )
    parser.add_argument(
        "--consecutive-404s",
        "-c",
        type=int,
        default=15,
        help="Number of consecutive 404s before stopping file discovery (default: 5)",
    )

    args = parser.parse_args()

    extractor = GwasiExtractor(args.output, args.consecutive_404s)
    try:
        if args.cache_only:
            # Load only from cached files
            data = extractor.load_from_cache_only()

            # Save processed data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if args.format in ["csv", "both"]:
                extractor.save_to_csv(data, f"gwasi_data_{timestamp}.csv")
            if args.format in ["json", "both"]:
                extractor.save_to_json(data, f"gwasi_data_{timestamp}.json")
            extractor.generate_summary(data, timestamp)
        else:
            # Normal extraction with optional caching
            use_cache = not args.no_cache
            data = extractor.extract_all_data(
                args.format, args.max_files, use_cache, args.force_full
            )

        print(f"\n🎉 Extraction complete! Found {len(data)} entries.")
        print(f"📁 Data saved to: {extractor.output_dir}")
        print(f"📂 Intermediate files saved to: {extractor.raw_data_dir}")

    except KeyboardInterrupt:
        print("\n⏹️  Extraction interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
