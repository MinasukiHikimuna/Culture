# Reddit Post Analyzer

This NodeJS script analyzes Reddit post data from r/gonewildaudio using a local LLM (via LM Studio) to extract structured information about audio releases.

## What it analyzes

The script examines Reddit post content to determine:

- **Performers**: How many voice actors are involved and who they are
- **Alternative versions**: Different variants of the audio (M4F/F4M, with/without SFX, etc.)
- **Series information**: Whether it's part of a series, has prequels/sequels
- **Script analysis**: Whether there's a script, authorship, availability (public vs private fills), and source location

## Prerequisites

1. **LM Studio**: Download and install [LM Studio](https://lmstudio.ai/)
2. **Local LLM**: Download a suitable model (e.g., Llama 3, Mistral, etc.)
3. **Node.js**: Version 22.0.0 or higher
4. **Dependencies**: Run `npm install` to install required packages

## Setup

1. Start LM Studio and load a model
2. Start the local server in LM Studio (default: http://localhost:1234)
3. Make sure the model is running and accepting requests

## Usage

### Analyze a single post

```bash
node analyze-reddit-post.js reddit_data/alekirser/1amzk7q.json
```

### Analyze all posts in a directory

```bash
node analyze-reddit-post.js reddit_data/alekirser/ --output analysis_results.json
```

### Use custom LM Studio URL or model

```bash
node analyze-reddit-post.js reddit_data/alekirser/1amzk7q.json --url http://localhost:8080/v1/chat/completions --model my-custom-model
```

### Using npm script

```bash
npm run analyze-reddit reddit_data/alekirser/1amzk7q.json
```

## Output Format

The script returns structured JSON with the following format:

```json
{
  "performers": {
    "count": 1,
    "primary": "alekirser",
    "additional": [],
    "confidence": "high"
  },
  "alternatives": {
    "hasAlternatives": false,
    "versions": [],
    "description": "Single version audio",
    "confidence": "high"
  },
  "series": {
    "isPartOfSeries": false,
    "hasPrequels": false,
    "hasSequels": false,
    "seriesName": null,
    "partNumber": null,
    "confidence": "high"
  },
  "script": {
    "url": null,
    "fillType": "original",
    "author": "alekirser"
  },
  "analysis_notes": "Self-written original content",
  "metadata": {
    "post_id": "1amzk7q",
    "username": "alekirser",
    "title": "[F4M] You Have A New Girlfriend...",
    "date": "2024-02-09T23:45:08",
    "reddit_url": "https://www.reddit.com/r/gonewildaudio/comments/1amzk7q/",
    "analyzed_at": "2024-01-15T10:30:00.000Z"
  }
}
```

## Script Analysis Fields

- **url**: Direct URL to the script if available, `null` if no URL provided
- **fillType**: Type of script fill:
  - `"original"`: Voice actor wrote their own script/scenario
  - `"public"`: Filling a publicly available script (with URL or clear reference)
  - `"private"`: Private fill (script shared privately with performer)
  - `"unknown"`: Cannot determine the type
- **author**: Username of the script author (always uses Reddit username, not nicknames)

## Confidence Levels

- **high**: Clear evidence in the text
- **medium**: Reasonable inference from context
- **low**: Uncertain or ambiguous

## Error Handling

- Connection errors to LM Studio are handled gracefully
- Invalid JSON responses are logged and reported
- Processing continues even if individual files fail
- Results include error information for failed analyses

## Tips for Best Results

1. Use a capable local model (7B+ parameters recommended)
2. Ensure stable connection to LM Studio
3. Process files in small batches to avoid overwhelming the LLM
4. Review results manually for accuracy, especially for complex posts

## Integration with GWASI Data

This analyzer is designed to work with the existing GWASI Reddit data structure and follows the audio-centric architecture outlined in CLAUDE.md. The analysis results can be used to:

- Identify collaborative releases
- Group alternative versions into releases
- Track series and storylines
- Link scripts to audio files
- Enhance metadata for Stashapp integration