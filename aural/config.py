#!/usr/bin/env python3
"""
Centralized configuration for Aural data paths.

All scripts should import paths from this module rather than
defining their own hardcoded paths. This enables:
1. Single backup root (aural_data/) for restic
2. Environment-based configuration
3. Consistent paths across all scripts
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")

# Base data directory - all data lives under this root
AURAL_DATA_DIR = Path(os.getenv("AURAL_DATA_DIR", "./aural_data")).resolve()

# Index directory - discovery and indexing data
INDEX_DIR = AURAL_DATA_DIR / "index"
GWASI_INDEX_DIR = INDEX_DIR / "gwasi"
REDDIT_INDEX_DIR = INDEX_DIR / "reddit"

# Sources directory - platform-specific downloads
SOURCES_DIR = AURAL_DATA_DIR / "sources"
REDDIT_SAVED_DIR = SOURCES_DIR / "reddit_saved"
REDDIT_SAVED_PENDING_DIR = REDDIT_SAVED_DIR / "pending"
REDDIT_SAVED_ARCHIVED_DIR = REDDIT_SAVED_DIR / "archived"
AO3_DIR = SOURCES_DIR / "ao3"
SCRIPTBIN_DIR = SOURCES_DIR / "scriptbin"
HOTAUDIO_DIR = SOURCES_DIR / "hotaudio"
YTDLP_DIR = SOURCES_DIR / "ytdlp"  # Also includes pornhub (via yt-dlp)

# Releases directory - processed releases organized by performer
RELEASES_DIR = AURAL_DATA_DIR / "releases"
CYOA_DIR = AURAL_DATA_DIR / "cyoa"  # Choose Your Own Adventure content

# Analysis directory - LLM analysis results
ANALYSIS_DIR = AURAL_DATA_DIR / "analysis"

# Tracking directory - processing state
TRACKING_DIR = AURAL_DATA_DIR / "tracking"
PROCESSED_POSTS_FILE = TRACKING_DIR / "processed_posts.json"

# External paths (from .env) - Stashapp library on external volume
STASH_OUTPUT_DIR = (
    Path(os.getenv("STASH_OUTPUT_DIR")) if os.getenv("STASH_OUTPUT_DIR") else None
)
STASH_BASE_URL = os.getenv("STASH_BASE_URL", "")


def ensure_directories() -> None:
    """Create all required directories if they don't exist."""
    dirs = [
        AURAL_DATA_DIR,
        INDEX_DIR,
        GWASI_INDEX_DIR,
        REDDIT_INDEX_DIR,
        SOURCES_DIR,
        REDDIT_SAVED_DIR,
        REDDIT_SAVED_PENDING_DIR,
        REDDIT_SAVED_ARCHIVED_DIR,
        AO3_DIR,
        SCRIPTBIN_DIR,
        HOTAUDIO_DIR,
        YTDLP_DIR,
        RELEASES_DIR,
        CYOA_DIR,
        ANALYSIS_DIR,
        TRACKING_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def validate_stash_config() -> bool:
    """Validate Stashapp configuration is complete."""
    if not STASH_OUTPUT_DIR:
        raise ValueError(
            "STASH_OUTPUT_DIR not configured in .env. "
            "Set it to your Stashapp library path."
        )
    if not STASH_OUTPUT_DIR.exists():
        raise ValueError(f"STASH_OUTPUT_DIR does not exist: {STASH_OUTPUT_DIR}")
    return True
