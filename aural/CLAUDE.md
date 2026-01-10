# Aural

Audio content extraction and Stashapp import system for GoneWildAudio content.

## Running Python Scripts

All Python scripts must be run with `uv`:

```bash
uv run python script_name.py [args]
```

Examples:
```bash
uv run python gwasi_extractor.py --help
uv run python reddit_extractor.py <reddit_url>
uv run python script_url_extractor.py <url>
```

## Architecture Overview

### Core Principle: Audio-Centric Architecture

**Audio files are the foundation** - without audio, there is no release. Everything else enriches the audio with metadata.

### Data Hierarchy

```
Audio File (required - from Soundgasm, Whyp.it, HotAudio)
├── Enrichment Data (from Reddit/Patreon posts)
│   ├── Title, Date, Primary Performer
│   └── Additional metadata (tags, description)
├── Script (optional - from scriptbin.works, etc.)
└── Artwork (optional)

Release (collection of related audio variants)
├── Audio Variant 1 (e.g., M4F version)
├── Audio Variant 2 (e.g., F4M version)
└── Audio Variant 3 (e.g., with/without SFX)
```

### Platform Roles

- **Audio Platforms**: Soundgasm, Whyp.it, HotAudio (source of audio files)
- **Post Platforms**: Reddit, Patreon (source of enrichment metadata)
- **GWASI**: Index into Reddit posts (discovery, not primary source)
- **Script Platforms**: scriptbin.works (optional script content)
- **Stashapp**: Final destination for organized releases

## Implemented Scripts

### Python Scripts (run with `uv run python`)

| Script | Purpose |
|--------|---------|
| `gwasi_extractor.py` | Extract data from gwasi.com (Reddit audio index) |
| `reddit_extractor.py` | Extract Reddit post metadata via PRAW |
| `soundgasm_extractor.py` | Download from Soundgasm |
| `whypit_extractor.py` | Download from Whyp.it |
| `hotaudio_extractor.py` | Download from HotAudio (encrypted) |
| `script_url_extractor.py` | Extract script URLs from posts |
| `reddit-flair-fetcher.py` | Fetch Reddit flair data |
| `reset_post.py` | Reset post data for reprocessing |

| `analyze_download_import.py` | Main workflow: analyze Reddit post → download → import to Stashapp |
| `analyze_reddit_post.py` | LLM-powered Reddit post analysis |
| `release_orchestrator.py` | Orchestrate full release processing |
| `stashapp_importer.py` | Import releases to Stashapp (FFmpeg conversion + GraphQL) |
| `scriptbin_extractor.py` | Extract scripts from scriptbin.works |
| `cyoa_import.py` | Import CYOA (Choose Your Own Adventure) content |

## Directory Structure

All data is consolidated under `aural_data/` for easy backup with restic:

```
aural_data/                              # Single backup root
├── index/                               # Discovery and indexing data
│   ├── gwasi/                           # GWASI index cache
│   │   ├── raw_json/                    # Raw GWASI JSON partitions
│   │   ├── base_entries_cache.json      # Consolidated entries (~5.6GB)
│   │   └── current_base_version.txt     # Version tracker
│   └── reddit/                          # Reddit post metadata from PRAW
│       └── {author}/{post_id}_*.json
│
├── sources/                             # Platform-specific downloads
│   ├── reddit_saved/                    # Reddit saved posts
│   │   ├── pending/                     # Posts awaiting processing
│   │   └── archived/                    # Successfully imported posts
│   ├── ao3/                             # AO3 content
│   ├── scriptbin/                       # Scripts from scriptbin.works
│   ├── hotaudio/                        # HotAudio downloads
│   └── ytdlp/                           # yt-dlp downloads (YouTube, PornHub, etc.)
│
├── releases/                            # Processed releases by performer
│   └── {performer}/
│       └── {post_id}_{slug}/
│           ├── release.json             # Full release metadata
│           ├── {audio_name}.m4a         # Downloaded audio file
│           ├── {audio_name}.json        # Audio-specific metadata
│           ├── script.txt               # Extracted script (if available)
│           └── script_metadata.json     # Script source metadata
│
├── analysis/                            # LLM analysis results
│   └── {post_id}_{slug}_analysis.json
│
└── tracking/
    └── processed_posts.json             # Processing state tracker
```

Configuration is centralized in `config.py` with paths configurable via `.env`.

## Environment Configuration

Copy `.env.example` to `.env` and fill in the required values.

## Typical Workflow

1. **Discover content** via GWASI or direct Reddit URL
2. **Analyze post** with `analyze_reddit_post.py` (LLM extracts metadata)
3. **Download audio** from Soundgasm/Whyp.it/HotAudio
4. **Import to Stashapp** with `stashapp_importer.py` (converts audio→video, uploads metadata)

Or use `analyze_download_import.py` for the complete workflow:
```bash
uv run python analyze_download_import.py <reddit_post_file>
```

## Metadata Collection

All extractors preserve and enrich metadata along the pipeline:
- Original platform metadata (Soundgasm, Reddit, etc.)
- LLM analysis results in `content.json`
- Complete audit trail of processing steps

## Command Line Tools

Use modern alternatives instead of legacy tools:
- Use `fd` instead of `find`
- Use `rg` (ripgrep) instead of `grep`
