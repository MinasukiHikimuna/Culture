/**
 * HotAudio Extractor
 *
 * Pure audio extractor - downloads directly to target path provided by caller.
 * Returns platform-agnostic schema.
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const crypto = require('crypto');

class HotAudioExtractor {
  constructor(config = {}) {
    this.platform = 'hotaudio';
    this.requestDelay = config.requestDelay || 3000;
    this.lastRequestTime = 0;
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
      throw error;
    }
  }

  async closeBrowser() {
    if (this.browser) {
      await this.browser.close();
      console.log("🔒 Browser closed");
    }
  }

  /**
   * Extract content from HotAudio URL
   * @param {string} url - HotAudio URL to extract
   * @param {object} targetPath - Target paths for output files
   * @param {string} targetPath.dir - Directory to save files
   * @param {string} targetPath.basename - Base filename (without extension)
   */
  async extract(url, targetPath) {
    await this.rateLimit();

    try {
      console.log(`📥 Processing: ${url}`);

      // Parse URL
      const urlInfo = this.parseHotAudioUrl(url);
      if (!urlInfo) {
        throw new Error("Invalid HotAudio URL format");
      }

      const { dir, basename } = targetPath;
      await fs.mkdir(dir, { recursive: true });

      // Check if already extracted (JSON exists)
      const jsonPath = path.join(dir, `${basename}.json`);
      try {
        await fs.access(jsonPath);
        const cached = JSON.parse(await fs.readFile(jsonPath, 'utf8'));
        console.log(`✅ Using cached extraction for: ${url}`);
        return cached;
      } catch (e) {
        // Not cached, continue with extraction
      }

      // Setup temp directory for audio capture
      const tempDir = path.join(dir, '.temp');
      await fs.mkdir(tempDir, { recursive: true });

      // Create new page with audio capture
      const page = await this.createNewPage(tempDir);

      try {
        await page.goto(url, { waitUntil: "networkidle" });

        // Check if player exists
        try {
          await page.waitForSelector('#player-progress-text', { timeout: 10000 });
        } catch (e) {
          throw new Error("No audio player found on page");
        }

        // Save HTML backup
        const htmlPath = path.join(dir, `${basename}.html`);
        await this.saveHtmlBackup(page, htmlPath);

        // Extract metadata from page
        const metadata = await this.extractPageMetadata(page, urlInfo);

        // Start playback and capture
        const audioPath = await this.captureAudio(page, tempDir, dir, basename);

        // Calculate checksum
        const checksum = await this.calculateChecksum(audioPath);

        // Get file stats
        const stats = await fs.stat(audioPath);

        // Validate audio file
        const validation = await this.validateAudioFile(audioPath);
        if (!validation.valid) {
          await fs.unlink(audioPath);
          throw new Error(`Audio validation failed: ${validation.reason}`);
        }

        // Build result in platform-agnostic schema
        const result = {
          audio: {
            sourceUrl: url,
            downloadUrl: null,
            filePath: audioPath,
            format: 'mp4',
            fileSize: stats.size,
            checksum: {
              sha256: checksum
            }
          },
          metadata: {
            title: metadata.title || urlInfo.audioId,
            author: urlInfo.user,
            description: metadata.description || '',
            tags: metadata.tags || [],
            duration: validation.duration,
            platform: {
              name: 'hotaudio',
              url: 'https://hotaudio.net'
            }
          },
          platformData: {
            audioId: urlInfo.audioId,
            validation: validation,
            extractedAt: new Date().toISOString()
          },
          backupFiles: {
            html: htmlPath,
            metadata: jsonPath
          }
        };

        // Save metadata (serves as completion marker)
        await fs.writeFile(jsonPath, JSON.stringify(result, null, 2));

        // Cleanup temp directory
        try {
          await fs.rm(tempDir, { recursive: true });
        } catch (e) {
          // Ignore cleanup errors
        }

        console.log(`✅ Successfully extracted: ${result.metadata.title}`);
        return result;

      } finally {
        await page.close();
      }

    } catch (error) {
      console.error(`❌ Failed to extract ${url}:`, error.message);
      throw error;
    }
  }

  parseHotAudioUrl(url) {
    const match = url.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
    if (match) {
      const [, user, audioId] = match;
      return {
        id: `${user}/${audioId}`,
        url: url,
        user: user,
        audioId: audioId,
      };
    }
    return null;
  }

  async extractPageMetadata(page, urlInfo) {
    try {
      const metadata = await page.evaluate(() => {
        // Try to extract title from various places
        let title = null;
        const titleElements = [
          'h1', 'h2', '.title', '.audio-title', '[class*="title"]'
        ];
        
        for (const selector of titleElements) {
          const element = document.querySelector(selector);
          if (element && element.textContent.trim()) {
            title = element.textContent.trim();
            break;
          }
        }
        
        // Extract description if available
        let description = null;
        const descElements = [
          '.description', '.audio-description', '[class*="description"]',
          'meta[name="description"]'
        ];
        
        for (const selector of descElements) {
          const element = document.querySelector(selector);
          if (element) {
            description = element.getAttribute('content') || element.textContent.trim();
            if (description) break;
          }
        }
        
        // Extract tags
        const tags = [];
        const tagElements = document.querySelectorAll('.tag, [class*="tag"]');
        tagElements.forEach(el => {
          const tag = el.textContent.trim();
          if (tag && !tags.includes(tag)) {
            tags.push(tag);
          }
        });
        
        return { title, description, tags };
      });
      
      return metadata;
    } catch (e) {
      return { title: null, description: null, tags: [] };
    }
  }

  async saveHtmlBackup(page, htmlPath) {
    const htmlContent = await page.content();
    await fs.writeFile(htmlPath, htmlContent);
  }

  async captureAudio(page, tempDir, dir, basename) {
    // Get audio duration
    const durationText = await page.$eval('#player-progress-text', el => el.textContent);
    console.log(`⏱️  Audio duration: ${durationText}`);

    // Click play button
    console.log(`▶️  Starting playback...`);
    const playButton = await page.$('#player-playpause');
    if (!playButton) {
      throw new Error("Play button not found");
    }
    await playButton.click();

    // Monitor playback progress
    let playbackComplete = false;
    const progressInterval = setInterval(async () => {
      try {
        const progress = await page.$eval('#player-progress-text', el => el.textContent);
        console.log(`📊 [Progress] ${progress}`);

        const [current, total] = progress.split(' / ');
        if (current === total || progress.includes('PLAYBACK ERROR')) {
          playbackComplete = true;
          clearInterval(progressInterval);
        }
      } catch (e) {
        // Player might have been removed
      }
    }, 5000);

    // Wait for playback to complete
    console.log(`⏳ Waiting for playback to complete...`);
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

    // Wait for capture to finish
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Export captured data
    console.log(`📤 Exporting captured audio data...`);
    const capturedData = await page.evaluate(() => {
      if (window.exportAudioCapture) {
        return window.exportAudioCapture();
      }
      return null;
    });

    if (!capturedData || capturedData.segments.length === 0) {
      throw new Error("No audio data was captured");
    }

    console.log(`📊 Captured ${capturedData.segmentCount} segments (${(capturedData.totalBytes / 1024 / 1024).toFixed(2)} MB)`);

    // Trigger browser-side file combination
    await page.evaluate(() => {
      if (window.reconstructAudio) {
        window.reconstructAudio();
      }
    });

    // Get combined temp file
    const combinedTempFile = await page.evaluate(() => {
      if (window.__audioCapture && window.__audioCapture.sessionId) {
        return `${window.__audioCapture.sessionId}.temp`;
      }
      return null;
    });

    if (!combinedTempFile) {
      throw new Error("Failed to combine audio segments");
    }

    // Move to final location
    const tempFilePath = path.join(tempDir, combinedTempFile);
    const audioFilePath = path.join(dir, `${basename}.mp4`);
    await fs.rename(tempFilePath, audioFilePath);

    return audioFilePath;
  }

  async createNewPage(tempDir) {
    const page = await this.context.newPage();

    // Inject Node.js bridge functions
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
              await fs.unlink(segmentPath);
              processed++;
              setImmediate(processNext);
            } catch (e) {
              console.warn(`Warning: Could not read segment file ${segmentFile}:`, e.message);
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
    
    return page;
  }

  getAudioSourceHook() {
    // Return the same audio capture hook from the original
    return `
// AudioSource hook - captures decrypted audio segments
(() => {
  console.log('[AudioSource Hook] Installing...');
  
  window.__audioCapture = {
    segments: [],
    metadata: {},
    sourceBuffers: new WeakMap(),
    totalBytes: 0,
    segmentFiles: [],
    sessionId: crypto.randomUUID()
  };
  
  if (window.MediaSource) {
    const originalAddSourceBuffer = MediaSource.prototype.addSourceBuffer;
    
    MediaSource.prototype.addSourceBuffer = function(mimeType) {
      console.log('[AudioSource Hook] MediaSource.addSourceBuffer called with:', mimeType);
      
      const sourceBuffer = originalAddSourceBuffer.call(this, mimeType);
      window.__audioCapture.metadata.mimeType = mimeType;
      
      const originalAppendBuffer = sourceBuffer.appendBuffer;
      let segmentIndex = 0;
      
      sourceBuffer.appendBuffer = function(data) {
        if (segmentIndex % 100 === 0) {
          console.log('[AudioSource Hook] SourceBuffer.appendBuffer called with', data.byteLength, 'bytes');
        }
        
        const segmentId = segmentIndex.toString().padStart(8, '0');
        const tempFileName = \`\${window.__audioCapture.sessionId}-\${segmentId}.temp\`;
        
        const segment = {
          index: segmentIndex++,
          timestamp: Date.now(),
          tempFileName: tempFileName,
          byteLength: data.byteLength
        };
        
        window.__audioCapture.segments.push(segment);
        window.__audioCapture.segmentFiles.push(tempFileName);
        window.__audioCapture.totalBytes += data.byteLength;
        
        if (window.__nodeWriteSegment) {
          const uint8Data = new Uint8Array(data);
          window.__nodeWriteSegment(tempFileName, uint8Data).catch(writeError => {
            console.error(\`[AudioSource Hook] Failed to write segment \${segment.index}:\`, writeError);
          });
        }
        
        return originalAppendBuffer.call(this, data);
      };
      
      window.__audioCapture.sourceBuffers.set(sourceBuffer, {
        mimeType: mimeType,
        created: Date.now()
      });
      
      return sourceBuffer;
    };
  }
  
  window.exportAudioCapture = () => {
    const segments = window.__audioCapture.segments;
    console.log(\`[AudioSource Hook] Exporting \${segments.length} segments\`);
    
    return {
      metadata: window.__audioCapture.metadata,
      totalBytes: window.__audioCapture.totalBytes,
      segmentCount: segments.length,
      segments: segments,
      captureTime: new Date().toISOString()
    };
  };
  
  window.reconstructAudio = () => {
    const segments = window.__audioCapture.segments;
    if (segments.length === 0) return null;
    
    segments.sort((a, b) => a.index - b.index);
    
    const combinedTempFile = \`\${window.__audioCapture.sessionId}.temp\`;
    
    if (window.__nodeCombineSegments) {
      const segmentFiles = segments.map(s => s.tempFileName);
      window.__nodeCombineSegments(segmentFiles, combinedTempFile);
      return combinedTempFile;
    }
    
    return null;
  };
  
  console.log('[AudioSource Hook] Ready');
})();
`;
  }

  async validateAudioFile(audioFile) {
    try {
      const { exec } = require('child_process');
      const { promisify } = require('util');
      const execAsync = promisify(exec);
      
      const stats = await fs.stat(audioFile);
      if (stats.size === 0) {
        return { valid: false, reason: 'empty_file', size: 0 };
      }
      
      // Use ffprobe to validate
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
      if (duration < 10) {
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

  async calculateChecksum(filePath) {
    const fileBuffer = await fs.readFile(filePath);
    const hashSum = crypto.createHash('sha256');
    hashSum.update(fileBuffer);
    return hashSum.digest('hex');
  }

  sanitizeFilename(filename) {
    return filename.replace(/[<>:"/\\|?*]/g, "_").trim();
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
}

module.exports = HotAudioExtractor;