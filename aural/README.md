# GWASI Reddit Audio Data Extractor

This tool extracts comprehensive data from [gwasi.com](https://gwasi.com/), which maintains an index of Reddit audio content from various adult audio subreddits.

## Quickstart

```bash
# Step 1: Set up Reddit API credentials (one-time setup)
#   - Create app at https://www.reddit.com/prefs/apps (choose "script" type)
#   - Copy .env.example to .env and fill in your credentials:
cp .env.example .env
# Edit .env with your REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET

# Step 2: Extract post index from GWASI (~2.7GB of post metadata)
uv run python gwasi_extractor.py --output extracted_data

# Step 3: Fetch full Reddit post content for a specific user
uv run python reddit_extractor.py extracted_data/gwasi_data_*.json --output extracted_data/reddit --filter-users username

# Step 4: Analyze, download audio, and import to Stashapp
# Single post:
node analyze-download-import.js extracted_data/reddit/username/postid_title.json

# All posts from a user:
node analyze-download-import.js extracted_data/reddit/username/

# Dry run first (see what would be downloaded without downloading):
node analyze-download-import.js extracted_data/reddit/username/ --dry-run
```

**What you get:**
- Step 2: Post IDs, titles, tags, dates, scores (from GWASI index)
- Step 3: Full post content with audio links, performer info, scripts (from Reddit API)
- Step 4: Downloaded audio files organized by release, imported to Stashapp

## Entry Points

There are several scripts for different use cases:

| Script | Use Case | Input | Description |
|--------|----------|-------|-------------|
| `gwasi_extractor.py` | Initial discovery | GWASI delta/base files | Extracts post index from GWASI (~227k posts) |
| `reddit_extractor.py` | Post enrichment | GWASI JSON + username filter | Fetches full Reddit post content via PRAW |
| `analyze-download-import.js` | **Full pipeline** | Directory or JSON file | Analyzes posts, downloads audio, imports to Stashapp |
| `process-reddit-url.js` | Ad-hoc URL processing | Reddit URL | Processes a single Reddit URL directly |

### When to use each:

**`analyze-download-import.js`** - Main batch processing script
```bash
# Process all posts from a user (tracks progress, skips already processed)
node analyze-download-import.js extracted_data/reddit/SweetnEvil86/

# Process single post
node analyze-download-import.js extracted_data/reddit/SweetnEvil86/1bdg16n_post.json

# Skip Stashapp import (just download audio)
node analyze-download-import.js extracted_data/reddit/SweetnEvil86/ --skip-import

# Force re-process already processed posts
node analyze-download-import.js extracted_data/reddit/SweetnEvil86/ --force

# Check processing status
node analyze-download-import.js --status
```

**`process-reddit-url.js`** - For ad-hoc Reddit URLs (not from GWASI)
```bash
# Process a single Reddit URL directly
node process-reddit-url.js "https://www.reddit.com/r/gonewildaudio/comments/xyz123/..."
```

### Special Features

- **Crosspost resolution**: Automatically fetches content from original posts when encountering crossposts
- **Duplicate tracking**: Maintains `data/processed_posts.json` to avoid re-processing
- **Resume support**: Can stop and restart batch processing anytime

## Features

- ✅ Extracts data from GWASI's JSON API endpoints
- ✅ Processes both incremental (delta.json) and multiple base files (1.json, 2.json, etc.)
- ✅ **Intelligent caching system** - saves intermediate JSON files locally
- ✅ **Resume capability** - can continue interrupted downloads
- ✅ **Cache-only mode** - process previously downloaded data without network access
- ✅ Parses metadata including titles, tags, usernames, subreddits, scores
- ✅ Generates Reddit URLs for further processing with PRAW
- ✅ Outputs data in JSON format
- ✅ Removes duplicates and generates summary statistics
- ✅ Handles large datasets efficiently with rate limiting

## Data Sources

GWASI provides data via:
- `delta.json` - Recent updates and new posts
- `base_<hash>/` directory containing `1.json`, `2.json`, ... `1000+.json` - Complete historical dataset split into numbered files

## Installation

1. Clone or download this repository
2. Install [uv](https://docs.astral.sh/uv/) if not already installed
3. Dependencies will be automatically installed when running with `uv run`

## Usage

### Basic Usage
```bash
uv run python gwasi_extractor.py
```

### Advanced Options
```bash
# Specify output directory
uv run python gwasi_extractor.py --output extracted_data

# Test with limited files (useful for testing)
uv run python gwasi_extractor.py --max-files 10   # Download only first 10 base files

# Caching options
uv run python gwasi_extractor.py --no-cache       # Always fetch fresh data, don't use cache
uv run python gwasi_extractor.py --cache-only     # Only process cached files, no network requests

# Only fetch delta updates (skip base files)
uv run python gwasi_extractor.py --delta-only

# Non-interactive mode (auto-download new base when version changes)
uv run python gwasi_extractor.py --non-interactive

# Adjust consecutive 404 threshold for file discovery
uv run python gwasi_extractor.py --consecutive-404s 20

# Resume interrupted download
uv run python gwasi_extractor.py                  # Will automatically use cached files
```

### Example Output
```bash
🚀 Starting GWASI data extraction...
📥 Fetching delta.json...
✅ Fetched delta with 1,375 entries
📊 Fetching base data from base_22a412729b/...
📥 Downloading 1022 base files...
✅ Added 227,602 base entries to dataset
📝 Saved base version: base_22a412729b

🔄 Removing duplicates...
✅ Final dataset: 227,602 unique entries
💾 Saved 227,602 entries to extracted_data/gwasi_data_20251223_134855.json
📈 Summary saved to extracted_data/summary_20251223_134855.json

📈 EXTRACTION SUMMARY
==================================================
Total entries: 227,602
Date range: 2012-05-18 to 2025-12-23

Top subreddits:
  gonewildaudio: 172,906
  pillowtalkaudio: 19,690
  GWASapphic: 8,140
  ...

Content types:
  script: 91,143
  unknown: 68,499
  other: 43,070
  audio: 17,598
  verification: 7,292
```

## Output Format

### JSON Fields
- `post_id` - Reddit post ID
- `subreddit` - Subreddit name
- `username` - Reddit username
- `post_type` - Type indicator (Script Fill, Audio, etc.)
- `full_title` - Complete title with tags
- `date` - Post date (ISO format)
- `timestamp` - Unix timestamp
- `comments` - Number of comments
- `score` - Reddit score (upvotes - downvotes)
- `content_type` - Classified type (audio/script/verification/other)
- `duration` - Extracted duration if available
- `reddit_url` - Direct Reddit URL
- `tag_string` - Comma-separated list of tags
- `additional_info` - Extra metadata

### Using with PRAW

The extracted data includes Reddit URLs and post IDs that can be used with PRAW:

```python
import praw
import json

# Load extracted data
with open('extracted_data/gwasi_data_20250801_143022.json') as f:
    data = json.load(f)

# Initialize PRAW
reddit = praw.Reddit(
    client_id='your_client_id',
    client_secret='your_client_secret',
    user_agent='your_user_agent'
)

# Process posts
for entry in data[:10]:
    try:
        submission = reddit.submission(id=entry['post_id'])
        print(f"Title: {submission.title}")
        print(f"Author: {submission.author}")
        print(f"Score: {submission.score}")
        print("---")
    except Exception as e:
        print(f"Error processing {entry['post_id']}: {e}")
```

## File Structure

```
gwasi-extractor/
├── gwasi_extractor.py        # Main extraction script
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment configuration
├── README.md                # This file
└── extracted_data/                 # Output directory (or extracted_data/ by default)
    ├── gwasi_data_*.json        # Extracted data in JSON format
    ├── summary_*.json           # Summary statistics
    ├── current_base_version.txt # Tracks current base version
    └── raw_json/                # Cached intermediate JSON files
        ├── delta.json               # Cached delta data
        └── base_22a412729b/         # Base version directory (~1000+ files)
            ├── 1.json
            ├── 2.json
            ├── ...
            └── 1022.json
```

## Notes

- The complete dataset can be quite large (hundreds of files, gigabytes total)
- **Caching system**: Files are cached locally, so interrupted downloads can be resumed
- **First run**: Will discover and download all available base files automatically  
- **Subsequent runs**: Will use cached files and only download new/missing data
- GWASI data is updated regularly, so run the extractor periodically for fresh data
- All searches and data processing are performed locally for privacy
- The tool respects rate limits with delays between requests

## Caching Behavior

- **Default**: Uses cached files if available, downloads missing files
- **`--no-cache`**: Always downloads fresh data, overwrites cache
- **`--cache-only`**: Only processes existing cached files, no network requests
- **`--force-full`**: Force download of all base files even if version unchanged
- **Resume**: If download is interrupted, restart with same command to continue

## Version Management

- **Base version tracking**: Each base version (e.g., `base_37997ef38e`) gets its own directory
- **Automatic detection**: Script detects when GWASI updates their base data
- **Version preservation**: Old base versions are kept for comparison/rollback
- **Smart updates**: Only downloads delta.json if base version unchanged
- **Storage efficient**: Multiple versions coexist without conflicts

## Subreddits Covered

GWASI indexes content from multiple Reddit audio communities:
- r/gonewildaudio (GWA)
- r/pillowtalkaudio (PTA) 
- r/GWASapphic
- r/GoneWildAudioGay (GWAGay)
- r/TheRealmOfEroticAudio
- And many others

## Complete Audio Processing Workflow

This tool is part of a larger audio content processing pipeline. The complete workflow consists of:

### 1. Discovery Phase
- **GWASI Index**: Use this tool to discover posts from Reddit audio communities
- **Direct Sources**: Monitor Reddit/Patreon directly for new releases
- **Output**: List of posts with metadata (titles, performers, dates, tags)

### 2. Post Analysis Phase
- **Content Analysis**: Parse post content to extract:
  - Voice actor information
  - Script details and sources
  - Audio platform links (Soundgasm, Whyp.it, HotAudio)
  - Release variants (M4F/F4M, SFX versions, etc.)
- **Link Extraction**: Identify all audio file URLs and associated metadata

### 3. Download Planning Phase
- **Audio Inventory**: Catalog all available audio variants
- **Priority Assessment**: Determine which files to download based on:
  - Quality preferences
  - Storage constraints
  - Content type priorities
- **Deduplication**: Avoid downloading identical content from multiple sources

### 4. File Download & Processing Phase
- **Audio Download**: Retrieve audio files from platforms:
  - Soundgasm.net
  - Whyp.it
  - HotAudio.net
  - Patreon (premium content)
- **Script Download**: Fetch associated scripts from scriptbin.works
- **Artwork Collection**: Download cover art and promotional images
- **Format Standardization**: Convert audio to consistent formats if needed

### 5. Metadata Enrichment Phase
- **Tag Normalization**: Standardize content tags across sources
- **Performer Database**: Build comprehensive performer profiles
- **Release Grouping**: Link related audio variants into unified releases
- **Quality Metadata**: Add technical audio information (bitrate, duration, etc.)

### 6. Stashapp Integration Phase
- **Media Preparation**: Convert audio files to video format with static images
- **Metadata Mapping**: Transform audio metadata to Stashapp's video schema
- **Performer Management**: Create/update performer entries in Stashapp
- **Content Organization**: Organize releases by performers, tags, and series
- **Database Import**: Add processed content to Stashapp for browsing/management

### Data Flow Architecture

```
GWASI Index ─┐
Reddit Posts ├─→ Post Analysis ─→ Download Planning ─→ File Processing
Patreon      ├─→                                    ─→
Direct URLs  ─┘                                     ─→ Stashapp Integration
```

### Output Structure
```
processed_releases/
├── performers/           # Organized by voice actor
│   ├── performer_name/
│   │   ├── audio/       # Processed audio files
│   │   ├── scripts/     # Associated scripts
│   │   ├── artwork/     # Cover art and images
│   │   └── metadata.json
├── releases/            # Organized by release
│   ├── release_id/
│   │   ├── variants/    # Different versions (M4F, F4M, etc.)
│   │   ├── extras/      # Scripts, artwork, etc.
│   │   └── release.json
└── stashapp_import/     # Ready for Stashapp import
    ├── videos/          # Audio wrapped as video files
    ├── performers.json  # Performer database
    └── scenes.json      # Scene metadata
```

## License

This tool is for educational and research purposes. Please respect Reddit's terms of service and the content creators' rights when using this data.