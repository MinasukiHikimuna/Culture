# Reddit Post Analyzer

This Python script analyzes Reddit post data from r/gonewildaudio using a local LLM (via LM Studio) to extract structured information about audio releases.

## What it analyzes

The script examines Reddit post content to determine:

- **Performers**: How many voice actors are involved and who they are
- **Alternative versions**: Different variants of the audio (M4F/F4M, with/without SFX, etc.)
- **Series information**: Whether it's part of a series, has prequels/sequels
- **Script analysis**: Whether there's a script, authorship, availability (public vs private fills), and source location

## Prerequisites

1. **LM Studio**: Download and install [LM Studio](https://lmstudio.ai/)
2. **Local LLM**: Download a suitable model (e.g., Llama 3, Mistral, etc.)
3. **Python**: Version 3.11 or higher
4. **uv**: Install [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

1. Start LM Studio and load a model
2. Start the local server in LM Studio (default: http://localhost:1234)
3. Make sure the model is running and accepting requests

## Usage

### Analyze a single post

```bash
uv run python analyze_reddit_post.py extracted_data/reddit/alekirser/1amzk7q.json
```

### Analyze all posts in a directory

```bash
uv run python analyze_reddit_post.py extracted_data/reddit/alekirser/ --output analysis_results.json
```

### Use custom LM Studio URL or model

```bash
uv run python analyze_reddit_post.py extracted_data/reddit/alekirser/1amzk7q.json --url http://localhost:8080/v1/chat/completions --model my-custom-model
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
  "audio_versions": [
    {
      "version_name": "Main Audio",
      "description": "Primary audio version",
      "urls": [
        {
          "platform": "Soundgasm",
          "url": "https://soundgasm.net/u/alekirser/audio-title"
        },
        {
          "platform": "Whypit",
          "url": "https://whyp.it/tracks/12345/audio-title"
        }
      ]
    }
  ],
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

## Audio Versions Structure

The `audio_versions` field contains an array of different audio versions, each with:

- **version_name**: Descriptive name (e.g., "Main Audio", "F4M Version", "Bloopers")
- **description**: Detailed description of this version
- **urls**: Array of URLs where this version is available, each containing:
  - **platform**: Platform name (e.g., "Soundgasm", "Whypit", "Hotaudio")
  - **url**: Direct URL to the audio file

### Example Audio Version Patterns

**Single version with multiple platforms:**
```json
"audio_versions": [
  {
    "version_name": "Main Audio",
    "description": "Primary audio version",
    "urls": [
      { "platform": "Soundgasm", "url": "https://soundgasm.net/u/performer/audio" },
      { "platform": "Whypit", "url": "https://whyp.it/tracks/12345/audio" }
    ]
  }
]
```

**Multiple versions (F4M/F4F):**
```json
"audio_versions": [
  {
    "version_name": "F4M Version",
    "description": "Version for male listeners",
    "urls": [
      { "platform": "Soundgasm", "url": "https://soundgasm.net/u/performer/f4m-audio" }
    ]
  },
  {
    "version_name": "F4F Version", 
    "description": "Version for female listeners",
    "urls": [
      { "platform": "Soundgasm", "url": "https://soundgasm.net/u/performer/f4f-audio" }
    ]
  }
]
```

**Main audio plus bloopers:**
```json
"audio_versions": [
  {
    "version_name": "Main Audio",
    "description": "Primary audio version",
    "urls": [
      { "platform": "Soundgasm", "url": "https://soundgasm.net/u/performer/main" }
    ]
  },
  {
    "version_name": "Bloopers",
    "description": "Outtakes and mistakes from recording",
    "urls": [
      { "platform": "Soundgasm", "url": "https://soundgasm.net/u/performer/bloopers" }
    ]
  }
]
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

## Analysis Storage & Quality Assurance

The analyzer includes a simple storage system for building a high-quality dataset of analyses:

### Simplified Storage Structure

Each Reddit post gets its own directory with all related analyses:

```
analyses/
├── 1ljhk83/                    # Reddit post ID  
│   ├── original_post.json      # Complete Reddit post data
│   ├── llm_analysis.json       # Approved LLM analysis (matches reference quality)
│   ├── reference_analysis.json # Gold standard analysis (Claude Sonnet)
│   └── notes.md               # Human notes and observations
└── 1m9aefh/                   # Another post
    ├── original_post.json
    ├── llm_analysis.json       # Only saved when approved
    ├── reference_analysis.json
    └── notes.md
```

### Workflow for Quality Improvement

**IMPORTANT**: Always create the gold standard reference analysis first, then test local LLM against it.

1. **Create Gold Standard Reference**: Manually analyze post with high-quality model (Claude Sonnet)
   ```bash
   # Analyze the post carefully and save reference analysis using AnalysisStorage
   # This becomes your training target and quality benchmark
   ```

2. **Test Local LLM**: Run your local model on the same post (output only, don't save yet)
   ```bash
   # Test local LLM analysis - review output in terminal
   uv run python analyze_reddit_post.py post.json
   ```

3. **Compare Results**: Check LLM output against reference standard
   - Identify specific areas where local LLM failed
   - Note patterns in errors (script detection, performer counting, etc.)

4. **Iterate and Improve**:
   - **If LLM failed**: Update prompts based on failures, test again (don't save)
   - **If LLM succeeded**: Save as approved analysis
   ```bash
   # Only save when LLM analysis meets the reference standard
   uv run python analyze_reddit_post.py post.json --save-approved
   ```

### Benefits of This Approach

- **No clutter**: Only store high-quality analyses  
- **Focus on improvement**: Use failures to enhance prompts, not storage
- **Clean dataset**: Build training data from verified correct analyses only
- **Efficient iteration**: Quick test-and-improve cycle without file management

### Benefits of Simple Structure

- **Easy Navigation**: All data for a post in one place
- **Clear Comparison**: LLM vs reference side-by-side  
- **Flexible Status**: Metadata tracks approval/rejection status
- **Version Control Friendly**: Simple file structure works well with git

### Analysis Files

**llm_analysis.json** - Contains the LLM result plus metadata:
```json
{
  "performers": { "count": 3, "primary": "alekirser", ... },
  "script": { "author": "alekirser", "fillType": "original" },
  "llm_metadata": {
    "model": "mistral-7b-instruct",
    "approved": false,
    "experimental": true,
    "saved_at": "2025-08-03T09:40:02Z"
  }
}
```

**reference_analysis.json** - The corrected/accepted version:
```json
{
  "performers": { "count": 3, "primary": "alekirser", ... },
  "script": { "author": "inscrutableuser", "fillType": "private" },
  "reference_metadata": {
    "analyzer": "claude-sonnet-4",
    "saved_at": "2025-08-03T09:42:00Z"
  }
}
```

## Integration with GWASI Data

This analyzer is designed to work with the existing GWASI Reddit data structure and follows the audio-centric architecture outlined in CLAUDE.md. The analysis results can be used to:

- Identify collaborative releases
- Group alternative versions into releases  
- Track series and storylines
- Link scripts to audio files
- Enhance metadata for Stashapp integration
- Build comprehensive quality datasets for model improvement