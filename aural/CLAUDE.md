# GWASI Extractor

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
| `script_url_extractor.py` | Extract script URLs from posts |
| `reddit-flair-fetcher.py` | Fetch Reddit flair data |
| `reset_post.py` | Reset post data for reprocessing |

### JavaScript Scripts (run with `node`)

| Script | Purpose |
|--------|---------|
| `analyze-download-import.js` | Main workflow: analyze Reddit post → download → import to Stashapp |
| `analyze-reddit-post.js` | LLM-powered Reddit post analysis |
| `release-orchestrator.js` | Orchestrate full release processing |
| `stashapp-importer.js` | Import releases to Stashapp (FFmpeg conversion + GraphQL) |
| `soundgasm-extractor.js` | Download from Soundgasm |
| `whypit-extractor.js` | Download from Whyp.it |
| `hotaudio-extractor.js` | Download from HotAudio |
| `scriptbin-extractor.js` | Extract scripts from scriptbin.works |
| `cyoa-import.js` | Import CYOA (Choose Your Own Adventure) content |
| `reset-post.js` | Reset post data for reprocessing (JS version) |

## Directory Structure

```
project_root/
├── data/
│   ├── releases/                   # Releases organized by performer
│   │   └── {performer}/
│   │       └── {post_id}_{slug}/
│   │           ├── release.json           # Full release metadata (LLM analysis, sources)
│   │           ├── {audio_name}.m4a       # Downloaded audio file
│   │           ├── {audio_name}.json      # Audio-specific metadata
│   │           ├── script.txt             # Extracted script (if available)
│   │           ├── script.html            # Script HTML source
│   │           └── script_metadata.json   # Script source metadata
│   ├── cyoa/                       # CYOA (Choose Your Own Adventure) imports
│   ├── hotaudio/                   # HotAudio-specific data
│   └── processed_posts.json        # Tracking of processed Reddit posts
├── extracted_data/                 # GWASI index cache
│   ├── raw_json/                   # Raw GWASI JSON files
│   ├── reddit/                     # Reddit post data from PRAW
│   └── base_entries_cache.json     # Consolidated GWASI entries (~5.6GB)
└── analysis_results/               # LLM analysis results for Reddit posts
    └── {post_id}_{slug}_analysis.json
```

## Environment Configuration

Copy `.env.example` to `.env` and fill in the required values.

## Typical Workflow

1. **Discover content** via GWASI or direct Reddit URL
2. **Analyze post** with `analyze-reddit-post.js` (LLM extracts metadata)
3. **Download audio** from Soundgasm/Whyp.it/HotAudio
4. **Import to Stashapp** with `stashapp-importer.js` (converts audio→video, uploads metadata)

Or use `analyze-download-import.js` for the complete workflow:
```bash
node analyze-download-import.js <reddit_url>
```

## Metadata Collection

All extractors preserve and enrich metadata along the pipeline:
- Original platform metadata (Soundgasm, Reddit, etc.)
- LLM analysis results in `content.json`
- Complete audit trail of processing steps
