/**
 * Whyp.it Extractor
 *
 * Pure audio extractor - downloads directly to target path provided by caller.
 * Returns platform-agnostic schema.
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const crypto = require('crypto');

class WhypitExtractor {
  constructor(config = {}) {
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
   * @param {string} url - Whyp.it URL to extract
   * @param {object} targetPath - Target paths for output files
   * @param {string} targetPath.dir - Directory to save files
   * @param {string} targetPath.basename - Base filename (without extension)
   */
  async extract(url, targetPath) {
    await this.rateLimit();

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

      // Capture audio URL
      const audioUrl = await this.captureAudioUrl();

      // Download audio
      const audioFilePath = path.join(dir, `${basename}.mp3`);
      await this.downloadFile(audioUrl, audioFilePath);

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
          duration: null,
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
          html: htmlPath,
          metadata: jsonPath
        }
      };

      // Save metadata (serves as completion marker)
      await fs.writeFile(jsonPath, JSON.stringify(result, null, 2));

      console.log(`✅ Successfully extracted: ${title} by ${performer}`);
      return result;

    } catch (error) {
      console.error(`❌ Failed to extract ${url}:`, error.message);
      throw error;
    }
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