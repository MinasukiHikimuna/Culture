# Audio/Video Extractor Transformation System

## Overview

The transformation system provides a unified way to process audio and video files across all extractors in the GWASI system. It supports chained transformations with full provenance tracking.

## Key Features

- **Common Data Structures**: Unified `MediaFile`, `ExtractedContent`, and `MediaTransformation` classes
- **Configurable Pipelines**: JSON-based transformation pipeline configuration
- **Provenance Tracking**: Complete audit trail of all transformations with SHA-256 checksums
- **Platform-Specific Defaults**: Different pipelines for different platforms (e.g., Patreon WAV→FLAC→Video)
- **Error Recovery**: Graceful handling of transformation failures with detailed error logging

## Data Structures

### MediaFile
Represents any audio or video file with metadata:
```javascript
{
  id: "unique-file-id",
  originalUrl: "https://source.com/audio.m4a",
  sourceType: "audio", // "audio" | "video"
  mimeType: "audio/mp4",
  format: "m4a",
  filePath: "/path/to/file.m4a",
  fileSize: 12345678,
  duration: 456.78,
  checksum: {
    sha256: "abc123...",
    md5: "def456..."
  },
  extractedAt: "2025-08-03T12:00:00.000Z",
  metadata: {} // Format-specific metadata
}
```

### ExtractedContent
Complete extracted content with transformations:
```javascript
{
  id: "content-id",
  sourceUrl: "https://soundgasm.net/u/user/audio",
  platform: "soundgasm",
  title: "Audio Title",
  author: "Username",
  description: "Description text",
  tags: ["tag1", "tag2"],
  originalMediaFile: MediaFile, // Original downloaded file
  transformedMediaFiles: [MediaFile], // Array of transformed files
  transformations: [MediaTransformation], // Transformation records
  metadata: {}, // Platform-specific metadata
  enrichmentData: {} // Reddit/Patreon enrichment data
}
```

### MediaTransformation
Records how files were transformed:
```javascript
{
  id: "transformation-id",
  sourceFileId: "source-file-id",
  targetFileId: "target-file-id", 
  transformationType: "audio_to_video",
  parameters: {}, // Transformation parameters
  command: "ffmpeg -i input.m4a -i gwa.png ...",
  executedAt: "2025-08-03T12:00:00.000Z",
  success: true,
  error: null
}
```

## Default Transformation Pipelines

### AUDIO_TO_VIDEO
Converts audio files to video with static GWA image:
```bash
ffmpeg -i {input} -i gwa.png -c:v libx264 -c:a copy -shortest {output}
```

### PATREON_PIPELINE  
For Patreon WAV files - converts to FLAC then video:
```bash
# Step 1: WAV → FLAC
ffmpeg -i {input} -c:a flac -compression_level 8 {output}

# Step 2: FLAC → Video with GWA image
ffmpeg -i {input} -i gwa.png -c:v libx264 -c:a copy -shortest {output}
```

### HIGH_QUALITY_ENCODE
High quality archival encoding (disabled by default):
```bash
# Step 1: High quality FLAC
ffmpeg -i {input} -c:a flac -compression_level 12 {output}

# Step 2: High quality video
ffmpeg -i {input} -i gwa.png -c:v libx264 -preset veryslow -crf 18 -c:a copy -shortest {output}
```

## Usage Examples

### Basic Extractor Implementation
```javascript
const { BaseExtractor, ExtractedContent } = require('./common-extractor-types');

class MyExtractor extends BaseExtractor {
  constructor() {
    super('myplatform', 'output_dir', {
      defaultPipeline: 'AUDIO_TO_VIDEO',
      enableTransformations: true
    });
  }

  async extract(url) {
    // Extract metadata and download original file
    const content = new ExtractedContent({
      sourceUrl: url,
      platform: this.platform,
      title: "Audio Title"
    });

    // Download and create MediaFile
    const audioPath = await this.downloadAudio(url);
    content.originalMediaFile = await this.createMediaFile(audioPath, url);

    // Execute transformations 
    await this.executeTransformations(content);

    return content;
  }
}
```

### Custom Pipeline Configuration
```javascript
const extractor = new MyExtractor('output', {
  defaultPipeline: 'PATREON_PIPELINE',
  enableTransformations: true,
  calculateChecksums: true
});

// Add custom pipeline
extractor.transformationPipelines.CUSTOM = {
  name: 'custom_pipeline',
  steps: [
    {
      type: 'normalize_audio',
      command: 'ffmpeg -i {input} -af loudnorm {output}',
      outputFormat: 'wav'
    }
  ]
};
```

### Disable Transformations
```javascript
const extractor = new MyExtractor('output', {
  enableTransformations: false // Only download originals
});
```

## File Organization

The system maintains the original extractor directory structure while adding transformation outputs:

```
soundgasm_data/
├── LurkyDip/
│   ├── Audio-Title.m4a              # Original audio
│   ├── Audio-Title_audio_to_video.mp4 # Transformed video
│   ├── Audio-Title.json             # Complete metadata with transformations
│   └── Audio-Title.html             # HTML backup
```

## Configuration

### transformation-config.json
Central configuration for all transformation pipelines:
- Pipeline definitions
- Platform defaults  
- Global settings
- Requirements checking

### Platform Defaults
```json
{
  "platformDefaults": {
    "soundgasm": "AUDIO_TO_VIDEO",
    "whypit": "AUDIO_TO_VIDEO", 
    "hotaudio": "AUDIO_TO_VIDEO",
    "patreon": "PATREON_PIPELINE"
  }
}
```

## Requirements

1. **FFmpeg**: Required for all transformations
2. **gwa.png**: Static image for audio-to-video conversion
3. **Node.js**: Runtime for the transformation system

## Error Handling

- Transformations can fail without affecting the original extraction
- Failed transformations are recorded with error details
- Pipeline execution stops on first failure
- Original files are always preserved

## Checksum Verification

All files include SHA-256 and MD5 checksums for:
- Data integrity verification
- Duplicate detection
- Change tracking
- Archival validation

## Migration Guide

To upgrade existing extractors:

1. Extend `BaseExtractor` instead of implementing from scratch
2. Replace custom download logic with `createMediaFile()`
3. Use `ExtractedContent` for structured output
4. Enable transformations with `executeTransformations()`
5. Update output format to include transformation metadata

## Performance Considerations

- Transformations run sequentially by default
- Large files may require significant disk space during processing
- FFmpeg operations are CPU-intensive
- Consider disabling transformations for batch processing of large datasets