#!/usr/bin/env python3
"""
Match Legacy Audio Files to Extracted Reddit Posts

For legacy M4A files without sidecars, find matching Reddit posts in
extracted_data/reddit by comparing filenames to post titles.

Usage:
    uv run python match_legacy_to_reddit.py "/Volumes/Culture 1/Aural/GWA/"
    uv run python match_legacy_to_reddit.py "/Volumes/Culture 1/Aural/GWA/" --limit 5
    uv run python match_legacy_to_reddit.py "/Volumes/Culture 1/Aural/GWA/" --import
"""

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from analyze_download_import import AnalyzeDownloadImportPipeline
from stashapp_importer import StashappClient


def normalize_text(text: str) -> str:
    """Normalize text for comparison by removing special chars and lowercasing."""
    if not text:
        return ""
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    # Remove common variations
    text = text.lower()
    # Remove special characters but keep alphanumeric and spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title_from_reddit_title(full_title: str) -> str:
    """Extract the core title from a Reddit post title, removing tags."""
    # Remove [tag] patterns
    title = re.sub(r"\[.*?\]", "", full_title)
    # Remove extra whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def parse_legacy_filename(filename: str) -> tuple[str, str] | None:
    """Parse legacy filename into (performer, title)."""
    # Pattern: "Performer - Title.m4a"
    stem = Path(filename).stem
    match = re.match(r"^(.+?)\s*-\s*(.+)$", stem)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None


def find_matching_post(
    performer: str, title: str, reddit_dir: Path, verbose: bool = False
) -> Path | None:
    """Find a matching Reddit post JSON for the given performer and title."""
    # Check performer directory
    performer_dir = reddit_dir / performer
    if not performer_dir.exists():
        # Try case-insensitive match
        for d in reddit_dir.iterdir():
            if d.is_dir() and d.name.lower() == performer.lower():
                performer_dir = d
                break
        else:
            if verbose:
                print(f"  No directory for performer: {performer}")
            return None

    normalized_title = normalize_text(title)
    if verbose:
        print(f"  Looking for: '{normalized_title}'")

    best_match = None
    best_score = 0

    for json_file in performer_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            full_title = data.get("full_title", "")
            core_title = extract_title_from_reddit_title(full_title)
            normalized_core = normalize_text(core_title)

            # Check for substring match
            if normalized_title in normalized_core or normalized_core in normalized_title:
                # Calculate match score based on length similarity
                score = min(len(normalized_title), len(normalized_core)) / max(
                    len(normalized_title), len(normalized_core), 1
                )
                if score > best_score:
                    best_score = score
                    best_match = json_file
                    if verbose:
                        print(f"    Match ({score:.2f}): {core_title[:60]}")

            # Also check individual words for partial matches
            title_words = set(normalized_title.split())
            core_words = set(normalized_core.split())
            if len(title_words) >= 3:
                common = title_words & core_words
                word_score = len(common) / max(len(title_words), 1)
                if word_score > 0.7 and word_score > best_score:
                    best_score = word_score
                    best_match = json_file
                    if verbose:
                        print(f"    Word match ({word_score:.2f}): {core_title[:60]}")

        except (json.JSONDecodeError, KeyError):
            continue

    return best_match


def find_legacy_files_without_sidecars(directory: Path) -> list[Path]:
    """Find M4A files that don't have corresponding JSON sidecars."""
    results = []
    for m4a_file in sorted(directory.glob("*.m4a")):
        json_sidecar = m4a_file.with_suffix(".json")
        if not json_sidecar.exists():
            results.append(m4a_file)
    return results


def compute_file_sha256(file_path: Path) -> str | None:
    """Compute SHA-256 hash of file."""
    try:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"  Error computing hash: {e}")
        return None


def verify_scene_in_stashapp(client: StashappClient, audio_sha256: str) -> dict | None:
    """Verify a scene exists in Stashapp with matching audio_sha256 fingerprint."""
    return client.find_scene_by_fingerprint("audio_sha256", audio_sha256)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match legacy audio files to extracted Reddit posts"
    )
    parser.add_argument("directory", help="Path to legacy GWA directory")
    parser.add_argument("--filter", type=str, help="Only process files containing this string (case-insensitive)")
    parser.add_argument("--limit", type=int, help="Max files to process")
    parser.add_argument(
        "--import", dest="do_import", action="store_true", help="Run import pipeline"
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    directory = Path(args.directory)
    reddit_dir = Path("extracted_data/reddit")

    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1

    if not reddit_dir.exists():
        print(f"Error: Reddit data directory not found: {reddit_dir}")
        return 1

    # Find M4A files without sidecars
    legacy_files = find_legacy_files_without_sidecars(directory)
    print(f"Found {len(legacy_files)} M4A files without sidecars")

    # Apply filename filter if specified
    if args.filter:
        filter_lower = args.filter.lower()
        legacy_files = [f for f in legacy_files if filter_lower in f.name.lower()]
        print(f"Filtered to {len(legacy_files)} files matching '{args.filter}'")

    if args.limit:
        legacy_files = legacy_files[: args.limit]

    if not legacy_files:
        return 0

    # Initialize pipeline and Stashapp client if importing
    pipeline = None
    client = None
    if args.do_import:
        pipeline = AnalyzeDownloadImportPipeline({"verbose": args.verbose})
        client = StashappClient()

    results = {"matched": [], "not_found": [], "imported": [], "deleted": [], "failed": []}

    for i, m4a_path in enumerate(legacy_files):
        print(f"\n[{i + 1}/{len(legacy_files)}] {m4a_path.name}")

        # Parse filename
        parsed = parse_legacy_filename(m4a_path.name)
        if not parsed:
            print("  Could not parse filename")
            results["not_found"].append(str(m4a_path))
            continue

        performer, title = parsed
        if args.verbose:
            print(f"  Performer: {performer}")
            print(f"  Title: {title}")

        # Find matching post
        match = find_matching_post(performer, title, reddit_dir, args.verbose)
        if match:
            print(f"  Found: {match.name}")
            results["matched"].append({"file": str(m4a_path), "post": str(match)})

            if args.do_import and pipeline and client:
                # Compute fingerprint of legacy file before import
                legacy_sha256 = compute_file_sha256(m4a_path)
                if not legacy_sha256:
                    results["failed"].append(str(m4a_path))
                    print("  Failed to compute fingerprint")
                    continue

                print("  Running import pipeline...")
                try:
                    result = pipeline.process_post(match)
                    if result.get("success"):
                        results["imported"].append(str(m4a_path))
                        print(f"  Imported: Scene {result.get('stashSceneId')}")

                        # Verify scene exists with matching fingerprint
                        print("  Verifying fingerprint in Stashapp...")
                        scene = verify_scene_in_stashapp(client, legacy_sha256)
                        if scene:
                            print(f"  Verified: Scene {scene['id']} has matching fingerprint")
                            # Delete legacy file
                            try:
                                m4a_path.unlink()
                                results["deleted"].append(str(m4a_path))
                                print(f"  Deleted: {m4a_path.name}")
                            except Exception as e:
                                print(f"  Error deleting file: {e}")
                        else:
                            print("  Warning: Fingerprint not found in Stashapp, keeping file")
                    else:
                        results["failed"].append(str(m4a_path))
                        print(f"  Import failed: {result.get('error')}")
                except Exception as e:
                    results["failed"].append(str(m4a_path))
                    print(f"  Import error: {e}")
        else:
            print("  No match found")
            results["not_found"].append(str(m4a_path))

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Matched: {len(results['matched'])}")
    print(f"Not found: {len(results['not_found'])}")
    if args.do_import:
        print(f"Imported: {len(results['imported'])}")
        print(f"Deleted: {len(results['deleted'])}")
        print(f"Failed: {len(results['failed'])}")

    if results["matched"] and not args.do_import:
        print("\nMatched files (use --import to process):")
        for m in results["matched"][:10]:
            print(f"  - {Path(m['file']).name}")
            print(f"    → {Path(m['post']).name}")
        if len(results["matched"]) > 10:
            print(f"  ... and {len(results['matched']) - 10} more")

    return 0


if __name__ == "__main__":
    exit(main())
