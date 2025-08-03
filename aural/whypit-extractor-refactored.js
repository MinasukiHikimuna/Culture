#!/usr/bin/env node

/**
 * Whyp.it Extractor - Refactored for Clean Architecture
 * 
 * Pure audio extractor with platform-agnostic schema
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const crypto = require('crypto');

class WhypitExtractor {
  constructor(outputDir = "whypit_data", config = {}) {
    this.outputDir = path.resolve(outputDir);
    this.platform = 'whypit';
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
      console.log("🔧 Playwright browser closed");
    }
  }

  /**
   * Extract content from Whyp.it URL
   * Pure extraction without any external dependencies
   */
  async extract(url) {
    await this.rateLimit();
    
    try {
      console.log(`📥 Processing: ${url}`);
      
      // Check cache first
      const cached = await this.checkCache(url);
      if (cached) {
        console.log(`✅ Using cached extraction for: ${url}`);
        return cached;
      }
      
      await this.page.goto(url, { waitUntil: "networkidle" });

      // Extract metadata from the page
      const pageData = await this.extractPageData();
      
      // Extract track info from URL
      const urlMatch = url.match(/\/tracks\/(\d+)\/(.+)$/);
      if (!urlMatch) {
        throw new Error("Invalid Whyp.it URL format");
      }

      const trackId = urlMatch[1];
      const titleSlug = urlMatch[2];
      const performer = pageData.performer || "unknown";
      const title = pageData.title || titleSlug;

      // Setup directories
      const userDir = path.join(this.outputDir, this.sanitizeFilename(performer));
      const releaseDir = path.join(userDir, this.sanitizeFilename(titleSlug));
      await fs.mkdir(releaseDir, { recursive: true });

      // Capture audio URL
      const audioUrl = await this.captureAudioUrl();
      
      // Download audio
      const filename = `${trackId}_${this.sanitizeFilename(titleSlug)}.mp3`;
      const audioFilePath = path.join(releaseDir, filename);
      
      await this.downloadFile(audioUrl, audioFilePath);
      
      // Calculate checksum
      const checksum = await this.calculateChecksum(audioFilePath);
      
      // Get file stats
      const stats = await fs.stat(audioFilePath);
      
      // Save HTML backup
      const htmlPath = await this.saveHtmlBackup(releaseDir, filename);
      
      // Build result in platform-agnostic schema
      const result = {
        audio: {
          sourceUrl: url,
          downloadUrl: audioUrl,
          filePath: audioFilePath,
          format: 'mp3',
          fileSize: stats.size,
          checksum: {
            sha256: checksum
          }
        },
        metadata: {
          title: title,
          author: performer,
          description: pageData.description || '',
          tags: pageData.tags || [],
          duration: null, // Whyp.it doesn't provide duration before playing
          platform: {
            name: 'whypit',
            url: 'https://whyp.it'
          }
        },
        platformData: {
          trackId: trackId,
          titleSlug: titleSlug,
          extractedAt: new Date().toISOString()
        },
        backupFiles: {
          html: htmlPath
        }
      };
      
      // Save metadata
      const metadataPath = path.join(releaseDir, `${filename.replace('.mp3', '')}.json`);
      await fs.writeFile(metadataPath, JSON.stringify(result, null, 2));
      result.backupFiles.metadata = metadataPath;
      
      // Create completion marker
      await this.createCompletionMarker(releaseDir, result);
      
      console.log(`✅ Successfully extracted: ${title} by ${performer}`);
      return result;

    } catch (error) {
      console.error(`❌ Failed to extract ${url}:`, error.message);
      throw error;
    }
  }

  async checkCache(url) {
    try {
      const urlMatch = url.match(/\/tracks\/(\d+)\/(.+)$/);
      if (!urlMatch) return null;
      
      const [, trackId, titleSlug] = urlMatch;
      
      // Try to find existing data in any performer directory
      const files = await fs.readdir(this.outputDir);
      
      for (const file of files) {
        const filePath = path.join(this.outputDir, file);
        const stat = await fs.stat(filePath);
        
        if (stat.isDirectory()) {
          const releaseDir = path.join(filePath, this.sanitizeFilename(titleSlug));
          const markerFile = path.join(releaseDir, '.extracted');
          
          try {
            await fs.access(markerFile);
            
            // Found cached extraction
            const metadataFiles = await fs.readdir(releaseDir);
            const jsonFile = metadataFiles.find(f => f.endsWith('.json') && f !== '.extracted');
            
            if (jsonFile) {
              const cached = JSON.parse(await fs.readFile(path.join(releaseDir, jsonFile), 'utf8'));
              return cached;
            }
          } catch (e) {
            // Not in this directory
          }
        }
      }
    } catch (e) {
      // Error checking cache
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

  async extractPageData() {
    return await this.page.evaluate(() => {
      // Extract title
      const titleElement = document.querySelector("h1");
      const title = titleElement ? titleElement.textContent.trim() : null;

      // Extract performer
      const userLinkElement = document.querySelector('a[href*="/users/"]');
      let performer = null;
      if (userLinkElement) {
        const performerElement = userLinkElement.querySelector('div:first-child div:first-child');
        if (performerElement) {
          const fullText = performerElement.textContent.trim();
          performer = fullText.split('\n')[0].trim();
        }
      }

      // Extract description and tags
      const metaDescriptionElement = document.querySelector('meta[name="description"]');
      let description = null;
      let tags = [];
      
      if (metaDescriptionElement) {
        description = metaDescriptionElement.getAttribute('content');
        if (description) {
          description = description.trim();
          const tagMatches = description.match(/\[([^\]]+?)\]/g);
          if (tagMatches) {
            tags = tagMatches
              .map(tag => tag.replace(/[\[\]]/g, "").trim())
              .filter(tag => tag.length > 0);
          }
        }
      }

      return {
        title: title,
        performer: performer,
        description: description,
        tags: tags
      };
    });
  }

  async captureAudioUrl() {
    const audioUrls = [];
    
    // Set up network listener
    this.page.on('response', async (response) => {
      const url = response.url();
      if (url.includes('cdn.whyp.it') && url.includes('.mp3') && url.includes('token=')) {
        audioUrls.push(url);
        console.log(`🎵 Found audio URL: ${url}`);
      }
    });

    // Click play button
    console.log("🎯 Looking for play button...");
    
    const playButtonClicked = await this.page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      for (const button of buttons) {
        const hasPlayIcon = button.innerHTML.includes('play') || 
                           button.querySelector('svg path[d*="8,5.14V19.14L19,12.14L8,5.14Z"]') ||
                           button.querySelector('path[d*="play"]');
        
        if (hasPlayIcon || button.getAttribute('aria-label')?.includes('play')) {
          button.click();
          return true;
        }
      }
      
      const audioPlayerButtons = document.querySelectorAll('button[class*="relative"], button[class*="cursor-pointer"]');
      if (audioPlayerButtons.length > 0) {
        audioPlayerButtons[0].click();
        return true;
      }
      
      return false;
    });

    if (!playButtonClicked) {
      throw new Error("Could not find or click play button");
    }

    console.log("▶️ Play button clicked, waiting for audio URL...");

    // Wait for audio URL
    let waitTime = 0;
    const maxWaitTime = 10000;
    while (audioUrls.length === 0 && waitTime < maxWaitTime) {
      await new Promise(resolve => setTimeout(resolve, 500));
      waitTime += 500;
    }

    if (audioUrls.length === 0) {
      throw new Error("No audio URL found in network requests");
    }

    return audioUrls[0];
  }

  async downloadFile(url, filePath, maxRetries = 5) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`📥 Download attempt ${attempt}/${maxRetries}...`);
        const response = await fetch(url, {
          headers: {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const buffer = await response.arrayBuffer();
        await fs.writeFile(filePath, Buffer.from(buffer));
        console.log("✅ Audio download completed successfully");
        return true;
      } catch (error) {
        console.log(`❌ Download attempt ${attempt}/${maxRetries} failed: ${error.message}`);
        if (attempt < maxRetries) {
          const waitTime = 5000 * attempt;
          console.log(`⏱️ Waiting ${waitTime / 1000} seconds before retry...`);
          await new Promise((resolve) => setTimeout(resolve, waitTime));
        } else {
          throw error;
        }
      }
    }
  }

  async saveHtmlBackup(releaseDir, baseFilename) {
    const htmlContent = await this.page.content();
    const htmlPath = path.join(releaseDir, `${baseFilename.replace('.mp3', '')}.html`);
    await fs.writeFile(htmlPath, htmlContent);
    return htmlPath;
  }

  async calculateChecksum(filePath) {
    const fileBuffer = await fs.readFile(filePath);
    const hashSum = crypto.createHash('sha256');
    hashSum.update(fileBuffer);
    return hashSum.digest('hex');
  }

  sanitizeFilename(name) {
    return name.replace(/[^A-Za-z0-9 \-_]/g, "");
  }

  async rateLimit() {
    const currentTime = Date.now();
    const timeSinceLastRequest = currentTime - this.lastRequestTime;

    if (timeSinceLastRequest < this.requestDelay) {
      const sleepTime = this.requestDelay - timeSinceLastRequest;
      console.log(`⏱️ Rate limiting: waiting ${sleepTime}ms...`);
      await new Promise((resolve) => setTimeout(resolve, sleepTime));
    }

    this.lastRequestTime = Date.now();
  }
}

module.exports = WhypitExtractor;

// CLI Interface
if (require.main === module) {
  const { Command } = require("commander");
  
  const program = new Command();
  program
    .name("whypit-extractor")
    .description("Extract audio content from Whyp.it - pure extraction with platform-agnostic schema")
    .version("2.0.0");

  program
    .argument("[urls...]", "Whyp.it URLs to extract")
    .option("-o, --output <dir>", "Output directory", "whypit_data")
    .option("-f, --url-file <file>", "File containing URLs (one per line)")
    .action(async (urls, options) => {
      const extractor = new WhypitExtractor(options.output);
      
      try {
        // Get URLs from file if specified
        if (options.urlFile) {
          const content = await fs.readFile(options.urlFile, 'utf8');
          urls = content
            .split('\n')
            .map(line => line.trim())
            .filter(line => line && !line.startsWith('#'));
          console.log(`📂 Loaded ${urls.length} URLs from ${options.urlFile}`);
        }

        if (!urls || urls.length === 0) {
          console.error("❌ No URLs provided");
          process.exit(1);
        }

        await extractor.setupPlaywright();
        
        const results = [];
        for (let i = 0; i < urls.length; i++) {
          const url = urls[i];
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
        
        console.log(`\n📊 Summary:`);
        console.log(`✅ Successful: ${successful}`);
        console.log(`❌ Failed: ${failed}`);
        
      } catch (error) {
        console.error("❌ Fatal error:", error.message);
        process.exit(1);
      } finally {
        await extractor.closeBrowser();
      }
    });

  program.parse();
}