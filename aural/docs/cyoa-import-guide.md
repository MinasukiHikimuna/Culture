# CYOA Import Guide

This guide documents how to import Choose Your Own Adventure (CYOA) releases to Stashapp with decision tree navigation.

## Overview

CYOA releases have a decision tree structure where:
- Audios are numbered (0, 1A, 1B, 2A, etc.)
- Each audio offers choices leading to different subsequent audios
- Multiple endings exist (bad, good, best)
- A flowchart image usually shows the structure

## Detection

The `analyze-reddit-post.js` script automatically detects CYOA releases using LLM analysis. When a CYOA is detected, the batch processor shows a warning indicating manual handling is required.

## Import Process

### Step 1: Create Decision Tree JSON

Create a JSON file with the complete decision tree structure:

```json
{
  "title": "Choose Your Own Adventure: Title Here",
  "reddit_post_id": "abc123",
  "performer": "performer_username",
  "script_author": "script_author_username",
  "total_audios": 27,
  "total_endings": 15,
  "flowchart_url": "https://example.com/flowchart.png",
  "audios": {
    "0": {
      "title": "Introduction",
      "audio_id": "Audio 0",
      "url": "https://soundgasm.net/u/performer/Audio-0",
      "tags": [],
      "isEnding": false,
      "endingType": null,
      "choices": [
        { "label": "Choice A", "leadsTo": "1A" },
        { "label": "Choice B", "leadsTo": "1B" }
      ]
    },
    "1A": {
      "title": "Choice A Result",
      "audio_id": "Audio 1",
      "url": "https://soundgasm.net/u/performer/Audio-1",
      "tags": ["Tag1", "Tag2"],
      "isEnding": true,
      "endingType": "good",
      "choices": []
    }
  }
}
```

### Step 2: Run the Import Script

```bash
# Full import (download, convert, import, update descriptions)
node cyoa-import.js data/cyoa/your_cyoa.json

# Download only (useful for testing)
node cyoa-import.js data/cyoa/your_cyoa.json --download-only

# Update descriptions only (after manual scene ID mapping)
node cyoa-import.js data/cyoa/your_cyoa.json --update-only

# Dry run (show what would be done)
node cyoa-import.js data/cyoa/your_cyoa.json --dry-run
```

## Data Structure

### Audio Node Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Display title for the audio |
| `audio_id` | string | Original audio identifier (e.g., "Audio 0") |
| `url` | string | Soundgasm URL for the audio |
| `tags` | array | Content tags for this audio |
| `isEnding` | boolean | Whether this is an ending node |
| `endingType` | string | Type of ending: "bad", "good", "best", or null |
| `choices` | array | List of choices leading to other audios |

### Choice Fields

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | Text displayed for the choice |
| `leadsTo` | string | Audio key this choice leads to |

## Scene Description Format

The import script generates scene descriptions with:

1. **Title** - The audio title as a heading
2. **Ending indicator** - For ending nodes, shows "BAD ENDING", "GOOD ENDING", or "BEST ENDING"
3. **Tags** - Content tags (excluding ending type tags)
4. **Choices** - Clickable links to other scenes
5. **Navigation** - "Start Over" link to return to the beginning

Example:

```markdown
# Section 0: Introduction

## Choose your path:

- [Take Her to the Library](/scenes/123)
- [Take Her Behind the Gym](/scenes/124)
- [Rape Her in the Bathroom](/scenes/125)

---
[Start Over](/scenes/120)
```

## Scene Mapping

After import, a `{post_id}_scene_mapping.json` file is created:

```json
{
  "0": "120",
  "1A": "121",
  "1B": "122"
}
```

This maps audio keys to Stashapp scene IDs and is used when updating descriptions.

## Groups

All CYOA scenes are automatically added to a Group named "CYOA: {Title}" with scene ordering preserved.

## Files Created

| File | Purpose |
|------|---------|
| `data/cyoa/{post_id}.json` | Decision tree data |
| `data/cyoa/{post_id}/` | Downloaded audio files |
| `data/cyoa/{post_id}_scene_mapping.json` | Audio key → Scene ID mapping |

## Troubleshooting

### Scene not found after scan
- Wait longer for Stashapp indexing (increase scan timeout)
- Check the video files exist in the Stashapp library directory
- Manually trigger a scan in Stashapp UI

### Description links not working
- Verify scene IDs in the mapping file are correct
- Check the scene URL format matches your Stashapp instance
- Ensure all scenes were imported before updating descriptions

### Missing audio files
- Verify Soundgasm URLs are still valid
- Check network connectivity
- Some audios may require authentication or be removed
