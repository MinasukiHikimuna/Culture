#!/usr/bin/env node

/**
 * Soundgasm Extractor - Refactored for Clean Architecture
 * 
 * Pure audio extractor without LLM awareness
 * Returns platform-agnostic schema
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const crypto = require('crypto');

class SoundgasmExtractor {
  constructor(outputDir = "soundgasm_data", config = {}) {
    this.outputDir = outputDir;
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
   * Pure extraction without any LLM dependencies
   */
  async extract(url) {
    await this.ensureRateLimit();
    
    try {
      console.log(`📥 Processing: ${url}`);
      
      // Check cache first
      const cached = await this.checkCache(url);
      if (cached) {
        console.log(`✅ Using cached extraction for: ${url}`);
        return cached;
      }
      
      // Navigate to page and extract metadata
      await this.page.goto(url, { waitUntil: "networkidle" });
      
      const metadata = await this.extractMetadata(url);
      const audioUrl = await this.extractAudioUrl();
      
      // Create output directory structure
      const authorDir = path.join(this.outputDir, this.sanitizeFilename(metadata.author));
      const releaseDir = path.join(authorDir, this.sanitizeFilename(metadata.titleFromUrl));
      await fs.mkdir(releaseDir, { recursive: true });
      
      // Download audio file
      const audioFilePath = await this.downloadAudio(audioUrl, metadata, releaseDir);
      
      // Calculate checksum
      const checksum = await this.calculateChecksum(audioFilePath);
      
      // Get file stats
      const stats = await fs.stat(audioFilePath);
      
      // Save HTML backup
      const htmlPath = await this.saveHtmlBackup(releaseDir, metadata.titleFromUrl);
      
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
          html: htmlPath
        }
      };
      
      // Save metadata
      const metadataPath = path.join(releaseDir, `${metadata.titleFromUrl}.json`);
      await fs.writeFile(metadataPath, JSON.stringify(result, null, 2));
      result.backupFiles.metadata = metadataPath;
      
      // Create completion marker
      await this.createCompletionMarker(releaseDir, result);
      
      console.log(`✅ Successfully extracted: ${metadata.title}`);
      return result;

    } catch (error) {
      console.error(`❌ Failed to extract ${url}:`, error.message);
      throw error;
    }
  }

  async checkCache(url) {
    try {
      // Derive cache location from URL
      const urlMatch = url.match(/soundgasm\.net\/u\/([^\/]+)\/([^\/]+)/);
      if (!urlMatch) return null;
      
      const [, author, titleSlug] = urlMatch;
      const cacheDir = path.join(this.outputDir, this.sanitizeFilename(author), this.sanitizeFilename(titleSlug));
      const markerFile = path.join(cacheDir, '.extracted');
      
      // Check if marker file exists
      await fs.access(markerFile);
      
      // Load and return cached result
      const metadataFiles = await fs.readdir(cacheDir);
      const jsonFile = metadataFiles.find(f => f.endsWith('.json') && f !== '.extracted');
      
      if (jsonFile) {
        const cached = JSON.parse(await fs.readFile(path.join(cacheDir, jsonFile), 'utf8'));
        return cached;
      }
    } catch (e) {
      // Not cached
    }
    return null;
  }

  async createCompletionMarker(outputDir, result) {
    const markerFile = path.join(outputDir, '.extracted');
    const markerData = {
      url: result.audio.sourceUrl,
      extractedAt: result.platformData.extractedAt,
      checksum: result.audio.checksum.sha256
    };
    await fs.writeFile(markerFile, JSON.stringify(markerData, null, 2));
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

  async downloadAudio(audioUrl, metadata, releaseDir) {
    const filename = `${metadata.titleFromUrl}.m4a`;
    const audioFilePath = path.join(releaseDir, filename);

    try {
      console.log(`⬇️  Downloading audio: ${audioUrl}`);
      
      const response = await this.page.context().request.get(audioUrl);
      if (!response.ok()) {
        throw new Error(`HTTP ${response.status()}: ${response.statusText()}`);
      }

      const buffer = await response.body();
      await fs.writeFile(audioFilePath, buffer);
      
      console.log(`💾 Audio saved: ${audioFilePath}`);
      return audioFilePath;
    } catch (error) {
      console.error(`Failed to download audio from ${audioUrl}:`, error);
      throw error;
    }
  }

  async saveHtmlBackup(releaseDir, titleFromUrl) {
    const htmlContent = await this.page.content();
    const htmlPath = path.join(releaseDir, `${titleFromUrl}.html`);
    await fs.writeFile(htmlPath, htmlContent);
    return htmlPath;
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

// CLI Interface
if (require.main === module) {
  const { Command } = require("commander");
  
  const program = new Command();
  program
    .name("soundgasm-extractor")
    .description("Extract audio content from Soundgasm - pure extraction without LLM dependencies")
    .version("3.0.0");

  program
    .command("extract")
    .description("Extract content from a Soundgasm URL")
    .argument("<url>", "Soundgasm URL to extract")
    .option("-o, --output <dir>", "Output directory", "soundgasm_data")
    .action(async (url, options) => {
      const extractor = new SoundgasmExtractor(options.output);

      try {
        await extractor.setupPlaywright();
        
        const content = await extractor.extract(url);
        
        console.log("\n📊 Extraction Summary:");
        console.log(`Title: ${content.metadata.title}`);
        console.log(`Author: ${content.metadata.author}`);
        console.log(`Audio file: ${content.audio.filePath}`);
        console.log(`File size: ${(content.audio.fileSize / 1024 / 1024).toFixed(2)} MB`);
        console.log(`Checksum: ${content.audio.checksum.sha256.substring(0, 16)}...`);
        
      } catch (error) {
        console.error("❌ Extraction failed:", error.message);
        process.exit(1);
      } finally {
        await extractor.closeBrowser();
      }
    });

  program
    .command("batch")
    .description("Extract multiple URLs from a file")
    .argument("<file>", "File containing URLs (one per line)")
    .option("-o, --output <dir>", "Output directory", "soundgasm_data")
    .action(async (file, options) => {
      const extractor = new SoundgasmExtractor(options.output);
      
      try {
        const content = await fs.readFile(file, 'utf8');
        const urls = content.split('\n').filter(line => line.trim() && !line.startsWith('#'));
        
        console.log(`📋 Found ${urls.length} URLs to process`);
        
        await extractor.setupPlaywright();
        
        const results = [];
        for (let i = 0; i < urls.length; i++) {
          const url = urls[i].trim();
          console.log(`\n[${i + 1}/${urls.length}] Processing: ${url}`);
          
          try {
            const content = await extractor.extract(url);
            results.push({ success: true, url, title: content.metadata.title });
          } catch (error) {
            console.error(`❌ Failed: ${error.message}`);
            results.push({ success: false, url, error: error.message });
          }
        }
        
        const successful = results.filter(r => r.success).length;
        const failed = results.filter(r => !r.success).length;
        
        console.log(`\n📊 Batch Summary:`);
        console.log(`✅ Successful: ${successful}`);
        console.log(`❌ Failed: ${failed}`);
        
      } catch (error) {
        console.error("❌ Batch processing failed:", error.message);
        process.exit(1);
      } finally {
        await extractor.closeBrowser();
      }
    });

  program.parse();
}