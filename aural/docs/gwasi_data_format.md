# GWASI Data Format

## Overview

GWASI (GoneWildAudio Search Index) provides a searchable index of Reddit posts from audio-related subreddits. Data is distributed as versioned JSON snapshots.

## Data Structure

### Base Files

Base data is split across ~700 numbered JSON files at `https://gwasi.com/base_{VERSION}/{N}.json`.

Each file contains:

```json
{
  "entries": [
    ["post_id", "subreddit", "author", "flair", "title", "timestamp", "upvotes", "comments", "script_author"],
    ...
  ],
  "off": [...]  // Internal pagination/offset data
}
```

**Entry format** (array, not object):
| Index | Field | Example |
|-------|-------|---------|
| 0 | post_id | `"1kus6af"` |
| 1 | subreddit | `"pillowtalkaudio"` |
| 2 | author | `"--Lev"` |
| 3 | flair | `"Script Fill"` |
| 4 | title | `"[M4A] [Script Fill] Say You..."` |
| 5 | timestamp | `1748140513` (Unix epoch) |
| 6 | upvotes | `14` |
| 7 | comments | `96` |
| 8 | script_author | `"u/livejoker"` (optional) |

### Delta File

`https://gwasi.com/delta.json` contains:
- `base`: Current base version hash (e.g., `"46996abd35"`)
- `entries`: Recent updates since last base snapshot

## Version Updates

When GWASI publishes a new base version:

1. **All files are regenerated** - not just appending new entries
2. **Entries may be shuffled** between files
3. **Entry counts per file change** - some increase, some decrease
4. **Files may be added/removed** - count can vary between versions
5. **Total entries may decrease** - entries can be removed (deleted posts, etc.)

### Example: base_22a412729b → base_46996abd35

| Metric | Old | New |
|--------|-----|-----|
| Total entries | 5,441,923 | 5,425,071 |
| File count | 689 | 688 |
| Size | ~2.4GB | ~2.4GB |

File-level changes (sample):
- `1.json`: 14,853 → 14,900 entries (+47)
- `4.json`: 5,109 → 5,103 entries (-6)
- `115.json`: exists → removed

Post IDs overlap significantly but not completely between versions (~99% overlap in sampled files).

## Local Caching

The extractor maintains:
- `current_base_version.txt`: Tracks cached version
- `base_entries_cache.json`: Consolidated cache (~5.7GB) to avoid parsing 700 files
- `raw_json/base_{VERSION}/`: Individual JSON files
