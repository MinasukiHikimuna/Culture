#!/usr/bin/env node

/**
 * Soundgasm Extractor V2 - Pure Audio Extraction
 * 
 * Focused solely on extracting audio and platform metadata.
 * No knowledge of LLM analysis or enrichment data.
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const crypto = require('crypto');

class SoundgasmExtractor {
  constructor(config = {}) {
    this.outputDir = config.outputDir || "soundgasm_data";
    this.requestDelay = config.requestDelay || 2000;
    this.version = "2.0.0";
    
    this.lastRequestTime = 0;
    this.browser = null;
    this.page = null;
  }

  async setupPlaywright() {
    console.log("🚀 Starting Playwright browser...");
    this.browser = await chromium.launch({ headless: true });
    this.page = await this.browser.newPage();

    await this.page.setExtraHTTPHeaders({
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    });

    console.log("✅ Playwright browser initialized");
  }

  async closeBrowser() {
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
      this.page = null;
    }
  }

  /**
   * Main extraction method - returns unified schema
   */
  async extract(url) {
    // Check cache first
    const cached = await this.checkCache(url);
    if (cached) {
      console.log(`📦 Using cached data for: ${url}`);
      return cached;
    }
    
    await this.ensureRateLimit();
    
    console.log(`📥 Extracting: ${url}`);
    
    try {
      // Navigate and extract page data
      await this.page.goto(url, { waitUntil: "networkidle" });
      
      const pageData = await this.extractPageData(url);
      const audioUrl = await this.extractAudioUrl();
      
      // Download audio file
      const audioFile = await this.downloadAudio(audioUrl, pageData);
      
      // Calculate checksum
      const checksum = await this.calculateChecksum(audioFile.path);
      
      // Save HTML backup
      const htmlBackup = await this.saveHtmlBackup(pageData);
      
      // Build result in unified schema
      const result = {
        audio: {
          sourceUrl: url,
          downloadUrl: audioUrl,
          filePath: audioFile.path,
          format: audioFile.format,
          fileSize: audioFile.size,
          checksum: checksum
        },
        metadata: {
          title: pageData.title,
          author: pageData.author,
          description: pageData.description,
          tags: pageData.tags,
          duration: pageData.duration,
          uploadDate: null, // Soundgasm doesn't provide this
          extractedAt: new Date().toISOString(),
          platform: {
            name: 'soundgasm',
            extractorVersion: this.version
          }
        },
        platformData: {
          titleFromUrl: pageData.titleFromUrl,
          expectedDuration: pageData.expectedDuration,
          pageTitle: pageData.pageTitle
        },
        backupFiles: {
          html: htmlBackup,
          metadata: null // Will be set after saving
        }
      };
      
      // Save metadata and create marker
      const metadataFile = await this.saveMetadata(result, audioFile.dir);
      result.backupFiles.metadata = metadataFile;
      
      // Create completion marker
      await this.createCompletionMarker(audioFile.dir, result);
      
      console.log(`✅ Extraction complete: ${pageData.title}`);
      return result;
      
    } catch (error) {
      console.error(`❌ Extraction failed: ${error.message}`);
      throw error;
    }
  }

  async extractPageData(url) {
    // Parse URL for author and title
    const urlMatch = url.match(
      /https?:\/\/(?:www\.)?soundgasm\.net\/u\/([^\/]+)\/([^\/]+)/
    );
    if (!urlMatch) {
      throw new Error("Invalid Soundgasm URL format");
    }

    const [, author, titleFromUrl] = urlMatch;

    // Extract from page
    const pageData = await this.page.evaluate(() => {
      const titleEl = document.querySelector(".jp-title");
      const descEl = document.querySelector(".jp-description");
      
      // Try to extract duration
      let duration = null;
      const timeEls = document.querySelectorAll('[class*="time"], .jp-duration');
      for (const el of timeEls) {
        const text = el.textContent.trim();
        const match = text.match(/-?(\d+):(\d+)/);
        if (match) {
          duration = parseInt(match[1]) * 60 + parseInt(match[2]);
          break;
        }
      }

      return {
        detailedTitle: titleEl?.textContent.trim(),
        description: descEl?.textContent.trim(),
        expectedDuration: duration
      };
    });

    const pageTitle = await this.page.title();
    const title = pageData.detailedTitle || pageTitle || titleFromUrl;

    // Parse tags from description
    const tags = this.parseTags(pageData.description || "");

    return {
      title: title.trim(),
      author: author.trim(),
      titleFromUrl: titleFromUrl,
      description: (pageData.description || "").trim(),
      tags: tags,
      duration: pageData.expectedDuration,
      expectedDuration: pageData.expectedDuration,
      pageTitle: pageTitle
    };
  }

  async extractAudioUrl() {
    const audioUrl = await this.page.evaluate(() => {
      // Try audio element first
      const audioEl = document.querySelector("audio");
      if (audioEl?.src) {
        return audioEl.src;
      }

      // Fallback to regex search
      const html = document.documentElement.innerHTML;
      const match = html.match(
        /(https?:\/\/media\.soundgasm\.net\/sounds\/[A-Z0-9a-z]+\.m4a)/i
      );
      return match ? match[1] : null;
    });
    
    if (!audioUrl) {
      throw new Error("Could not find audio URL in page");
    }

    return audioUrl;
  }

  async downloadAudio(audioUrl, pageData) {
    const filename = this.sanitizeFilename(pageData.titleFromUrl);
    const authorDir = path.join(this.outputDir, this.sanitizeFilename(pageData.author));
    const releaseDir = path.join(authorDir, filename);
    
    await fs.mkdir(releaseDir, { recursive: true });

    const audioPath = path.join(releaseDir, `${filename}.m4a`);

    console.log(`⬇️  Downloading: ${audioUrl}`);
    
    const response = await this.page.context().request.get(audioUrl);
    if (!response.ok()) {
      throw new Error(`HTTP ${response.status()}: ${response.statusText()}`);
    }

    const buffer = await response.body();
    await fs.writeFile(audioPath, buffer);
    
    const stats = await fs.stat(audioPath);
    
    console.log(`💾 Audio saved: ${audioPath} (${(stats.size / 1024 / 1024).toFixed(2)} MB)`);
    
    return {
      path: audioPath,
      dir: releaseDir,
      format: 'm4a',
      size: stats.size
    };
  }

  async calculateChecksum(filePath) {
    const fileBuffer = await fs.readFile(filePath);
    
    const sha256 = crypto.createHash('sha256').update(fileBuffer).digest('hex');
    const md5 = crypto.createHash('md5').update(fileBuffer).digest('hex');
    
    return { sha256, md5 };
  }

  async saveHtmlBackup(pageData) {
    const html = await this.page.content();
    const filename = this.sanitizeFilename(pageData.titleFromUrl);
    const authorDir = path.join(this.outputDir, this.sanitizeFilename(pageData.author));
    const releaseDir = path.join(authorDir, filename);
    const htmlPath = path.join(releaseDir, `${filename}.html`);
    
    await fs.writeFile(htmlPath, html);
    return htmlPath;
  }

  async saveMetadata(result, outputDir) {
    const metadataPath = path.join(outputDir, 'metadata.json');
    await fs.writeFile(metadataPath, JSON.stringify(result, null, 2));
    return metadataPath;
  }

  async createCompletionMarker(outputDir, result) {
    const markerPath = path.join(outputDir, '.extracted');
    const marker = {
      extractedAt: result.metadata.extractedAt,
      extractorVersion: this.version,
      success: true,
      audioFile: path.basename(result.audio.filePath),
      checksum: result.audio.checksum.sha256
    };
    
    await fs.writeFile(markerPath, JSON.stringify(marker, null, 2));
  }

  async checkCache(url) {
    // Derive cache location from URL
    const urlMatch = url.match(
      /https?:\/\/(?:www\.)?soundgasm\.net\/u\/([^\/]+)\/([^\/]+)/
    );
    if (!urlMatch) return null;
    
    const [, author, titleFromUrl] = urlMatch;
    const filename = this.sanitizeFilename(titleFromUrl);
    const authorDir = path.join(this.outputDir, this.sanitizeFilename(author));
    const releaseDir = path.join(authorDir, filename);
    const markerPath = path.join(releaseDir, '.extracted');
    
    try {
      await fs.access(markerPath);
      
      // Load cached metadata
      const metadataPath = path.join(releaseDir, 'metadata.json');
      const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf8'));
      
      return metadata;
    } catch {
      return null;
    }
  }

  parseTags(description) {
    const tags = [];
    const tagRegex = /\[([^\]]+)\]/g;
    let match;
    
    while ((match = tagRegex.exec(description)) !== null) {
      tags.push(match[1]);
    }
    
    return tags;
  }

  sanitizeFilename(filename) {
    return filename
      .replace(/[<>:"/\\|?*]/g, '-')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  }

  async ensureRateLimit() {
    const now = Date.now();
    const elapsed = now - this.lastRequestTime;
    
    if (elapsed < this.requestDelay) {
      const wait = this.requestDelay - elapsed;
      console.log(`⏳ Rate limiting: ${wait}ms`);
      await new Promise(resolve => setTimeout(resolve, wait));
    }
    
    this.lastRequestTime = Date.now();
  }
}

module.exports = SoundgasmExtractor;

// CLI interface
if (require.main === module) {
  const { Command } = require("commander");
  
  const program = new Command();
  program
    .name("soundgasm-extractor-v2")
    .description("Extract audio from Soundgasm - pure extraction, no enrichment")
    .version("2.0.0");

  program
    .command("extract")
    .description("Extract audio from a Soundgasm URL")
    .argument("<url>", "Soundgasm URL to extract")
    .option("-o, --output <dir>", "Output directory", "soundgasm_data")
    .action(async (url, options) => {
      const extractor = new SoundgasmExtractor({
        outputDir: options.output
      });

      try {
        await extractor.setupPlaywright();
        const result = await extractor.extract(url);
        
        console.log("\n📊 Extraction Result:");
        console.log(`Title: ${result.metadata.title}`);
        console.log(`Author: ${result.metadata.author}`);
        console.log(`File: ${result.audio.filePath}`);
        console.log(`Size: ${(result.audio.fileSize / 1024 / 1024).toFixed(2)} MB`);
        console.log(`SHA256: ${result.audio.checksum.sha256}`);
        
      } catch (error) {
        console.error("❌ Extraction failed:", error.message);
        process.exit(1);
      } finally {
        await extractor.closeBrowser();
      }
    });

  program.parse();
}