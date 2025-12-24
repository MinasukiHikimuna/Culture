/**
 * Soundgasm Extractor
 *
 * Pure audio extractor - downloads directly to target path provided by caller.
 * Returns platform-agnostic schema.
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const crypto = require('crypto');

class SoundgasmExtractor {
  constructor(config = {}) {
    this.platform = 'soundgasm';
    this.requestDelay = config.requestDelay || 2000;
    this.lastRequestTime = 0;
    this.browser = null;
    this.page = null;
  }

  async setupPlaywright() {
    try {
      console.log("🚀 Starting Playwright browser...");
      this.browser = await chromium.launch({ headless: true });
      this.page = await this.browser.newPage();

      await this.page.setExtraHTTPHeaders({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36",
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
      this.browser = null;
      this.page = null;
    }
  }

  /**
   * Extract content from Soundgasm URL
   * @param {string} url - Soundgasm URL to extract
   * @param {object} targetPath - Target paths for output files
   * @param {string} targetPath.dir - Directory to save files
   * @param {string} targetPath.basename - Base filename (without extension)
   */
  async extract(url, targetPath) {
    await this.ensureRateLimit();

    try {
      console.log(`📥 Processing: ${url}`);

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

      // Navigate to page and extract metadata
      await this.page.goto(url, { waitUntil: "networkidle" });

      const metadata = await this.extractMetadata(url);
      const audioUrl = await this.extractAudioUrl();

      // Download audio file
      const audioFilePath = path.join(dir, `${basename}.m4a`);
      await this.downloadAudio(audioUrl, audioFilePath);

      // Calculate checksum
      const checksum = await this.calculateChecksum(audioFilePath);

      // Get file stats
      const stats = await fs.stat(audioFilePath);

      // Save HTML backup
      const htmlPath = path.join(dir, `${basename}.html`);
      await this.saveHtmlBackup(htmlPath);

      // Build result in platform-agnostic schema
      const result = {
        audio: {
          sourceUrl: url,
          downloadUrl: audioUrl,
          filePath: audioFilePath,
          format: 'm4a',
          fileSize: stats.size,
          checksum: {
            sha256: checksum
          }
        },
        metadata: {
          title: metadata.title,
          author: metadata.author,
          description: metadata.description || '',
          tags: metadata.tags || [],
          duration: metadata.expectedDuration,
          platform: {
            name: 'soundgasm',
            url: 'https://soundgasm.net'
          }
        },
        platformData: {
          titleFromUrl: metadata.titleFromUrl,
          pageTitle: metadata.pageTitle,
          extractedAt: new Date().toISOString()
        },
        backupFiles: {
          html: htmlPath,
          metadata: jsonPath
        }
      };

      // Save metadata (serves as completion marker)
      await fs.writeFile(jsonPath, JSON.stringify(result, null, 2));

      console.log(`✅ Successfully extracted: ${metadata.title}`);
      return result;

    } catch (error) {
      console.error(`❌ Failed to extract ${url}:`, error.message);
      throw error;
    }
  }

  async extractMetadata(url) {
    try {
      // Extract author and title from URL
      const urlMatch = url.match(
        /https?:\/\/(?:www\.)?soundgasm\.net\/u\/([A-Za-z0-9\-_]+)\/([A-Za-z0-9\-_]+)/
      );
      if (!urlMatch) {
        throw new Error("Invalid Soundgasm URL format");
      }

      const author = urlMatch[1];
      const titleFromUrl = urlMatch[2];

      // Extract detailed title, description, and duration from page
      const { detailedTitle, description, duration } = await this.page.evaluate(() => {
        const titleElement = document.querySelector(".jp-title");
        const descriptionElement = document.querySelector(".jp-description");
        
        // Try to get duration from the page
        let duration = null;
        const timeElements = document.querySelectorAll('[class*="time"], .jp-duration, .duration');
        for (const el of timeElements) {
          const text = el.textContent.trim();
          if (text.includes(':')) {
            const match = text.match(/-?(\d+):(\d+)/);
            if (match) {
              const minutes = parseInt(match[1]);
              const seconds = parseInt(match[2]);
              duration = minutes * 60 + seconds;
            }
          }
        }

        return {
          detailedTitle: titleElement ? titleElement.textContent.trim() : null,
          description: descriptionElement
            ? descriptionElement.textContent.trim()
            : null,
          duration: duration
        };
      });

      // Get page title as fallback
      const pageTitle = await this.page.title();
      const title = detailedTitle || pageTitle || titleFromUrl;

      // Extract tags from description
      const tags = this.parseTags(description || "");

      return {
        title: title.trim(),
        author: author.trim(),
        titleFromUrl: titleFromUrl, // For filename
        pageTitle: pageTitle,
        description: (description || "").trim(),
        tags: tags,
        expectedDuration: duration // Duration in seconds
      };
    } catch (error) {
      console.error("Failed to extract metadata:", error);
      throw error;
    }
  }

  async extractAudioUrl() {
    try {
      const audioUrl = await this.page.evaluate(() => {
        // First try to find the audio element
        const audioElement = document.querySelector("audio");
        if (audioElement && audioElement.src) {
          return audioElement.src;
        }

        // Fallback to searching in HTML content
        const content = document.documentElement.innerHTML;
        const match = content.match(
          /(https?:\/\/media\.soundgasm\.net\/sounds\/[A-Z0-9a-z]+\.m4a)/i
        );
        return match ? match[1] : null;
      });
      
      if (!audioUrl) {
        throw new Error("Could not find audio URL in Soundgasm page");
      }

      return audioUrl;
    } catch (error) {
      console.error("Failed to extract audio URL:", error);
      throw error;
    }
  }

  async downloadAudio(audioUrl, audioFilePath) {
    try {
      console.log(`⬇️  Downloading audio: ${audioUrl}`);

      const response = await this.page.context().request.get(audioUrl);
      if (!response.ok()) {
        throw new Error(`HTTP ${response.status()}: ${response.statusText()}`);
      }

      const buffer = await response.body();
      await fs.writeFile(audioFilePath, buffer);

      console.log(`💾 Audio saved: ${audioFilePath}`);
    } catch (error) {
      console.error(`Failed to download audio from ${audioUrl}:`, error);
      throw error;
    }
  }

  async saveHtmlBackup(htmlPath) {
    const htmlContent = await this.page.content();
    await fs.writeFile(htmlPath, htmlContent);
  }

  async calculateChecksum(filePath) {
    const fileBuffer = await fs.readFile(filePath);
    const hashSum = crypto.createHash('sha256');
    hashSum.update(fileBuffer);
    return hashSum.digest('hex');
  }

  parseTags(description) {
    const tagRegex = /\[([^\]]+)\]/g;
    const tags = [];
    let match;
    
    while ((match = tagRegex.exec(description)) !== null) {
      tags.push(match[1]);
    }
    
    return tags;
  }

  sanitizeFilename(filename) {
    return filename.replace(/[<>:"/\\|?*]/g, '-').replace(/\s+/g, '-');
  }

  async ensureRateLimit() {
    const now = Date.now();
    const timeSinceLastRequest = now - this.lastRequestTime;
    
    if (timeSinceLastRequest < this.requestDelay) {
      const delay = this.requestDelay - timeSinceLastRequest;
      console.log(`⏳ Rate limiting: waiting ${delay}ms`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
    
    this.lastRequestTime = Date.now();
  }
}

module.exports = SoundgasmExtractor;