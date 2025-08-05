# HotAudio Follow Feature

The HotAudio follow feature is designed to handle Choose Your Own Adventure (CYOA) type audio content where a single HotAudio link in a Reddit post leads to a branching story with multiple audio files.

## Background

Many CYOA audios on HotAudio only have a single link posted on Reddit, but the actual content consists of multiple interconnected audio files that users navigate through by making choices. The follow feature automatically discovers and maps all these connected audio files.

## Usage

```bash
# Extract and download all audio files
node hotaudio-follow-extractor.js https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up

# Extract without downloading (metadata only)
node hotaudio-follow-extractor.js --no-download https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up

# Show browser window for debugging
node hotaudio-follow-extractor.js --show-browser https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up

# Limit recursion depth
node hotaudio-follow-extractor.js --max-depth 3 https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up

# Specify output directories
node hotaudio-follow-extractor.js --output-dir ./audio --enrichment-dir ./metadata https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up
```

## Output

### Story Tree Structure

The follow feature generates a hierarchical tree structure representing the CYOA story:

```json
{
  "url": "https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up",
  "title": "Wake Up - A Choose Your Own Adventure",
  "user": "The_LUST_Project",
  "audio": "T1-Wake-Up",
  "duration": "15:23",
  "children": [
    {
      "url": "https://hotaudio.net/u/The_LUST_Project/T2-Option-A",
      "title": "Option A - Go to the Kitchen",
      "children": [...]
    },
    {
      "url": "https://hotaudio.net/u/The_LUST_Project/T2-Option-B",
      "title": "Option B - Stay in Bed",
      "children": [...]
    }
  ]
}
```

### Summary Statistics

The extractor also generates summary statistics:

```json
{
  "stats": {
    "totalNodes": 15,
    "totalAudioFiles": 15,
    "downloadedFiles": 15,
    "totalDurationSeconds": 12580,
    "formattedTotalDuration": "3h 29m",
    "maxDepth": 4,
    "performers": ["The_LUST_Project"],
    "tags": ["CYOA", "Adventure", "Fantasy"]
  }
}
```

## Integration with GWASI Extractor

When processing Reddit posts that contain HotAudio CYOA content:

1. The extractor identifies single HotAudio links in Reddit posts
2. If the link appears to be a CYOA (based on title or tags), it triggers follow mode
3. All discovered audio files are added to the release
4. The story structure is preserved in the metadata

## Example Workflow

```javascript
// In your Reddit post processor
if (post.body.includes('hotaudio.net')) {
  const hotAudioUrls = extractHotAudioUrls(post.body);
  
  for (const url of hotAudioUrls) {
    if (isCYOA(post.title) || post.tags.includes('CYOA')) {
      // Use follow extractor
      const extractor = new HotAudioFollowExtractor();
      const result = await extractor.extract(url);
      
      // Add all found audios to the release
      release.audioVariants = result.summary.audioFiles.map(audio => ({
        platform: 'hotaudio',
        url: audio.url,
        title: audio.title,
        duration: audio.duration,
        filePath: audio.filePath
      }));
      
      // Store the story structure
      release.metadata.storyStructure = result.storyTree;
    }
  }
}
```

## Technical Details

- Uses Playwright for browser automation
- Recursively follows HotAudio links found on each page
- Implements cycle detection to avoid infinite loops
- Respects maximum depth limits
- Can operate in headless or visible browser mode
- Supports both metadata extraction and full audio download

## Known Limitations

- Requires Playwright and Chrome/Chromium
- Some CYOA audios may use JavaScript navigation that's harder to detect
- Rate limiting may apply for large story trees
- Download functionality requires proper authentication if content is restricted