#!/usr/bin/env python3
"""
Migrate existing data directories to new unified structure.

This script moves data from the old scattered directory structure to the
new centralized aural_data/ directory for easier backup and management.

Usage:
    uv run python migrate_data_directories.py --dry-run  # Preview changes
    uv run python migrate_data_directories.py            # Execute migration
    uv run python migrate_data_directories.py --verify   # Verify after migration
"""

import argparse
import shutil
from pathlib import Path

from config import (
    ANALYSIS_DIR,
    AO3_DIR,
    AURAL_DATA_DIR,
    GWASI_INDEX_DIR,
    HOTAUDIO_DIR,
    PROCESSED_POSTS_FILE,
    REDDIT_INDEX_DIR,
    REDDIT_SAVED_ARCHIVED_DIR,
    REDDIT_SAVED_PENDING_DIR,
    RELEASES_DIR,
    SCRIPTBIN_DIR,
    YTDLP_DIR,
    ensure_directories,
)

# Project root
PROJECT_ROOT = Path(__file__).parent

# Migration mappings: (source, destination, description)
# For directories, contents will be merged if destination exists
MIGRATIONS: list[tuple[Path, Path, str]] = [
    # GWASI index files
    (
        PROJECT_ROOT / "extracted_data" / "raw_json",
        GWASI_INDEX_DIR / "raw_json",
        "GWASI raw JSON partitions",
    ),
    (
        PROJECT_ROOT / "extracted_data" / "base_entries_cache.json",
        GWASI_INDEX_DIR / "base_entries_cache.json",
        "GWASI base entries cache",
    ),
    (
        PROJECT_ROOT / "extracted_data" / "current_base_version.txt",
        GWASI_INDEX_DIR / "current_base_version.txt",
        "GWASI version tracker",
    ),
    # GWASI data snapshots (glob pattern)
    (
        PROJECT_ROOT / "extracted_data" / "gwasi_data_*.json",
        GWASI_INDEX_DIR,
        "GWASI data snapshots",
    ),
    (
        PROJECT_ROOT / "extracted_data" / "summary_*.json",
        GWASI_INDEX_DIR,
        "GWASI summary files",
    ),
    # Reddit index
    (
        PROJECT_ROOT / "extracted_data" / "reddit",
        REDDIT_INDEX_DIR,
        "Reddit post metadata",
    ),
    # Releases
    (
        PROJECT_ROOT / "data" / "releases",
        RELEASES_DIR,
        "Processed releases",
    ),
    # Tracking
    (
        PROJECT_ROOT / "data" / "processed_posts.json",
        PROCESSED_POSTS_FILE,
        "Processed posts tracker",
    ),
    # Analysis
    (
        PROJECT_ROOT / "analysis_results",
        ANALYSIS_DIR,
        "LLM analysis results",
    ),
    # Reddit saved posts
    (
        PROJECT_ROOT / "saved_posts",
        REDDIT_SAVED_PENDING_DIR,
        "Reddit saved posts (pending)",
    ),
    (
        PROJECT_ROOT / "saved_posts_archived",
        REDDIT_SAVED_ARCHIVED_DIR,
        "Reddit saved posts (archived)",
    ),
    # Platform sources
    (
        PROJECT_ROOT / "ao3_data",
        AO3_DIR,
        "AO3 content",
    ),
    (
        PROJECT_ROOT / "scriptbin_data",
        SCRIPTBIN_DIR,
        "Script content",
    ),
    (
        PROJECT_ROOT / "hotaudio_data",
        HOTAUDIO_DIR,
        "HotAudio content",
    ),
    (
        PROJECT_ROOT / "ytdlp_data",
        YTDLP_DIR,
        "yt-dlp downloads",
    ),
    (
        PROJECT_ROOT / "pornhub_data",
        YTDLP_DIR,
        "PornHub downloads (merged into ytdlp)",
    ),
]

# Directories to clean up after migration (test/temp data or already imported)
CLEANUP_DIRS = [
    PROJECT_ROOT / "data" / "cyoa",  # Already imported to Stashapp
    PROJECT_ROOT / "data" / "enrichment",
    PROJECT_ROOT / "data" / "hotaudio-test",
    PROJECT_ROOT / "data" / "hotaudio-crypto",
    PROJECT_ROOT / "data" / "soundgasm",
    PROJECT_ROOT / "data" / "test-extract",
    PROJECT_ROOT / "data" / "test_hotaudio",
]


def count_files(path: Path) -> int:
    """Count files in a path (file or directory)."""
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    return sum(1 for _ in path.rglob("*") if _.is_file())


def get_size(path: Path) -> int:
    """Get total size of path in bytes."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def format_size(size: int) -> str:
    """Format size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def migrate_path(
    source: Path, dest: Path, description: str, dry_run: bool = True
) -> tuple[int, int]:
    """
    Migrate a source path to destination.

    Returns (files_moved, bytes_moved).
    """
    # Handle glob patterns
    if "*" in str(source):
        parent = source.parent
        pattern = source.name
        sources = list(parent.glob(pattern))
        total_files = 0
        total_bytes = 0
        for src in sources:
            f, b = migrate_path(src, dest / src.name, f"{description}: {src.name}", dry_run)
            total_files += f
            total_bytes += b
        return total_files, total_bytes

    if not source.exists():
        print(f"  SKIP: {source} (does not exist)")
        return 0, 0

    files = count_files(source)
    size = get_size(source)

    if dry_run:
        print(f"  WOULD MOVE: {source}")
        print(f"             -> {dest}")
        print(f"             ({files} files, {format_size(size)})")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)

        if source.is_file():
            if dest.exists():
                print(f"  SKIP: {dest} already exists")
                return 0, 0
            shutil.move(str(source), str(dest))
            print(f"  MOVED: {source} -> {dest}")
        else:
            # Directory - merge contents
            if dest.exists():
                # Merge by moving contents
                for item in source.iterdir():
                    item_dest = dest / item.name
                    if item_dest.exists():
                        if item.is_dir():
                            # Recursively merge directories
                            for subitem in item.rglob("*"):
                                if subitem.is_file():
                                    rel = subitem.relative_to(item)
                                    final_dest = item_dest / rel
                                    if not final_dest.exists():
                                        final_dest.parent.mkdir(parents=True, exist_ok=True)
                                        shutil.move(str(subitem), str(final_dest))
                        else:
                            print(f"  SKIP: {item_dest} already exists")
                    else:
                        shutil.move(str(item), str(item_dest))
                # Remove empty source directory
                try:
                    source.rmdir()
                except OSError:
                    pass  # Not empty, that's fine
            else:
                shutil.move(str(source), str(dest))
            print(f"  MOVED: {source} -> {dest} ({files} files)")

    return files, size


def run_migration(dry_run: bool = True) -> None:
    """Run the full migration."""
    print("=" * 60)
    print("Data Directory Migration")
    print("=" * 60)
    print(f"Target: {AURAL_DATA_DIR}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will move files)'}")
    print()

    if not dry_run:
        print("Creating directory structure...")
        ensure_directories()
        print()

    total_files = 0
    total_bytes = 0

    print("Migrations:")
    print("-" * 60)
    for source, dest, description in MIGRATIONS:
        print(f"\n{description}:")
        files, size = migrate_path(source, dest, description, dry_run)
        total_files += files
        total_bytes += size

    print()
    print("-" * 60)
    print(f"Total: {total_files} files, {format_size(total_bytes)}")
    print()

    # Show cleanup candidates
    print("Cleanup candidates (test/temp directories):")
    print("-" * 60)
    for path in CLEANUP_DIRS:
        if path.exists():
            files = count_files(path)
            size = get_size(path)
            if dry_run:
                print(f"  WOULD DELETE: {path} ({files} files, {format_size(size)})")
            else:
                print(f"  Skipping cleanup of {path} - manual review recommended")

    if dry_run:
        print()
        print("=" * 60)
        print("This was a DRY RUN. No files were moved.")
        print("Run without --dry-run to execute the migration.")
        print("=" * 60)


def verify_migration() -> None:
    """Verify the migration was successful."""
    print("=" * 60)
    print("Migration Verification")
    print("=" * 60)
    print()

    # Check new structure exists
    print("Checking new directory structure:")
    print("-" * 60)

    checks = [
        (AURAL_DATA_DIR, "Base data directory"),
        (GWASI_INDEX_DIR, "GWASI index"),
        (REDDIT_INDEX_DIR, "Reddit index"),
        (RELEASES_DIR, "Releases"),
        (ANALYSIS_DIR, "Analysis results"),
        (REDDIT_SAVED_PENDING_DIR, "Reddit saved (pending)"),
        (REDDIT_SAVED_ARCHIVED_DIR, "Reddit saved (archived)"),
        (PROCESSED_POSTS_FILE.parent, "Tracking directory"),
    ]

    all_ok = True
    for path, description in checks:
        exists = path.exists()
        files = count_files(path) if exists else 0
        size = format_size(get_size(path)) if exists else "0 B"
        status = "OK" if exists else "MISSING"
        if not exists:
            all_ok = False
        print(f"  [{status}] {description}: {path}")
        if exists:
            print(f"         ({files} files, {size})")

    print()

    # Check old directories are empty/gone
    print("Checking old directories removed:")
    print("-" * 60)

    old_dirs = [
        PROJECT_ROOT / "extracted_data",
        PROJECT_ROOT / "data" / "releases",
        PROJECT_ROOT / "analysis_results",
        PROJECT_ROOT / "saved_posts",
        PROJECT_ROOT / "saved_posts_archived",
        PROJECT_ROOT / "ao3_data",
        PROJECT_ROOT / "scriptbin_data",
        PROJECT_ROOT / "hotaudio_data",
        PROJECT_ROOT / "ytdlp_data",
        PROJECT_ROOT / "pornhub_data",
    ]

    for path in old_dirs:
        if path.exists():
            files = count_files(path)
            if files > 0:
                print(f"  [WARN] {path} still has {files} files")
                all_ok = False
            else:
                print(f"  [OK] {path} is empty")
        else:
            print(f"  [OK] {path} removed")

    print()
    if all_ok:
        print("Migration verification: PASSED")
    else:
        print("Migration verification: ISSUES FOUND")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate data directories to new unified structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without moving files (default behavior)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the migration (moves files)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration was successful",
    )
    args = parser.parse_args()

    if args.verify:
        verify_migration()
    else:
        # Default to dry-run for safety - must explicitly use --execute to migrate
        dry_run = not args.execute
        if dry_run and not args.dry_run:
            print("Note: Running in dry-run mode by default. Use --execute to migrate.")
            print()
        run_migration(dry_run=dry_run)


if __name__ == "__main__":
    main()
