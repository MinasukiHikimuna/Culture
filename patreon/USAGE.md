# Usage Guide

## Data Capture with HAR Format

### Why HAR Format?

HAR (HTTP Archive) captures everything in one file:

- ✅ Request headers (cookies, authorization, user-agent)
- ✅ Response content
- ✅ No manual header copying needed

### Capture Process (Microsoft Edge)

1. **Open Microsoft Edge** and navigate to Patreon
2. **Login** to your Patreon account if needed
3. **Open Developer Tools** (`F12`)
4. **Network tab** → Check "Preserve log" → Select "Fetch/XHR" filter
5. **Clear** existing requests
6. **Navigate** to creator's posts page (just load the first page)
7. **Right-click** in Network requests → **"Save all as HAR with content"**
8. **Save** as `captured/patreon_capture.har`

**Note**: You only need to capture one page - the scraper will automatically fetch all remaining pages using the API template and authentication from your HAR file. The scraper starts fresh from page 1 and continues until all posts are collected.

### Testing Captured Data

```bash
# Validate your HAR file
uv run python scripts/validate_capture.py captured/patreon_capture.har
```

Expected output:

```
✅ Successfully loaded: captured/patreon_capture.har
🔍 HAR file detected
📡 Found 55 Patreon API requests
✅ Using posts request: https://www.patreon.com/api/posts?include=...
🔑 Headers captured: 12 headers
   ✅ Authorization: Present
   ✅ Cookie: Present
📊 Found 20 data items
🖼️ Media URLs found: 8
✅ Valid Patreon API response detected
```

## Running the Scraper

### Basic Usage

```bash
# With specific HAR file
uv run python scripts/scraper.py captured/patreon_capture.har

# With default location (captured/patreon_capture.har)
uv run python scripts/scraper.py
```

### Advanced Options

```bash
# Skip media downloads (faster, data only)
uv run python scripts/scraper.py captured/patreon_capture.har --no-media

# Full re-scrape (disable incremental mode)
uv run python scripts/scraper.py captured/patreon_capture.har --full-rescrape

# Verbose logging
uv run python scripts/scraper.py captured/patreon_capture.har --verbose

# Combine options
uv run python scripts/scraper.py captured/patreon_capture.har --no-media --verbose
```

### Incremental Scraping

By default, the scraper runs in **incremental mode**:

- ✅ Automatically detects previously scraped posts
- ✅ Only downloads new content since last run
- ✅ Stops when reaching known posts (50%+ duplicates)
- ✅ Preserves existing files with cursor-based naming

**First run**: Downloads all available posts
**Subsequent runs**: Only downloads new posts since last scrape

To force a complete re-scrape, use `--full-rescrape`

## Multiple Creators

For multiple creators, capture and process separately:

```bash
# Capture data for each creator
# Save as: captured/creator1.har, captured/creator2.har, etc.

# Process each separately
uv run python scripts/scraper.py captured/creator1.har
uv run python scripts/scraper.py captured/creator2.har
```

## Output Structure

After running the scraper:

```
Patreon/
├── data/
│   ├── creator_name_complete.json           # All posts combined
│   ├── creator_name_cursor_abc123.json      # Latest posts (cursor: abc123)
│   ├── creator_name_cursor_def456.json      # Next batch (cursor: def456)
│   ├── creator_name_page_1234567890_001.json # Fallback naming
│   └── ...                                  # Additional cursor-based files
├── media/
│   └── creator_name/
│       ├── images/
│       └── videos/
└── captured/
    └── patreon_capture.har                  # Original capture
```

### File Naming Strategy

The scraper now uses **cursor-based naming** for better incremental scraping:

- `creator_cursor_abc123.json` - Contains posts from a specific pagination cursor
- `creator_page_timestamp_001.json` - Fallback for first page without cursor
- Each file includes metadata about the cursor, timestamp, and content

This approach ensures:

- ✅ New posts don't invalidate existing files
- ✅ Incremental scraping stops when reaching known content
- ✅ Each file represents a stable set of posts
- ✅ Easy to identify the latest scraped content

## Data Analysis

### Using JSON (Python)

```python
import json
from pathlib import Path

# Load complete dataset
with open("data/creator_name_complete.json", "r") as f:
    complete_data = json.load(f)

# Handle new format with metadata
if "data" in complete_data:
    all_posts = complete_data["data"]
    metadata = complete_data["metadata"]
    print(f"Scraped at: {metadata['scraped_at']}")
else:
    # Legacy format
    all_posts = complete_data

print(f"Total posts: {len(all_posts)}")

# Load individual cursor-based file
cursor_files = list(Path("data").glob("creator_name_cursor_*.json"))
if cursor_files:
    with open(cursor_files[0], "r") as f:
        cursor_data = json.load(f)

    posts = cursor_data["data"]
    cursor_info = cursor_data["metadata"]
    print(f"Cursor: {cursor_info['cursor']}")
    print(f"Posts in this batch: {len(posts)}")

# Analyze post types
post_types = {}
for post in all_posts:
    post_type = post.get("attributes", {}).get("post_type", "unknown")
    post_types[post_type] = post_types.get(post_type, 0) + 1

print("Post types:", post_types)
```

### Using External Tools

The JSON files can be imported into:

- **Excel/Google Sheets**: For basic analysis
- **Pandas/Polars**: For data science workflows
- **Databases**: For complex queries
- **Analytics tools**: For visualization

## Troubleshooting

### Common Issues

| Issue                       | Solution                                               |
| --------------------------- | ------------------------------------------------------ |
| "No HAR file found"         | Check file path and ensure `.har` extension            |
| "No Patreon requests found" | Recapture data, ensure you loaded creator's posts page |
| "Authentication failed"     | HAR file may be expired, recapture fresh data          |
| "Large file sizes"          | Use `--no-media` flag to skip media downloads          |
| "No new posts found"        | All posts already scraped - incremental mode working   |
| "Want to re-scrape all"     | Use `--full-rescrape` flag to disable incremental mode |

### Debug Mode

```bash
# Enable detailed logging
uv run python scripts/scraper.py captured/patreon_capture.har --debug
```

### Manual Header Override

If HAR capture fails, you can still use manual headers:

```python
# In scripts/scraper.py, modify:
custom_headers = {
    "Authorization": "Bearer your_token_here",
    "Cookie": "session_id=abc; patreon_device_id=def;",
    "User-Agent": "Mozilla/5.0..."
}

run_complete_scraping_workflow("capture.har", headers=custom_headers)
```

## Rate Limiting

The scraper includes built-in rate limiting:

- Default: 1 second between requests
- Configurable in script: `REQUEST_DELAY = 2.0` # 2 seconds
- Respects server resources automatically

## Security Notes

- HAR files contain session data - keep them secure
- Don't share HAR files (contain authentication tokens)
- Sessions expire - recapture if scraping fails
- Only capture your own content or public content

## Performance Tips

- Use `--no-media` for faster data-only scraping
- **Single HAR capture** gets all pages automatically
- Run during off-peak hours for better performance
- Monitor disk space for media downloads
- Each page saved individually for easy management
