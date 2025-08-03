/**
 * Common Data Structures for Audio/Video Extractors
 * 
 * This module defines unified data structures and transformation pipelines
 * for all audio/video extractors in the GWASI system.
 */

/**
 * Core media file structure - represents any audio or video file
 */
class MediaFile {
  constructor(data = {}) {
    this.id = data.id || null;                    // Unique identifier for this media file
    this.originalUrl = data.originalUrl || null;  // Source URL where media was found
    this.sourceType = data.sourceType || null;    // 'audio' | 'video'
    this.mimeType = data.mimeType || null;        // Original MIME type
    this.format = data.format || null;            // File format (m4a, mp3, wav, mp4, etc.)
    this.filePath = data.filePath || null;        // Local file path
    this.fileSize = data.fileSize || null;        // File size in bytes
    this.duration = data.duration || null;        // Duration in seconds
    this.checksum = data.checksum || {};          // Hash checksums { sha256: '...', md5: '...' }
    this.extractedAt = data.extractedAt || new Date().toISOString();
    this.metadata = data.metadata || {};          // Format-specific metadata
  }
}

/**
 * Transformation record - tracks how original media was transformed
 */
class MediaTransformation {
  constructor(data = {}) {
    this.id = data.id || null;                    // Unique transformation ID
    this.sourceFileId = data.sourceFileId || null; // ID of the source MediaFile
    this.targetFileId = data.targetFileId || null; // ID of the resulting MediaFile
    this.transformationType = data.transformationType || null; // 'audio_to_video' | 'format_conversion' | 'encoding'
    this.parameters = data.parameters || {};      // Transformation parameters
    this.command = data.command || null;          // Command that was executed
    this.executedAt = data.executedAt || new Date().toISOString();
    this.success = data.success || false;
    this.error = data.error || null;
  }
}

/**
 * Extracted content - represents the complete extracted data from a source
 */
class ExtractedContent {
  constructor(data = {}) {
    this.id = data.id || null;                    // Unique content ID
    this.sourceUrl = data.sourceUrl || null;      // Original source URL
    this.platform = data.platform || null;       // 'soundgasm' | 'whypit' | 'hotaudio' | etc.
    this.title = data.title || null;
    this.author = data.author || data.user || null;
    this.description = data.description || null;
    this.tags = data.tags || [];
    this.extractedAt = data.extractedAt || new Date().toISOString();
    
    // Media files (original and transformed)
    this.originalMediaFile = data.originalMediaFile || null; // MediaFile instance
    this.transformedMediaFiles = data.transformedMediaFiles || []; // Array of MediaFile instances
    this.transformations = data.transformations || []; // Array of MediaTransformation instances
    
    // Additional metadata
    this.metadata = data.metadata || {};          // Platform-specific metadata
    this.enrichmentData = data.enrichmentData || {}; // Data from Reddit/Patreon posts
  }

  /**
   * Add a transformed media file with transformation record
   */
  addTransformation(transformedFile, transformation) {
    this.transformedMediaFiles.push(transformedFile);
    this.transformations.push(transformation);
  }

  /**
   * Get the final output file (usually the last transformation)
   */
  getFinalMediaFile() {
    if (this.transformedMediaFiles.length > 0) {
      return this.transformedMediaFiles[this.transformedMediaFiles.length - 1];
    }
    return this.originalMediaFile;
  }
}

/**
 * Transformation pipeline configuration
 */
class TransformationPipeline {
  constructor(data = {}) {
    this.name = data.name || null;
    this.description = data.description || null;
    this.steps = data.steps || [];               // Array of transformation steps
    this.enabled = data.enabled !== false;
  }
}

/**
 * Default transformation pipelines
 */
const DEFAULT_PIPELINES = {
  // Standard audio -> video with GWA image
  AUDIO_TO_VIDEO: new TransformationPipeline({
    name: 'audio_to_video',
    description: 'Convert audio file to video with static GWA image',
    steps: [
      {
        type: 'audio_to_video',
        command: 'ffmpeg -loop 1 -i gwa.png -i {input} -c:v libx264 -c:a copy -shortest -pix_fmt yuv420p {output}',
        outputFormat: 'mkv',
        preserveOriginal: true
      }
    ]
  }),

  // WAV -> FLAC -> Video (for Patreon content)
  PATREON_PIPELINE: new TransformationPipeline({
    name: 'patreon_wav_pipeline',
    description: 'Convert WAV to FLAC, then to video for Patreon content',
    steps: [
      {
        type: 'format_conversion',
        command: 'ffmpeg -i {input} -c:a flac {output}',
        outputFormat: 'flac',
        preserveOriginal: true
      },
      {
        type: 'audio_to_video',
        command: 'ffmpeg -loop 1 -i gwa.png -i {input} -c:v libx264 -c:a copy -shortest -pix_fmt yuv420p {output}',
        outputFormat: 'mkv',
        preserveOriginal: true
      }
    ]
  }),

  // Just audio format conversion
  FORMAT_CONVERSION: new TransformationPipeline({
    name: 'format_conversion',
    description: 'Convert between audio formats while preserving quality',
    steps: [
      {
        type: 'format_conversion',
        command: 'ffmpeg -i {input} -c:a {codec} {output}',
        outputFormat: '{target_format}',
        preserveOriginal: true
      }
    ]
  })
};

/**
 * Base extractor class that all extractors should extend
 */
class BaseExtractor {
  constructor(platform, outputDir, config = {}) {
    this.platform = platform;
    this.outputDir = outputDir;
    this.config = {
      enableTransformations: true,
      defaultPipeline: 'AUDIO_TO_VIDEO',
      preserveOriginals: true,
      calculateChecksums: true,
      ...config
    };
    this.transformationPipelines = { ...DEFAULT_PIPELINES };
  }

  /**
   * Calculate file checksums
   */
  async calculateChecksums(filePath) {
    const crypto = require('crypto');
    const fs = require('fs');
    
    const data = await fs.promises.readFile(filePath);
    return {
      sha256: crypto.createHash('sha256').update(data).digest('hex'),
      md5: crypto.createHash('md5').update(data).digest('hex')
    };
  }

  /**
   * Create MediaFile instance from local file
   */
  async createMediaFile(filePath, originalUrl = null, metadata = {}) {
    const fs = require('fs');
    const path = require('path');
    const { execSync } = require('child_process');

    const stats = await fs.promises.stat(filePath);
    const ext = path.extname(filePath).toLowerCase();
    
    // Try to get duration and format info
    let duration = null;
    let format = ext.substring(1);
    let mimeType = null;

    try {
      // Use ffprobe to get media info
      const ffprobeOutput = execSync(
        `ffprobe -v quiet -print_format json -show_format -show_streams "${filePath}"`,
        { encoding: 'utf8' }
      );
      const mediaInfo = JSON.parse(ffprobeOutput);
      
      if (mediaInfo.format) {
        duration = parseFloat(mediaInfo.format.duration);
        format = mediaInfo.format.format_name;
      }
      
      if (mediaInfo.streams && mediaInfo.streams[0]) {
        mimeType = mediaInfo.streams[0].codec_name;
      }
    } catch (error) {
      console.warn(`Could not get media info for ${filePath}:`, error.message);
    }

    const mediaFile = new MediaFile({
      id: this.generateFileId(filePath),
      originalUrl,
      sourceType: this.isAudioFile(ext) ? 'audio' : 'video',
      mimeType,
      format,
      filePath,
      fileSize: stats.size,
      duration,
      metadata
    });

    // Calculate checksums if enabled
    if (this.config.calculateChecksums) {
      mediaFile.checksum = await this.calculateChecksums(filePath);
    }

    return mediaFile;
  }

  /**
   * Execute transformation pipeline
   */
  async executeTransformations(content, pipelineName = null) {
    if (!this.config.enableTransformations || !content.originalMediaFile) {
      return content;
    }

    const pipeline = this.transformationPipelines[pipelineName || this.config.defaultPipeline];
    if (!pipeline || !pipeline.enabled) {
      return content;
    }

    let currentFile = content.originalMediaFile;

    for (const step of pipeline.steps) {
      try {
        const transformedFile = await this.executeTransformationStep(currentFile, step, content);
        const transformation = new MediaTransformation({
          id: this.generateTransformationId(),
          sourceFileId: currentFile.id,
          targetFileId: transformedFile.id,
          transformationType: step.type,
          parameters: step,
          command: this.buildCommand(step, currentFile, transformedFile),
          success: true
        });

        content.addTransformation(transformedFile, transformation);
        currentFile = transformedFile;

      } catch (error) {
        console.error(`Transformation step ${step.type} failed:`, error);
        
        const failedTransformation = new MediaTransformation({
          id: this.generateTransformationId(),
          sourceFileId: currentFile.id,
          transformationType: step.type,
          parameters: step,
          success: false,
          error: error.message
        });
        
        content.transformations.push(failedTransformation);
        break; // Stop pipeline on failure
      }
    }

    return content;
  }

  /**
   * Execute a single transformation step
   */
  async executeTransformationStep(sourceFile, step, content) {
    const path = require('path');
    const { execSync } = require('child_process');

    // Generate output filename - use clean filename without transformation suffix
    const sourceExt = path.extname(sourceFile.filePath);
    const baseName = path.basename(sourceFile.filePath, sourceExt);
    const outputExt = step.outputFormat.startsWith('{') ? sourceExt : `.${step.outputFormat}`;
    const outputPath = path.join(path.dirname(sourceFile.filePath), `${baseName}${outputExt}`);

    // Build and execute command
    const command = this.buildCommand(step, sourceFile, { filePath: outputPath });
    console.log(`Executing: ${command}`);
    
    execSync(command, { stdio: 'pipe' });

    // Create MediaFile for transformed output
    const transformedFile = await this.createMediaFile(outputPath, sourceFile.originalUrl, {
      transformedFrom: sourceFile.id,
      transformationType: step.type
    });

    // Validate video duration matches audio duration for audio_to_video transformations
    if (step.type === 'audio_to_video') {
      await this.validateVideoDuration(sourceFile, transformedFile);
    }

    return transformedFile;
  }

  /**
   * Build transformation command with parameter substitution
   */
  buildCommand(step, sourceFile, targetFile) {
    let command = step.command;
    
    // Replace placeholders
    command = command.replace('{input}', `"${sourceFile.filePath}"`);
    command = command.replace('{output}', `"${targetFile.filePath}"`);
    
    // Handle dynamic parameters
    if (step.outputFormat.includes('{')) {
      // Could implement dynamic format selection here
    }
    
    return command;
  }

  /**
   * Utility methods
   */
  generateFileId(filePath) {
    const crypto = require('crypto');
    const path = require('path');
    return crypto.createHash('md5').update(filePath + Date.now()).digest('hex');
  }

  generateTransformationId() {
    const crypto = require('crypto');
    return crypto.createHash('md5').update(Date.now().toString()).digest('hex');
  }

  isAudioFile(ext) {
    return ['.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac'].includes(ext.toLowerCase());
  }

  /**
   * Validate that video duration matches source audio duration
   */
  async validateVideoDuration(sourceFile, videoFile, toleranceSeconds = 1.0) {
    const sourceDuration = sourceFile.duration;
    const videoDuration = videoFile.duration;
    
    if (!sourceDuration || !videoDuration) {
      console.warn(`⚠️  Could not validate duration - source: ${sourceDuration}s, video: ${videoDuration}s`);
      return;
    }

    const durationDiff = Math.abs(sourceDuration - videoDuration);
    
    if (durationDiff > toleranceSeconds) {
      console.error(`❌ Duration mismatch! Audio: ${sourceDuration}s, Video: ${videoDuration}s (diff: ${durationDiff}s)`);
      throw new Error(`Video duration (${videoDuration}s) doesn't match audio duration (${sourceDuration}s). Difference: ${durationDiff}s`);
    } else {
      console.log(`✅ Duration validation passed: ${sourceDuration}s ≈ ${videoDuration}s (diff: ${durationDiff}s)`);
    }
  }

  /**
   * Abstract method - must be implemented by subclasses
   */
  async extract(url) {
    throw new Error('extract() method must be implemented by subclass');
  }
}

module.exports = {
  MediaFile,
  MediaTransformation,
  ExtractedContent,
  TransformationPipeline,
  BaseExtractor,
  DEFAULT_PIPELINES
};