#!/usr/bin/env node

/**
 * Soundgasm Extractor - Refactored with Common Data Structures
 * 
 * Example of how to refactor an existing extractor to use the new common
 * data structures and transformation system.
 */

const { BaseExtractor, ExtractedContent } = require('./common-extractor-types');
const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");

class SoundgasmExtractor extends BaseExtractor {
  constructor(outputDir = "soundgasm_data", config = {}) {
    super('soundgasm', outputDir, {
      defaultPipeline: 'AUDIO_TO_VIDEO', // Convert all audio to video by default
      ...config
    });
    
    this.requestDelay = 2000;
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
   * Extract content from Soundgasm URL using new data structures
   */
  async extract(url, analysisMetadata = null) {
    await this.ensureRateLimit();
    
    try {
      console.log(`📥 Processing: ${url}`);
      
      // Navigate to page and extract metadata
      await this.page.goto(url, { waitUntil: "networkidle" });
      
      const metadata = await this.extractMetadata(url);
      const audioUrl = await this.extractAudioUrl();
      
      // Create ExtractedContent instance
      const content = new ExtractedContent({
        id: this.generateContentId(url),
        sourceUrl: url,
        platform: this.platform,
        title: metadata.title,
        author: metadata.author,
        description: metadata.description,
        tags: metadata.tags,
        metadata: {
          soundgasmMetadata: metadata,
          audioUrl: audioUrl,
          analysisMetadata: analysisMetadata // Include LLM analysis data
        },
        enrichmentData: {
          llmAnalysis: analysisMetadata // Also add to enrichmentData for clarity
        }
      });

      // Download the original audio file
      const audioFilePath = await this.downloadAudio(audioUrl, metadata);
      
      // Create MediaFile for the original audio
      content.originalMediaFile = await this.createMediaFile(
        audioFilePath, 
        audioUrl, 
        { 
          platform: 'soundgasm',
          originalFormat: 'm4a'
        }
      );

      // Execute transformations (audio -> video with gwa.png)
      await this.executeTransformations(content);

      // Save metadata
      await this.saveMetadata(content);

      console.log(`✅ Successfully extracted: ${metadata.title}`);
      return content;

    } catch (error) {
      console.error(`❌ Failed to extract ${url}:`, error.message);
      throw error;
    }
  }

  async extractMetadata(url) {
    try {
      // Extract author and title from URL like the original
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
        
        // Try to get duration from the page - look for time display elements
        let duration = null;
        const timeElements = document.querySelectorAll('[class*="time"], .jp-duration, .duration');
        for (const el of timeElements) {
          const text = el.textContent.trim();
          if (text.includes(':') && text.includes('-')) {
            // Extract duration from format like "-49:15"
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

      // Use detailed title for metadata, but URL slug for filename (like original)
      const pageTitle = await this.page.title();
      const title = detailedTitle || pageTitle || titleFromUrl;

      // Extract tags from description
      const tags = this.parseTags(description || "");

      return {
        title: title.trim(),
        author: author.trim(),
        titleFromUrl: titleFromUrl, // For filename
        description: (description || "").trim(),
        tags: tags,
        expectedDuration: duration // Duration from page in seconds
      };
    } catch (error) {
      console.error("Failed to extract metadata:", error);
      throw error;
    }
  }

  async extractAudioUrl() {
    try {
      // Use the same approach as the original extractor
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

  async downloadAudio(audioUrl, metadata) {
    // Use titleFromUrl for filename and create release directory structure
    const filename = metadata.titleFromUrl;
    const authorDir = path.join(this.outputDir, metadata.author);
    const releaseDir = path.join(authorDir, filename);
    await fs.mkdir(releaseDir, { recursive: true });

    const audioFilePath = path.join(releaseDir, `${filename}.m4a`);

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

  async saveMetadata(content) {
    const releaseDir = path.dirname(content.originalMediaFile.filePath);
    const baseName = path.basename(content.originalMediaFile.filePath, path.extname(content.originalMediaFile.filePath));
    
    // Save comprehensive metadata including transformations
    const metadataPath = path.join(releaseDir, `${baseName}.json`);
    await fs.writeFile(metadataPath, JSON.stringify(content, null, 2));

    // Save HTML backup
    const htmlContent = await this.page.content();
    const htmlPath = path.join(releaseDir, `${baseName}.html`);
    await fs.writeFile(htmlPath, htmlContent);
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

  generateContentId(url) {
    const crypto = require('crypto');
    return crypto.createHash('md5').update(url).digest('hex');
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

// Example usage
if (require.main === module) {
  const { Command } = require("commander");
  
  const program = new Command();
  program
    .name("soundgasm-extractor")
    .description("Extract audio content from Soundgasm with transformations")
    .version("2.0.0");

  program
    .command("extract")
    .description("Extract content from a Soundgasm URL")
    .argument("<url>", "Soundgasm URL to extract")
    .option("-o, --output <dir>", "Output directory", "soundgasm_data")
    .option("--no-transform", "Disable transformations")
    .option("--pipeline <name>", "Transformation pipeline", "AUDIO_TO_VIDEO")
    .option("--analysis-metadata <file>", "Path to analysis metadata JSON file")
    .action(async (url, options) => {
      const extractor = new SoundgasmExtractor(options.output, {
        enableTransformations: options.transform,
        defaultPipeline: options.pipeline
      });

      try {
        await extractor.setupPlaywright();
        
        // Load analysis metadata if provided
        let analysisMetadata = null;
        if (options.analysisMetadata) {
          try {
            const fs = require('fs');
            const analysisData = fs.readFileSync(options.analysisMetadata, 'utf8');
            analysisMetadata = JSON.parse(analysisData);
            console.log('📋 Loaded analysis metadata');
          } catch (error) {
            console.warn(`⚠️ Warning: Could not load analysis metadata: ${error.message}`);
          }
        }
        
        const content = await extractor.extract(url, analysisMetadata);
        
        console.log("\n📊 Extraction Summary:");
        console.log(`Title: ${content.title}`);
        console.log(`Author: ${content.author}`);
        console.log(`Original file: ${content.originalMediaFile.filePath}`);
        console.log(`Transformations: ${content.transformations.length}`);
        
        if (content.transformedMediaFiles.length > 0) {
          console.log(`Final output: ${content.getFinalMediaFile().filePath}`);
        }
        
      } catch (error) {
        console.error("❌ Extraction failed:", error.message);
        process.exit(1);
      } finally {
        await extractor.closeBrowser();
      }
    });

  program.parse();
}