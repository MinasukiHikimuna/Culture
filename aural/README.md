# GWASI Reddit Audio Data Extractor

This tool extracts comprehensive data from [gwasi.com](https://gwasi.com/), which maintains an index of Reddit audio content from various adult audio subreddits.

## Features

- ✅ Extracts data from GWASI's JSON API endpoints
- ✅ Processes both incremental (delta.json) and multiple base files (1.json, 2.json, etc.)
- ✅ **Intelligent caching system** - saves intermediate JSON files locally
- ✅ **Resume capability** - can continue interrupted downloads
- ✅ **Cache-only mode** - process previously downloaded data without network access
- ✅ Parses metadata including titles, tags, usernames, subreddits, scores
- ✅ Generates Reddit URLs for further processing with PRAW
- ✅ Outputs data in CSV and JSON formats
- ✅ Removes duplicates and generates summary statistics
- ✅ Handles large datasets efficiently with rate limiting

## Data Sources

GWASI maintains multiple data sources:
- `delta.json` - Recent updates and new posts
- `base_<hash>/1.json`, `base_<hash>/2.json`, etc. - Complete historical dataset split into numbered files

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage
```bash
python gwasi_extractor.py
```

### Advanced Options
```bash
# Specify output directory
python gwasi_extractor.py --output my_data

# Choose output format
python gwasi_extractor.py --format csv      # CSV only
python gwasi_extractor.py --format json    # JSON only  
python gwasi_extractor.py --format both    # Both formats (default)

# Test with limited files (useful for testing)
python gwasi_extractor.py --max-files 10   # Download only first 10 base files

# Caching options
python gwasi_extractor.py --no-cache       # Always fetch fresh data, don't use cache
python gwasi_extractor.py --cache-only     # Only process cached files, no network requests

# Resume interrupted download
python gwasi_extractor.py                  # Will automatically use cached files
```

### Example Output
```bash
🚀 Starting GWASI data extraction...
🔍 Discovering JSON endpoints...
📄 Found base file: base_37997ef38e.json
📥 Fetching: https://gwasi.com/delta.json
✅ Successfully fetched data
📊 Fetching delta data...
✅ Processed 1,375 delta entries
📥 Fetching: https://gwasi.com/base_37997ef38e.json
✅ Successfully fetched data  
📊 Fetching base data...
✅ Processed 226,246 base entries
🔄 Removing duplicates...
✅ Final dataset: 226,246 unique entries
💾 Saved 226,246 entries to extracted_data/gwasi_data_20250801_143022.csv
💾 Saved 226,246 entries to extracted_data/gwasi_data_20250801_143022.json
📈 Summary saved to extracted_data/summary_20250801_143022.json

📈 EXTRACTION SUMMARY
==================================================
Total entries: 226,246
Date range: 2020-01-15T10:30:45 to 2025-08-01T14:30:22

Top subreddits:
  gonewildaudio: 84,544
  pillowtalkaudio: 58,763  
  GWASapphic: 33,995
  ...

Content types:
  audio: 180,234
  script: 35,678
  verification: 8,456
  other: 1,878
```

## Output Format

### CSV Columns
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
import pandas as pd

# Load extracted data
df = pd.read_csv('extracted_data/gwasi_data_20250801_143022.csv')

# Initialize PRAW
reddit = praw.Reddit(
    client_id='your_client_id',
    client_secret='your_client_secret', 
    user_agent='your_user_agent'
)

# Process posts
for _, row in df.head(10).iterrows():
    try:
        submission = reddit.submission(id=row['post_id'])
        print(f"Title: {submission.title}")
        print(f"Author: {submission.author}")
        print(f"Score: {submission.score}")
        print("---")
    except Exception as e:
        print(f"Error processing {row['post_id']}: {e}")
```

## File Structure

```
gwasi-extractor/
├── gwasi_extractor.py        # Main extraction script
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment configuration
├── README.md                # This file
└── extracted_data/          # Output directory (created automatically)
    ├── gwasi_data_*.csv         # Extracted data in CSV format
    ├── gwasi_data_*.json        # Extracted data in JSON format
    ├── summary_*.json           # Summary statistics
    ├── current_base_version.txt # Tracks current base version
    └── raw_json/                # Cached intermediate JSON files
        ├── delta.json               # Cached delta data
        ├── base_37997ef38e/         # Base version directory
        │   ├── 1.json                   # Base file 1
        │   ├── 2.json                   # Base file 2
        │   └── ...                      # Additional base files
        ├── base_12345678ab/         # Different base version (kept for comparison)
        │   ├── 1.json
        │   └── ...
        └── ...                      # Additional base versions
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

## License

This tool is for educational and research purposes. Please respect Reddit's terms of service and the content creators' rights when using this data.