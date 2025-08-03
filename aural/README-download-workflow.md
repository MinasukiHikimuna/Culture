# Download Workflow - From Reddit Analysis to Audio Files

This guide explains how to use the analyze-reddit-post results to download audio files using the integrated workflow.

## Overview

The complete workflow consists of:
1. **analyze-reddit-post.js** - Analyzes Reddit posts and extracts audio URLs, metadata
2. **download-orchestrator.js** - Coordinates downloads using platform-specific extractors  
3. **analyze-and-download.js** - Integrated pipeline that runs both steps

## Quick Start

### Single Reddit Post

```bash
# Complete workflow - analyze and download in one command
npm run analyze-and-download reddit_data/alekirser/1lxhwbd_post.json

# Or step by step:
npm run analyze-reddit reddit_data/alekirser/1lxhwbd_post.json --output analysis.json
npm run download-orchestrator analysis.json
```

### Batch Processing

```bash
# Process all posts in a directory
npm run analyze-and-download reddit_data/alekirser/

# Dry run to see what would be processed
npm run analyze-and-download reddit_data/alekirser/ --dry-run --verbose
```

## Workflow Details

### Step 1: Analysis (analyze-reddit-post.js)

Extracts structured data from Reddit posts:

```json
{
  "performers": {
    "count": 1,
    "primary": "alekirser", 
    "additional": []
  },
  "audio_versions": [
    {
      "version_name": "Main Audio",
      "urls": [
        {
          "platform": "Soundgasm",
          "url": "https://soundgasm.net/u/alekirser/audio-title"
        }
      ]
    }
  ],
  "script": {
    "url": "https://reddit.com/r/gonewildaudio/comments/...",
    "author": "ScriptAuthor",
    "fillType": "public"
  }
}
```

### Step 2: Download Orchestration (download-orchestrator.js)

Routes URLs to appropriate extractors:
- **Soundgasm** → `soundgasm-extractor.js`
- **Whyp.it** → `whypit-extractor.js` 
- **HotAudio** → `hotaudio-extractor.js`

Creates organized directory structure:
```
downloads/
├── username/
│   ├── postid_title/
│   │   ├── platform_files/          # Downloaded audio/video files
│   │   ├── metadata.json            # Download metadata
│   │   └── analysis.json            # Full analysis results
```

### Step 3: Audio Processing

Each extractor automatically:
1. Downloads original audio file (M4A/MP3)
2. Converts to video format (MKV) with static image
3. Saves comprehensive metadata including:
   - LLM analysis results (performers, script info, series data)
   - Platform-specific metadata (title, tags, description)
   - File checksums and transformation records
4. Validates file integrity and duration

### Final JSON Structure

The complete metadata saved in the final JSON includes:

```json
{
  "id": "unique_content_id",
  "title": "Audio title from platform",
  "author": "performer_username", 
  "originalMediaFile": {
    "checksum": { "sha256": "...", "md5": "..." },
    "filePath": "path/to/original.m4a"
  },
  "transformedMediaFiles": [{
    "checksum": { "sha256": "...", "md5": "..." },
    "filePath": "path/to/converted.mkv"
  }],
  "metadata": {
    "soundgasmMetadata": { /* Platform-specific data */ },
    "analysisMetadata": {
      "performers": { /* LLM-extracted performer info */ },
      "script": { /* Script attribution and type */ },
      "series": { /* Series information */ },
      "audio_versions": [ /* Audio URLs and variants */ ]
    }
  },
  "enrichmentData": {
    "llmAnalysis": { /* Complete LLM analysis results */ }
  }
}
```

## Command Reference

### analyze-and-download.js

**Complete integrated workflow**

```bash
node analyze-and-download.js <post_file_or_directory> [options]

Options:
  --analysis-dir <dir>     Directory for analysis results (default: analysis_results)
  --download-dir <dir>     Directory for downloads (default: downloads)
  --dry-run               Analyze posts but don't download files
  --verbose               Show detailed progress
  --save-approved         Save analysis as approved (for LLM training)
```

### download-orchestrator.js

**Download from existing analysis**

```bash
node download-orchestrator.js <analysis_file_or_directory> [options]

Options:
  --output <dir>          Output directory (default: downloads)
  --dry-run              Show what would be downloaded
  --verbose              Show detailed download progress
```

## Examples

### Example 1: Single Post with Custom Directories

```bash
npm run analyze-and-download reddit_data/performer/post.json \
  --analysis-dir my_analysis \
  --download-dir my_downloads \
  --verbose
```

### Example 2: Batch Processing with Dry Run

```bash
npm run analyze-and-download reddit_data/ \
  --dry-run \
  --verbose
```

### Example 3: Download from Existing Analysis

```bash
npm run download-orchestrator analysis_results/ --verbose
```

## Directory Structure

### Input Structure (Reddit Data)
```
reddit_data/
├── username1/
│   ├── postid1_title.json
│   ├── postid2_title.json
│   └── ...
├── username2/
│   └── ...
```

### Output Structure
```
analysis_results/              # Analysis outputs
├── postid1_title_analysis.json
├── postid2_title_analysis.json
└── ...

downloads/                     # Downloaded content
├── username1/
│   ├── postid1_title/
│   │   ├── soundgasm_files/
│   │   ├── metadata.json
│   │   └── analysis.json
│   └── postid2_title/
│       └── ...
└── username2/
    └── ...
```

## Supported Platforms

Currently supported audio platforms:
- **Soundgasm** - Full support with audio→video conversion
- **Whyp.it** - Full support with audio→video conversion  
- **HotAudio** - Full support with audio→video conversion

## Integration with CLAUDE.md Workflow

This workflow implements the **Technical Implementation Workflow** outlined in CLAUDE.md:

1. **Phase 2: Content Analysis Engine** ✅
   - Post parsing and metadata extraction
   - Audio URL detection and platform identification

2. **Phase 3: Download Management** ✅
   - Platform-specific download orchestration
   - Retry logic and error handling
   - Progress tracking and metadata storage

3. **Phase 4: Metadata Enrichment** ✅
   - Release aggregation and performer identification
   - Tag normalization and quality assessment

4. **Phase 5: Stashapp Integration** 🔄
   - Audio→video conversion with static images
   - Ready for Stashapp import (manual step currently)

## Troubleshooting

### Common Issues

1. **"No extractor found for platform"**
   - Check that the platform is supported
   - Verify URL format matches expected patterns

2. **"Command failed" errors**
   - Ensure all dependencies are installed: `npm install`
   - Install Playwright browsers: `npm run install-playwright`

3. **"Failed to create output directory"**
   - Check file path length (Windows limitation)
   - Verify write permissions

### Debug Mode

Use `--verbose` flag for detailed logging:
```bash
npm run analyze-and-download post.json --verbose
```

## Next Steps

- Add support for Patreon platform extraction
- Implement automated Stashapp integration
- Add quality assessment and deduplication
- Create web interface for batch management