#!/usr/bin/env python3
"""
Match Legacy GWA Orphan Files to Reddit Posts

Matches legacy audio files (without JSON sidecars) to their original Reddit posts
using fuzzy title matching against the extracted Reddit index.

Usage:
    # Scan directory and report match statistics
    uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --scan

    # Process specific author (dry-run)
    uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --author WendysLostBoys --dry-run

    # Create sidecars for high-confidence matches
    uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --threshold 0.9

    # Interactive mode for all files
    uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --interactive
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from config import REDDIT_INDEX_DIR
from rapidfuzz import fuzz


@dataclass
class LegacyFile:
    """Represents a legacy audio file to be matched."""

    path: Path
    authors: list[str]
    title: str
    has_sidecar: bool


@dataclass
class RedditPost:
    """Represents a Reddit post from the index."""

    post_id: str
    author: str
    full_title: str
    reddit_url: str
    json_path: Path


@dataclass
class Match:
    """Represents a match between a legacy file and a Reddit post."""

    legacy_file: LegacyFile
    reddit_post: RedditPost
    confidence: float
    clean_legacy_title: str
    clean_reddit_title: str


def parse_legacy_filename(filename: str) -> tuple[list[str], str]:
    """
    Parse a legacy filename into authors and title.

    Formats:
    - "Author - Title.m4a"
    - "Author1, Author2 & Author3 - Title.m4a"
    - "Author - Title - Track 1.m4a" (multi-track)
    """
    # Remove extension
    name = filename.rsplit(".", 1)[0] if "." in filename else filename

    # Split on " - " to separate author from title
    parts = name.split(" - ", 1)
    if len(parts) != 2:
        return [], name

    author_part, title_part = parts

    # Parse multiple authors: "A, B & C" or "A & B" or just "A"
    # Split on ", " first, then split last element on " & "
    authors = []
    if ", " in author_part:
        comma_parts = author_part.split(", ")
        for part in comma_parts[:-1]:
            authors.append(part.strip())
        # Last part might have " & "
        last = comma_parts[-1]
        if " & " in last:
            ampersand_parts = last.split(" & ")
            authors.extend(p.strip() for p in ampersand_parts)
        else:
            authors.append(last.strip())
    elif " & " in author_part:
        authors = [p.strip() for p in author_part.split(" & ")]
    else:
        authors = [author_part.strip()]

    return authors, title_part.strip()


def extract_part_number(title: str) -> int | None:
    """
    Extract part number from a title if present.

    Matches patterns like:
    - "Part 1", "Part 2", "part 3"
    - "Part 1:", "Part 1 -"
    - "Pt 1", "Pt. 2"

    Returns None if no part number found.
    """
    # Match "part N" or "pt N" or "pt. N" patterns
    match = re.search(r"\b(?:part|pt\.?)\s*(\d+)\b", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def clean_title_for_matching(title: str) -> str:
    """
    Clean a title for fuzzy matching by removing tags and normalizing.

    Removes:
    - GWA tags like [F4M], [Gentle Femdom], etc.
    - Common prefixes like "~" and extra whitespace
    - HTML entities and special characters
    """
    # Remove tags in square brackets
    cleaned = re.sub(r"\[[^\]]*\]", "", title)

    # Remove HTML entities
    cleaned = re.sub(r"&amp;", "&", cleaned)
    cleaned = re.sub(r"&lt;", "<", cleaned)
    cleaned = re.sub(r"&gt;", ">", cleaned)

    # Remove decorative characters
    cleaned = re.sub(r"[~\*]+", " ", cleaned)

    # Normalize whitespace
    cleaned = " ".join(cleaned.split())

    # Remove leading/trailing punctuation
    cleaned = cleaned.strip(" -.,!")

    return cleaned.lower()


AUDIO_EXTENSIONS = (".m4a", ".mp4")


def find_orphan_files(directory: Path, include_collabs: bool = False) -> list[LegacyFile]:
    """Find all audio files (M4A, MP4) without JSON sidecars."""
    orphans = []

    for audio_file in directory.iterdir():
        if not audio_file.is_file() or audio_file.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        json_file = audio_file.with_suffix(".json")
        has_sidecar = json_file.exists()

        authors, title = parse_legacy_filename(audio_file.name)

        # Skip collab files by default (files with multiple authors)
        if not include_collabs and len(authors) > 1:
            continue

        orphans.append(
            LegacyFile(
                path=audio_file,
                authors=authors,
                title=title,
                has_sidecar=has_sidecar,
            )
        )

    return sorted(orphans, key=lambda f: f.path.name)


def find_author_directory(author: str, reddit_dir: Path) -> Path | None:
    """Find the Reddit index directory for an author (case-insensitive)."""
    # Try exact match first
    exact = reddit_dir / author
    if exact.exists():
        return exact

    # Try case-insensitive match
    author_lower = author.lower()
    for subdir in reddit_dir.iterdir():
        if subdir.is_dir() and subdir.name.lower() == author_lower:
            return subdir

    # Try with underscores replaced by spaces and vice versa
    author_variants = [
        author.replace("_", " "),
        author.replace(" ", "_"),
        author.replace("_", ""),
    ]
    for variant in author_variants:
        variant_lower = variant.lower()
        for subdir in reddit_dir.iterdir():
            if subdir.is_dir() and subdir.name.lower() == variant_lower:
                return subdir

    return None


def load_author_posts(author_dir: Path) -> list[RedditPost]:
    """Load all Reddit posts for an author from JSON files."""
    posts = []

    for json_file in author_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            post_id = data.get("post_id", "")
            full_title = data.get("full_title") or data.get("reddit_data", {}).get(
                "title", ""
            )
            reddit_url = data.get("reddit_url") or data.get("reddit_data", {}).get(
                "permalink", ""
            )
            author = data.get("username") or data.get("reddit_data", {}).get(
                "author", ""
            )

            if post_id and full_title:
                posts.append(
                    RedditPost(
                        post_id=post_id,
                        author=author,
                        full_title=full_title,
                        reddit_url=reddit_url,
                        json_path=json_file,
                    )
                )
        except (json.JSONDecodeError, OSError):
            continue

    return posts


def find_best_matches(
    legacy_file: LegacyFile, reddit_dir: Path, top_n: int = 5
) -> list[Match]:
    """Find the best Reddit post matches for a legacy file."""
    matches = []
    clean_legacy = clean_title_for_matching(legacy_file.title)
    legacy_part = extract_part_number(legacy_file.title)

    # Collect candidate posts from all authors
    candidate_posts: list[RedditPost] = []
    for author in legacy_file.authors:
        author_dir = find_author_directory(author, reddit_dir)
        if author_dir:
            candidate_posts.extend(load_author_posts(author_dir))

    if not candidate_posts:
        return []

    # Score each candidate
    for post in candidate_posts:
        clean_reddit = clean_title_for_matching(post.full_title)
        reddit_part = extract_part_number(post.full_title)

        # Check part number compatibility
        # If both have part numbers, they must match
        if (
            legacy_part is not None
            and reddit_part is not None
            and legacy_part != reddit_part
        ):
            # Part numbers conflict - skip this candidate entirely
            continue

        # If legacy has a part number but Reddit doesn't (or vice versa),
        # this is likely a mismatch (e.g., "Part 1" file vs original post)
        part_mismatch_penalty = 0.0
        if legacy_part is not None and reddit_part is None:
            part_mismatch_penalty = 0.3  # Legacy expects a part, Reddit has none
        elif legacy_part is None and reddit_part is not None:
            part_mismatch_penalty = 0.3  # Reddit has a part, legacy doesn't

        # Use multiple scoring methods and take the best
        ratio = fuzz.ratio(clean_legacy, clean_reddit)
        partial = fuzz.partial_ratio(clean_legacy, clean_reddit)
        token_sort = fuzz.token_sort_ratio(clean_legacy, clean_reddit)
        token_set = fuzz.token_set_ratio(clean_legacy, clean_reddit)

        # Weight partial_ratio higher for truncated titles
        score = max(ratio, partial * 0.95, token_sort * 0.9, token_set * 0.9)

        # Apply part mismatch penalty
        score = score * (1.0 - part_mismatch_penalty)

        matches.append(
            Match(
                legacy_file=legacy_file,
                reddit_post=post,
                confidence=score / 100.0,
                clean_legacy_title=clean_legacy,
                clean_reddit_title=clean_reddit,
            )
        )

    # Sort by confidence and return top N
    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches[:top_n]


def create_sidecar(legacy_file: LegacyFile, match: Match) -> Path:
    """Create a JSON sidecar file for a matched legacy file."""
    sidecar_path = legacy_file.path.with_suffix(".json")

    sidecar_data = {
        "author": match.reddit_post.author,
        "title": match.reddit_post.full_title,
        "urls": [match.reddit_post.reddit_url],
        "matched_from": "fuzzy_title_match",
        "confidence": round(match.confidence, 4),
        "reddit_post_id": match.reddit_post.post_id,
        "original_filename": legacy_file.path.name,
    }

    sidecar_path.write_text(
        json.dumps(sidecar_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return sidecar_path


def scan_directory(directory: Path, reddit_dir: Path, include_collabs: bool = False) -> dict:
    """Scan directory and report match statistics."""
    files = find_orphan_files(directory, include_collabs=include_collabs)

    stats = {
        "total_files": len(files),
        "with_sidecar": sum(1 for f in files if f.has_sidecar),
        "without_sidecar": sum(1 for f in files if not f.has_sidecar),
        "high_confidence": 0,  # >= 90%
        "medium_confidence": 0,  # 60-90%
        "low_confidence": 0,  # < 60%
        "no_candidates": 0,
        "unique_authors": set(),
        "authors_not_found": set(),
    }

    orphans = [f for f in files if not f.has_sidecar]

    for f in orphans:
        for author in f.authors:
            stats["unique_authors"].add(author)
            if not find_author_directory(author, reddit_dir):
                stats["authors_not_found"].add(author)

        matches = find_best_matches(f, reddit_dir, top_n=1)
        if not matches:
            stats["no_candidates"] += 1
        elif matches[0].confidence >= 0.9:
            stats["high_confidence"] += 1
        elif matches[0].confidence >= 0.6:
            stats["medium_confidence"] += 1
        else:
            stats["low_confidence"] += 1

    # Convert sets to lists for JSON serialization
    stats["unique_authors"] = sorted(stats["unique_authors"])
    stats["authors_not_found"] = sorted(stats["authors_not_found"])

    return stats


def prompt_interactive_selection(matches: list[Match]) -> tuple[Match | None, bool]:
    """
    Prompt user to select a match interactively.

    Returns:
        (selected_match, should_skip) - match is None if skipped/no match
    """
    print("\n  Top matches:")
    for j, m in enumerate(matches[:3]):
        print(f"    {j + 1}. ({m.confidence * 100:.1f}%) {m.reddit_post.post_id}")
        print(f"       {m.reddit_post.full_title[:70]}...")

    choice = input("\n  Select match (1-3), 's' to skip, or 'n' for no match: ")
    if choice in ["1", "2", "3"]:
        idx = int(choice) - 1
        if idx < len(matches):
            return matches[idx], False
    elif choice.lower() == "s":
        return None, True
    return None, False


def process_files(
    directory: Path,
    reddit_dir: Path,
    dry_run: bool = False,
    interactive: bool = False,
    threshold: float = 0.8,
    filter_author: str | None = None,
    include_collabs: bool = False,
) -> dict:
    """Process orphan files and create sidecars for matches."""
    files = find_orphan_files(directory, include_collabs=include_collabs)
    orphans = [f for f in files if not f.has_sidecar]

    if filter_author:
        filter_lower = filter_author.lower()
        orphans = [
            f for f in orphans if any(a.lower() == filter_lower for a in f.authors)
        ]

    results = {
        "processed": [],
        "skipped": [],
        "no_match": [],
        "sidecars_created": [],
    }

    for i, legacy_file in enumerate(orphans):
        progress = f"[{i + 1}/{len(orphans)}]"
        print(f"\n{progress} {legacy_file.path.name}")
        print(f"  Authors: {', '.join(legacy_file.authors)}")
        print(f"  Title: {legacy_file.title}")

        matches = find_best_matches(legacy_file, reddit_dir, top_n=5)

        if not matches:
            print("  No candidates found - author(s) not in Reddit index")
            results["no_match"].append(
                {
                    "file": str(legacy_file.path),
                    "authors": legacy_file.authors,
                    "reason": "no_candidates",
                }
            )
            continue

        best = matches[0]
        print(f"  Best match ({best.confidence * 100:.1f}%): {best.reddit_post.post_id}")
        print(f"    {best.reddit_post.full_title[:80]}...")

        # Determine action based on confidence and mode
        should_create = False

        if interactive and best.confidence < 0.9:
            selected, should_skip = prompt_interactive_selection(matches)
            if should_skip:
                results["skipped"].append({"file": str(legacy_file.path)})
                continue
            if selected:
                best = selected
                should_create = True
        elif best.confidence >= threshold:
            should_create = True
        else:
            print(f"  Below threshold ({threshold * 100:.0f}%), skipping")
            results["skipped"].append(
                {
                    "file": str(legacy_file.path),
                    "best_confidence": best.confidence,
                }
            )
            continue

        if should_create:
            if dry_run:
                print(f"  Would create sidecar: {legacy_file.path.with_suffix('.json').name}")
                results["processed"].append(
                    {
                        "file": str(legacy_file.path),
                        "matched_to": best.reddit_post.post_id,
                        "confidence": best.confidence,
                    }
                )
            else:
                sidecar = create_sidecar(legacy_file, best)
                print(f"  Created sidecar: {sidecar.name}")
                results["sidecars_created"].append(str(sidecar))
                results["processed"].append(
                    {
                        "file": str(legacy_file.path),
                        "matched_to": best.reddit_post.post_id,
                        "confidence": best.confidence,
                        "sidecar": str(sidecar),
                    }
                )

    return results


def print_scan_results(stats: dict) -> None:
    """Print scan results summary."""
    print("\n" + "=" * 60)
    print("Scan Results")
    print("=" * 60)
    print(f"Total audio files: {stats['total_files']}")
    print(f"  With sidecar: {stats['with_sidecar']}")
    print(f"  Without sidecar (orphans): {stats['without_sidecar']}")
    print()
    print("Orphan match potential:")
    print(f"  High confidence (>=90%): {stats['high_confidence']}")
    print(f"  Medium confidence (60-90%): {stats['medium_confidence']}")
    print(f"  Low confidence (<60%): {stats['low_confidence']}")
    print(f"  No candidates found: {stats['no_candidates']}")
    print()
    print(f"Unique authors in orphans: {len(stats['unique_authors'])}")
    print(f"Authors not in Reddit index: {len(stats['authors_not_found'])}")

    if stats["authors_not_found"]:
        print("\nMissing authors:")
        for author in stats["authors_not_found"][:20]:
            print(f"  - {author}")
        if len(stats["authors_not_found"]) > 20:
            print(f"  ... and {len(stats['authors_not_found']) - 20} more")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match legacy GWA files to Reddit posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan and report statistics
  uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --scan

  # Process specific author (dry-run)
  uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --author WendysLostBoys --dry-run

  # Create sidecars for high-confidence matches
  uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --threshold 0.9

  # Interactive mode
  uv run python match_legacy_orphans.py "/Volumes/Culture 1/Aural/GWA/" --interactive
""",
    )
    parser.add_argument("directory", help="Path to legacy GWA directory")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan directory and report match statistics",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without creating sidecars",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode for reviewing matches",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Confidence threshold for auto-accept (default: 0.8)",
    )
    parser.add_argument(
        "--author",
        help="Filter to files from specific author",
    )
    parser.add_argument(
        "--output-unmatched",
        help="Path to output unmatched files JSON",
    )
    parser.add_argument(
        "--include-collabs",
        action="store_true",
        help="Include files with multiple authors (collabs are skipped by default)",
    )

    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1

    if args.scan:
        print(f"Scanning {directory}...")
        print(f"Reddit index: {REDDIT_INDEX_DIR}")
        if not args.include_collabs:
            print("Skipping collab files (use --include-collabs to include)")
        stats = scan_directory(directory, REDDIT_INDEX_DIR, include_collabs=args.include_collabs)
        print_scan_results(stats)
        return 0

    # Process mode
    results = process_files(
        directory,
        REDDIT_INDEX_DIR,
        dry_run=args.dry_run,
        interactive=args.interactive,
        threshold=args.threshold,
        filter_author=args.author,
        include_collabs=args.include_collabs,
    )

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Processed: {len(results['processed'])}")
    print(f"Skipped: {len(results['skipped'])}")
    print(f"No match found: {len(results['no_match'])}")
    if not args.dry_run:
        print(f"Sidecars created: {len(results['sidecars_created'])}")

    # Output unmatched files if requested
    if args.output_unmatched and results["no_match"]:
        output_path = Path(args.output_unmatched)
        output_path.write_text(
            json.dumps(results["no_match"], indent=2), encoding="utf-8"
        )
        print(f"\nUnmatched files written to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
