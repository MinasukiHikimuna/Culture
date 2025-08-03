#!/usr/bin/env node

/**
 * HotAudio Extractor - Node.js Version
 *
 * This script extracts individual audio files from HotAudio using Playwright and audio hooks.
 * It processes JSON index files created by hotaudio-indexer.js.
 *
 * Requirements:
 * 1. Install dependencies: npm install
 * 2. Install browser: npm run install-playwright
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const { Command } = require("commander");

class HotAudioExtractor {
  constructor(outputDir = "hotaudio_data") {
    this.outputDir = path.resolve(outputDir);
    this.requestDelay = 3000; // Longer delay for extraction
    this.lastRequestTime = 0;

    // Playwright setup
    this.browser = null;
    this.context = null;
  }

  async setupPlaywright() {
    try {
      console.log("🚀 Starting Playwright browser...");
      this.browser = await chromium.launch({
        headless: false,
        channel: 'chrome',
        args: ['--disable-blink-features=AutomationControlled']
      });
      this.context = await this.browser.newContext({
        viewport: { width: 1920, height: 1080 },
        userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36"
      });

      console.log("✅ Playwright browser initialized successfully");
    } catch (error) {
      console.error("❌ Failed to initialize Playwright:", error.message);
      console.log('💡 Run "npm run install-playwright" to install browser');
      throw error;
    }
  }

  async closeBrowser() {
    if (this.browser) {
      await this.browser.close();
      console.log("🔒 Browser closed");
    }
  }

  async rateLimit() {
    const now = Date.now();
    const timeSinceLastRequest = now - this.lastRequestTime;

    if (timeSinceLastRequest < this.requestDelay) {
      const waitTime = this.requestDelay - timeSinceLastRequest;
      console.log(`⏳ Rate limiting: waiting ${waitTime}ms...`);
      await new Promise((resolve) => setTimeout(resolve, waitTime));
    }

    this.lastRequestTime = Date.now();
  }

  async createNewPage(tempDir) {
    // Create a new page (tab) for this capture session
    const page = await this.context.newPage();

    // Inject Node.js bridge functions for file operations
    await page.exposeFunction(
      "__nodeWriteSegment",
      async (tempFileName, uint8Data) => {
        const tempFilePath = path.join(tempDir, tempFileName);
        await fs.writeFile(tempFilePath, Buffer.from(uint8Data));
      }
    );

    await page.exposeFunction(
      "__nodeCombineSegments",
      async (segmentFiles, combinedTempFile) => {
        const combinedTempPath = path.join(tempDir, combinedTempFile);
        const writeStream = require("fs").createWriteStream(combinedTempPath);

        return new Promise((resolve, reject) => {
          let processed = 0;

          const processNext = async () => {
            if (processed >= segmentFiles.length) {
              writeStream.end();
              resolve(combinedTempPath);
              return;
            }

            const segmentFile = segmentFiles[processed];
            const segmentPath = path.join(tempDir, segmentFile);

            try {
              const data = await fs.readFile(segmentPath);
              writeStream.write(data);
              // Clean up individual segment file
              await fs.unlink(segmentPath);
              processed++;
              setImmediate(processNext);
            } catch (e) {
              console.warn(
                `Warning: Could not read segment file ${segmentFile}:`,
                e.message
              );
              processed++;
              setImmediate(processNext);
            }
          };

          processNext();
        });
      }
    );

    // Inject the AudioSource hook script
    await page.addInitScript(this.getAudioSourceHook());
    
    // Monitor console for hook messages
    page.on('console', msg => {
      if (msg.text().includes('[AudioSource Hook]')) {
        console.log(msg.text());
      }
    });

    return page;
  }

  getAudioSourceHook() {
    return `
// AudioSource hook - captures decrypted audio segments as they're processed
(() => {
  console.log('[AudioSource Hook] Installing...');
  
  // Storage for captured audio segments
  window.__audioCapture = {
    segments: [], // Keep minimal metadata only
    metadata: {},
    sourceBuffers: new WeakMap(),
    totalBytes: 0,
    segmentFiles: [], // Track segment file paths
    sessionId: crypto.randomUUID() // Unique session ID for temp files
  };
  
  // Hook into MediaSource
  if (window.MediaSource) {
    const originalAddSourceBuffer = MediaSource.prototype.addSourceBuffer;
    
    MediaSource.prototype.addSourceBuffer = function(mimeType) {
      console.log('[AudioSource Hook] MediaSource.addSourceBuffer called with:', mimeType);
      
      const sourceBuffer = originalAddSourceBuffer.call(this, mimeType);
      
      // Store mime type
      window.__audioCapture.metadata.mimeType = mimeType;
      
      // Hook into SourceBuffer.appendBuffer
      const originalAppendBuffer = sourceBuffer.appendBuffer;
      let segmentIndex = 0;
      
      sourceBuffer.appendBuffer = function(data) {
        // Only log every 100th segment to reduce noise
        if (segmentIndex % 100 === 0) {
          console.log('[AudioSource Hook] SourceBuffer.appendBuffer called with', data.byteLength, 'bytes');
        }
        
        // Create temp file name for this segment
        const segmentId = segmentIndex.toString().padStart(8, '0');
        const tempFileName = \`\${window.__audioCapture.sessionId}-\${segmentId}.temp\`;
        
        // Store minimal segment metadata (no audio data in memory)
        const segment = {
          index: segmentIndex++,
          timestamp: Date.now(),
          tempFileName: tempFileName,
          byteLength: data.byteLength
        };
        
        window.__audioCapture.segments.push(segment);
        window.__audioCapture.segmentFiles.push(tempFileName);
        window.__audioCapture.totalBytes += data.byteLength;
        
        // Write segment data to temp file via Node.js bridge
        if (window.__nodeWriteSegment) {
          const uint8Data = new Uint8Array(data);
          // Fire and forget - don't block the audio processing
          window.__nodeWriteSegment(tempFileName, uint8Data).then(() => {
            // Only log successful writes every 100th segment
            if ((segment.index) % 100 === 0) {
              console.log(\`[AudioSource Hook] Successfully wrote segment \${segment.index}\`);
            }
          }).catch(writeError => {
            console.error(\`[AudioSource Hook] Failed to write segment \${segment.index}:\`, writeError);
          });
        } else {
          console.error('[AudioSource Hook] __nodeWriteSegment not available');
        }
        
        // Only log every 100th segment to reduce noise
        if ((segment.index) % 100 === 0) {
          console.log(\`[AudioSource Hook] Captured segment \${segment.index} (\${data.byteLength} bytes, total: \${window.__audioCapture.totalBytes} bytes)\`);
        }
        
        // Call original
        return originalAppendBuffer.call(this, data);
      };
      
      window.__audioCapture.sourceBuffers.set(sourceBuffer, {
        mimeType: mimeType,
        created: Date.now()
      });
      
      return sourceBuffer;
    };
  }
  
  // Export function to get captured audio
  window.exportAudioCapture = () => {
    const segments = window.__audioCapture.segments;
    console.log(\`[AudioSource Hook] Exporting \${segments.length} segments (\${window.__audioCapture.totalBytes} bytes total)\`);
    
    return {
      metadata: window.__audioCapture.metadata,
      totalBytes: window.__audioCapture.totalBytes,
      segmentCount: segments.length,
      segments: segments,
      captureTime: new Date().toISOString()
    };
  };
  
  // Function to reconstruct audio from temp files
  window.reconstructAudio = () => {
    const segments = window.__audioCapture.segments;
    if (segments.length === 0) {
      console.log('[AudioSource Hook] No segments captured yet');
      return null;
    }
    
    // Sort segments by index to ensure correct order
    segments.sort((a, b) => a.index - b.index);
    
    console.log(\`[AudioSource Hook] Starting reconstruction of \${segments.length} segments from temp files\`);
    
    // Create combined temp file name
    const combinedTempFile = \`\${window.__audioCapture.sessionId}.temp\`;
    
    // Request Node.js to combine all temp files
    if (window.__nodeCombineSegments) {
      const segmentFiles = segments.map(s => s.tempFileName);
      window.__nodeCombineSegments(segmentFiles, combinedTempFile);
      
      console.log('[AudioSource Hook] Segments combined successfully');
      return combinedTempFile;
    } else {
      console.error('[AudioSource Hook] Node.js bridge not available for file operations');
      return null;
    }
  };
  
  console.log('[AudioSource Hook] Ready. Functions available:');
  console.log('- window.exportAudioCapture() - Export captured segments as JSON');
  console.log('- window.reconstructAudio() - Reconstruct and download audio file');
})();
`;
  }

  async extractRelease(release, userDir, tempDir) {
    console.log(`🎵 Extracting: ${release.title} (${release.id})`);

    const audioName = this.sanitizeFilename(release.audioId);
    const audioFile = path.join(userDir, `${audioName}.mp4`);
    const metadataFile = path.join(userDir, `${audioName}.json`);

    // Check if already extracted
    try {
      await fs.access(audioFile);
      console.log(`⏭️  Skipping existing audio: ${audioName}`);
      return { skipped: true, reason: "already_exists" };
    } catch (e) {
      // File doesn't exist, proceed with extraction
    }

    const page = await this.createNewPage(tempDir);

    try {
      await this.rateLimit();
      console.log(`🌐 Navigating to: ${release.url}`);
      await page.goto(release.url, { waitUntil: "networkidle" });

      // Wait for player to load
      try {
        await page.waitForSelector('#player-progress-text', { timeout: 10000 });
      } catch (e) {
        console.log(`❌ No player found on ${release.url}, skipping...`);
        return { skipped: true, reason: 'no_player_found' };
      }

      // Save the HTML page content
      console.log(`💾 Saving HTML page content...`);
      try {
        const htmlContent = await page.content();
        const htmlFile = path.join(userDir, `${audioName}.html`);
        await fs.writeFile(htmlFile, htmlContent);
        console.log(`📄 HTML page saved to: ${htmlFile}`);
      } catch (error) {
        console.error(`❌ Error saving HTML:`, error);
      }

      // Get audio duration
      const durationText = await page.$eval('#player-progress-text', el => el.textContent);
      console.log(`⏱️  Audio duration: ${durationText}`);
      const totalDuration = durationText.split(' / ')[1];

      // Wait for everything to load
      await new Promise(resolve => setTimeout(resolve, 3000));

      // Click play button
      console.log(`▶️  Starting playback...`);
      const playButton = await page.$('#player-playpause');
      if (playButton) {
        await playButton.click();
      } else {
        console.log(`❌ Play button not found`);
        return { skipped: true, reason: 'no_play_button' };
      }

      // Monitor playback progress
      let lastProgress = '';
      let playbackComplete = false;
      const progressInterval = setInterval(async () => {
        try {
          const progress = await page.$eval('#player-progress-text', el => el.textContent);
          if (progress !== lastProgress) {
            console.log(`📊 [Progress] ${progress}`);
            lastProgress = progress;
            
            // Check if playback has ended
            const [current, total] = progress.split(' / ');
            if (current === total || progress.includes('PLAYBACK ERROR')) {
              playbackComplete = true;
              clearInterval(progressInterval);
              console.log(`✅ Playback complete!`);
            }
          }
          
          // Also check captured data
          const captureStatus = await page.evaluate(() => {
            if (window.__audioCapture) {
              return {
                segments: window.__audioCapture.segments.length,
                totalBytes: window.__audioCapture.totalBytes
              };
            }
            return null;
          });
          
          if (captureStatus && captureStatus.segments > 0) {
            console.log(`🎯 [Capture Status] ${captureStatus.segments} segments, ${(captureStatus.totalBytes / 1024 / 1024).toFixed(2)} MB`);
          }
        } catch (e) {
          // Player might have been removed
        }
      }, 5000);

      console.log(`⏳ Waiting for playback to complete (duration: ${totalDuration})...`);

      // Wait for playback to complete
      while (!playbackComplete) {
        await new Promise(resolve => setTimeout(resolve, 10000));
        
        try {
          await page.$eval('#player-progress-text', el => el.textContent);
        } catch (e) {
          console.log(`❌ Player element not found, stopping...`);
          break;
        }
      }

      clearInterval(progressInterval);

      // Wait a bit more to ensure all segments are captured (like original)
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Export captured data first (like original)
      console.log(`📤 Exporting captured audio data...`);
      
      const capturedData = await page.evaluate(() => {
        if (window.exportAudioCapture) {
          return window.exportAudioCapture();
        }
        return null;
      });
      
      if (!capturedData || capturedData.segments.length === 0) {
        console.error(`❌ No audio data was captured for ${release.title}`);
        return { skipped: true, reason: 'no_audio_captured' };
      }
      
      console.log(`📊 Captured ${capturedData.segmentCount} segments (${(capturedData.totalBytes / 1024 / 1024).toFixed(2)} MB)`);

      // Trigger browser-side file combination (like original)
      await page.evaluate(() => {
        if (window.reconstructAudio) {
          window.reconstructAudio();
        }
      });

      // Get the combined temp file name from the page (like original)
      const combinedTempFile = await page.evaluate(() => {
        if (window.__audioCapture && window.__audioCapture.sessionId) {
          return `${window.__audioCapture.sessionId}.temp`;
        }
        return null;
      });

      if (combinedTempFile) {
        const tempFilePath = path.join(tempDir, combinedTempFile);

        try {
          // Move the combined temp file to final location
          await fs.rename(tempFilePath, audioFile);
          console.log(`💾 Audio file moved: ${audioFile}`);
          
          // Validate the audio file using ffprobe
          console.log(`🔍 Validating audio file...`);
          const validation = await this.validateAudioFile(audioFile);
          
          if (!validation.valid) {
            console.error(`❌ Audio validation failed: ${validation.reason}`);
            if (validation.size) {
              console.error(`📊 File size: ${(validation.size / 1024 / 1024).toFixed(2)} MB`);
            }
            if (validation.duration) {
              console.error(`⏱️  Duration: ${validation.duration} seconds`);
            }
            
            // Delete invalid file
            try {
              await fs.unlink(audioFile);
              console.log(`🗑️  Deleted invalid audio file`);
            } catch (e) {
              console.warn(`⚠️  Could not delete invalid file: ${e.message}`);
            }
            
            return { error: `Audio validation failed: ${validation.reason}` };
          }
          
          console.log(`✅ Audio validated successfully!`);
          console.log(`📊 Duration: ${validation.duration} seconds, Size: ${(validation.size / 1024 / 1024).toFixed(2)} MB`);
          console.log(`🎵 Codec: ${validation.codec}, Bitrate: ${validation.bitrate}`);
          
          // Save metadata
          const metadata = {
            ...release,
            extractedAt: new Date().toISOString(),
            audioFile: path.basename(audioFile),
            validation: validation
          };

          await fs.writeFile(metadataFile, JSON.stringify(metadata, null, 2));
          console.log(`📋 Metadata saved: ${metadataFile}`);

          return { success: true, audioFile, metadataFile, validation };
        } catch (error) {
          console.error(`❌ Failed to save audio file: ${error.message}`);
          return { error: error.message };
        }
      } else {
        console.log(`⚠️  No audio captured for: ${release.title}`);
        return { skipped: true, reason: "no_audio_captured" };
      }
    } catch (error) {
      console.error(`❌ Error extracting ${release.title}: ${error.message}`);
      return { error: error.message };
    } finally {
      await page.close();
    }
  }

  sanitizeFilename(filename) {
    return filename.replace(/[<>:"/\\|?*]/g, "_").trim();
  }

  async validateAudioFile(audioFile) {
    try {
      const { exec } = require('child_process');
      const { promisify } = require('util');
      const execAsync = promisify(exec);
      
      // Check if file exists and has content
      const stats = await fs.stat(audioFile);
      if (stats.size === 0) {
        return { valid: false, reason: 'empty_file', size: 0 };
      }
      
      // Use ffprobe to validate audio file
      const ffprobeCmd = `ffprobe -v quiet -print_format json -show_format -show_streams "${audioFile}"`;
      const { stdout } = await execAsync(ffprobeCmd);
      const info = JSON.parse(stdout);
      
      if (!info.streams || info.streams.length === 0) {
        return { valid: false, reason: 'no_streams', size: stats.size };
      }
      
      const audioStream = info.streams.find(s => s.codec_type === 'audio');
      if (!audioStream) {
        return { valid: false, reason: 'no_audio_stream', size: stats.size };
      }
      
      const duration = parseFloat(info.format.duration || 0);
      if (duration < 10) { // Less than 10 seconds is probably incomplete
        return { valid: false, reason: 'too_short', duration, size: stats.size };
      }
      
      return { 
        valid: true, 
        duration, 
        size: stats.size,
        codec: audioStream.codec_name,
        bitrate: info.format.bit_rate
      };
      
    } catch (error) {
      return { valid: false, reason: 'validation_error', error: error.message };
    }
  }

  parseHotAudioUrl(url) {
    const match = url.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
    if (match) {
      const [, user, audioId] = match;
      return {
        id: `${user}/${audioId}`,
        url: url,
        title: audioId,
        user: user,
        audioId: audioId,
      };
    }
    return null;
  }

  async processSingleUrl(url) {
    console.log(`🎵 Processing single URL: ${url}`);

    const release = this.parseHotAudioUrl(url);
    if (!release) {
      throw new Error(`Invalid HotAudio URL format: ${url}`);
    }

    // Setup directories
    const userDir = path.join(this.outputDir, release.user);
    const tempDir = path.join(userDir, ".temp");

    await fs.mkdir(userDir, { recursive: true });
    await fs.mkdir(tempDir, { recursive: true });

    const result = await this.extractRelease(release, userDir, tempDir);

    // Cleanup temp directory
    try {
      await fs.rm(tempDir, { recursive: true });
    } catch (e) {
      console.warn(`⚠️  Could not clean up temp directory: ${e.message}`);
    }

    if (result.success) {
      console.log(`✅ Successfully extracted: ${release.title}`);
    } else if (result.skipped) {
      console.log(`⏭️  Skipped: ${release.title} (${result.reason})`);
    } else {
      console.error(`❌ Failed to extract: ${release.title} - ${result.error}`);
      throw new Error(result.error);
    }

    return result;
  }

  async processIndex(indexFile) {
    console.log(`📋 Loading index: ${indexFile}`);

    const indexData = JSON.parse(await fs.readFile(indexFile, "utf8"));
    const user = indexData.user || "unknown";

    console.log(
      `👤 Processing ${indexData.totalReleases} releases for user: ${user}`
    );

    // Setup directories
    const userDir = path.join(this.outputDir, user);
    const tempDir = path.join(userDir, ".temp");

    await fs.mkdir(userDir, { recursive: true });
    await fs.mkdir(tempDir, { recursive: true });

    const results = {
      total: indexData.releases.length,
      extracted: 0,
      skipped: 0,
      errors: 0,
      details: [],
    };

    // Process each release
    for (let i = 0; i < indexData.releases.length; i++) {
      const release = indexData.releases[i];
      console.log(
        `\n[${i + 1}/${indexData.releases.length}] Processing: ${release.title}`
      );

      const result = await this.extractRelease(release, userDir, tempDir);
      results.details.push({ release: release.id, ...result });

      if (result.success) {
        results.extracted++;
      } else if (result.skipped) {
        results.skipped++;
      } else {
        results.errors++;
      }
    }

    // Cleanup temp directory
    try {
      await fs.rm(tempDir, { recursive: true });
    } catch (e) {
      console.warn(`⚠️  Could not clean up temp directory: ${e.message}`);
    }

    // Save extraction report
    const reportFile = path.join(
      userDir,
      `extraction_report_${Date.now()}.json`
    );
    await fs.writeFile(reportFile, JSON.stringify(results, null, 2));

    console.log(`\n✅ Extraction completed!`);
    console.log(
      `📊 Results: ${results.extracted} extracted, ${results.skipped} skipped, ${results.errors} errors`
    );
    console.log(`📄 Report saved: ${reportFile}`);

    return results;
  }
}

// CLI Setup
const program = new Command();

program
  .name("hotaudio-extractor")
  .description("Extract HotAudio releases from index files or single URLs")
  .version("1.0.0");

program
  .option("-i, --input <file>", "Input index JSON file")
  .option("-u, --url <url>", "Single HotAudio URL to extract")
  .option("-o, --output <directory>", "Output directory", "hotaudio_data")
  .argument("[url]", "HotAudio URL to extract (alternative to -u flag)")
  .parse();

const options = program.opts();
const args = program.args;

async function main() {
  const urlFromArg = args[0];
  const urlFromOption = options.url;
  const inputFile = options.input;

  // Determine which URL to use (positional argument takes precedence)
  const targetUrl = urlFromArg || urlFromOption;

  if (!inputFile && !targetUrl) {
    console.error(
      "❌ Please provide either an input index file (-i) or a URL (as argument or -u flag)"
    );
    process.exit(1);
  }

  if (inputFile && targetUrl) {
    console.error("❌ Please provide either an input file or a URL, not both");
    process.exit(1);
  }

  const extractor = new HotAudioExtractor(options.output);

  try {
    await extractor.setupPlaywright();

    if (inputFile) {
      await extractor.processIndex(inputFile);
      console.log("🎉 All extractions completed successfully!");
    } else if (targetUrl) {
      await extractor.processSingleUrl(targetUrl);
      console.log("🎉 Single URL extraction completed successfully!");
    }
  } catch (error) {
    console.error("❌ Extraction failed:", error.message);
    process.exit(1);
  } finally {
    await extractor.closeBrowser();
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error("💥 Unexpected error:", error);
    process.exit(1);
  });
}

module.exports = { HotAudioExtractor };
