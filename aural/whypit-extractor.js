#!/usr/bin/env node

/**
 * Whyp.it Data Extractor - Node.js Version
 *
 * This script extracts audio files and metadata from Whyp.it using Playwright.
 * It clicks the play button, captures audio URLs from network requests, and downloads files.
 *
 * Requirements:
 * 1. Install dependencies: npm install
 * 2. Install browser: npm run install-playwright
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const { Command } = require("commander");

class WhypitExtractor {
  constructor(outputDir = "whypit_data") {
    this.outputDir = path.resolve(outputDir);
    this.requestDelay = 2000; // Milliseconds between requests
    this.lastRequestTime = 0;

    // Playwright setup
    this.browser = null;
    this.page = null;
    this.audioUrl = null;
  }

  async setupPlaywright() {
    try {
      console.log("🚀 Starting Playwright browser...");
      this.browser = await chromium.launch({ headless: true });
      this.page = await this.browser.newPage();

      // Set user agent
      await this.page.setExtraHTTPHeaders({
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36",
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
      console.log("🔧 Playwright browser closed");
    }
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

  cleanFilename(name) {
    return name.replace(/[^A-Za-z0-9 \-_]/g, "");
  }

  async downloadFile(url, filename, maxRetries = 5) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`📥 Download attempt ${attempt}/${maxRetries}...`);
        const response = await fetch(url, {
          headers: {
            "User-Agent":
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36",
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const buffer = await response.arrayBuffer();
        await fs.writeFile(filename, Buffer.from(buffer));
        console.log("✅ Audio download completed successfully");
        return true;
      } catch (error) {
        console.log(
          `❌ Download attempt ${attempt}/${maxRetries} failed: ${error.message}`
        );
        if (attempt < maxRetries) {
          const waitTime = 5000 * attempt;
          console.log(`⏱️ Waiting ${waitTime / 1000} seconds before retry...`);
          await new Promise((resolve) => setTimeout(resolve, waitTime));
        }
      }
    }
    return false;
  }

  extractMetadata(whypitUrl, title, description, author, tags = []) {
    return {
      title: title,
      author: author,
      description: description || null,
      tags: tags,
      url: whypitUrl,
      extracted_at: new Date().toISOString(),
    };
  }

  async extractWhypit(whypitUrl) {
    try {
      console.log(`🌐 Navigating to: ${whypitUrl}`);
      await this.rateLimit();
      await this.page.goto(whypitUrl, { waitUntil: "networkidle" });

      // Extract metadata from the page
      const pageData = await this.page.evaluate(() => {
        // Extract title from h1 element
        const titleElement = document.querySelector("h1");
        const title = titleElement ? titleElement.textContent.trim() : null;

        // Extract performer from the user link
        const userLinkElement = document.querySelector('a[href*="/users/"]');
        let performer = null;
        if (userLinkElement) {
          const performerElement = userLinkElement.querySelector('div:first-child div:first-child');
          if (performerElement) {
            const fullText = performerElement.textContent.trim();
            // Split by newlines and take only the first part (performer name)
            performer = fullText.split('\n')[0].trim();
          }
        }

        // Extract description from meta description element
        const metaDescriptionElement = document.querySelector('meta[name="description"]');
        let description = null;
        let tags = [];
        
        if (metaDescriptionElement) {
          description = metaDescriptionElement.getAttribute('content');
          if (description) {
            description = description.trim();
            // Extract tags from square brackets - handle consecutive tags like [3D][CEI]
            const tagMatches = description.match(/\[([^\]]+?)\]/g);
            if (tagMatches) {
              tags = tagMatches
                .map(tag => tag.replace(/[\[\]]/g, "").trim())
                .filter(tag => tag.length > 0 && tag !== ''); // Remove empty tags
              
              console.log(`🏷️ Extracted ${tags.length} tags from description`);
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

      console.log(`📊 Page data extracted:`);
      console.log(`  🎭 Title: ${pageData.title}`);
      console.log(`  👤 Performer: ${pageData.performer}`);
      console.log(`  🏷️ Tags: ${pageData.tags.join(", ")}`);

      // Set up network request listener for audio URLs
      const audioUrls = [];
      this.page.on('response', async (response) => {
        const url = response.url();
        if (url.includes('cdn.whyp.it') && url.includes('.mp3') && url.includes('token=')) {
          audioUrls.push(url);
          console.log(`🎵 Found audio URL: ${url}`);
        }
      });

      // Find and click the play button
      console.log("🎯 Looking for play button...");
      
      // Look for the play button - it's typically a button with a play icon
      const playButtonClicked = await this.page.evaluate(() => {
        // Look for buttons that might be play buttons
        const buttons = document.querySelectorAll('button');
        for (const button of buttons) {
          // Check if it has a play icon (triangle or play-related class)
          const hasPlayIcon = button.innerHTML.includes('play') || 
                             button.querySelector('svg path[d*="8,5.14V19.14L19,12.14L8,5.14Z"]') ||
                             button.querySelector('path[d*="play"]');
          
          if (hasPlayIcon || button.getAttribute('aria-label')?.includes('play')) {
            button.click();
            return true;
          }
        }
        
        // Fallback: look for any button in the audio player area
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

      // Wait for audio URL to be captured (up to 10 seconds)
      let waitTime = 0;
      const maxWaitTime = 10000;
      while (audioUrls.length === 0 && waitTime < maxWaitTime) {
        await new Promise(resolve => setTimeout(resolve, 500));
        waitTime += 500;
      }

      if (audioUrls.length === 0) {
        throw new Error("No audio URL found in network requests after clicking play");
      }

      this.audioUrl = audioUrls[0]; // Use the first audio URL found

      // Extract track ID and title for filename
      const urlMatch = whypitUrl.match(/\/tracks\/(\d+)\/(.+)$/);
      if (!urlMatch) {
        throw new Error("Invalid Whyp.it URL format");
      }

      const trackId = urlMatch[1];
      const titleSlug = urlMatch[2];
      const performer = pageData.performer || "unknown";
      const title = pageData.title || titleSlug;

      console.log(`📊 Extracting from Whyp.it:`);
      console.log(`  🎭 Title: ${title}`);
      console.log(`  👤 Performer: ${performer}`);
      console.log(`  🆔 Track ID: ${trackId}`);

      // Create directory structure: whypit_data/<performer>/<release>/
      const userDir = path.join(this.outputDir, this.cleanFilename(performer));
      const releaseDir = path.join(userDir, this.cleanFilename(titleSlug));
      await fs.mkdir(releaseDir, { recursive: true });

      // Use track ID and cleaned title for filename
      const filename = `${trackId}_${this.cleanFilename(titleSlug)}`;

      const dataFilename = path.join(releaseDir, `${filename}.json`);
      const audioFilename = path.join(releaseDir, `${filename}.mp3`);
      const htmlFilename = path.join(releaseDir, `${filename}.html`);

      // Check if files already exist
      const [audioExists, dataExists, htmlExists] = await Promise.all([
        fs
          .access(audioFilename)
          .then(() => true)
          .catch(() => false),
        fs
          .access(dataFilename)
          .then(() => true)
          .catch(() => false),
        fs
          .access(htmlFilename)
          .then(() => true)
          .catch(() => false),
      ]);

      if (audioExists && dataExists && htmlExists) {
        console.log(
          `⏭️ ${filename}.mp3, ${filename}.json, and ${filename}.html already exist! Skipping...`
        );
        return {
          skipped: true,
          title: title,
          author: performer,
        };
      }

      // Extract metadata
      const metadata = this.extractMetadata(
        whypitUrl,
        title,
        pageData.description,
        performer,
        pageData.tags
      );
      metadata.audio_url = this.audioUrl;
      metadata.track_id = trackId;

      // Save metadata
      await fs.writeFile(
        dataFilename,
        JSON.stringify(metadata, null, 2),
        "utf8"
      );
      console.log(`💾 Metadata saved to: ${filename}.json`);

      // Save HTML backup
      const pageSource = await this.page.content();
      await fs.writeFile(htmlFilename, pageSource, "utf8");
      console.log(`💾 HTML backup saved to: ${filename}.html`);

      // Download audio file
      console.log(`📥 Downloading audio to: ${filename}.mp3`);
      const success = await this.downloadFile(this.audioUrl, audioFilename);

      if (success) {
        console.log(`✅ Successfully extracted: ${title} by ${performer}`);
        return {
          success: true,
          title: title,
          author: performer,
          metadata: metadata,
        };
      } else {
        console.error("❌ Failed to download audio file after maximum retries");
        // Clean up metadata and HTML files if audio download failed
        await Promise.allSettled([
          fs.unlink(dataFilename),
          fs.unlink(htmlFilename),
        ]);
        return {
          success: false,
          title: title,
          author: performer,
          error: "Audio download failed",
        };
      }
    } catch (error) {
      console.error(`❌ Error processing Whyp.it URL: ${error.message}`);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  async ensureOutputDir() {
    try {
      await fs.mkdir(this.outputDir, { recursive: true });
    } catch (error) {
      // Directory might already exist, ignore error
    }
  }

  async extractFromUrls(urls) {
    console.log(`🚀 Starting Whyp.it extraction for ${urls.length} URLs...`);

    const results = [];
    const failedUrls = [];

    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      console.log(`\n📥 Processing audio ${i + 1}/${urls.length}: ${url}`);

      const result = await this.extractWhypit(url);
      results.push(result);

      if (!result.success && !result.skipped) {
        failedUrls.push({ url, error: result.error });
      }
    }

    const successful = results.filter((r) => r.success).length;
    const skipped = results.filter((r) => r.skipped).length;
    const failed = results.filter((r) => !r.success && !r.skipped).length;

    console.log(`\n📊 Extraction Summary:`);
    console.log(`✅ Successfully processed: ${successful}`);
    console.log(`⏭️ Skipped (already exist): ${skipped}`);
    console.log(`❌ Failed: ${failed}`);

    // Save failed URLs if any
    if (failedUrls.length > 0) {
      const timestamp = new Date()
        .toISOString()
        .replace(/[:.]/g, "-")
        .split("T")[0];
      const failedFilename = `failed_whypit_urls_${timestamp}.json`;
      const failedFilepath = path.join(this.outputDir, failedFilename);
      await fs.writeFile(
        failedFilepath,
        JSON.stringify(failedUrls, null, 2),
        "utf8"
      );
      console.log(`📝 Failed URLs saved to: ${failedFilename}`);
    }

    return results;
  }
}

async function main() {
  const program = new Command();

  program
    .name("whypit-extractor")
    .description("Extract audio files and metadata from Whyp.it")
    .version("1.0.0")
    .argument("[urls...]", "Whyp.it URLs to extract")
    .option("-o, --output <dir>", "Output directory", "whypit_data")
    .option(
      "-d, --delay <number>",
      "Delay between requests in milliseconds",
      parseInt,
      2000
    )
    .option("-f, --url-file <file>", "File containing URLs (one per line)")
    .parse();

  const options = program.opts();
  let urls = program.args;

  try {
    // Get URLs from file if specified
    if (options.urlFile) {
      const urlFile = path.resolve(options.urlFile);
      try {
        const fileContent = await fs.readFile(urlFile, "utf8");
        urls = fileContent
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line && !line.startsWith("#"));
        console.log(`📂 Loaded ${urls.length} URLs from ${options.urlFile}`);
      } catch (error) {
        console.error(`❌ URL file not found: ${options.urlFile}`);
        process.exit(1);
      }
    }

    if (!urls || urls.length === 0) {
      console.error("❌ No URLs provided");
      console.log("Usage: node whypit-extractor.js <whypit-url>");
      console.log(
        "Example: node whypit-extractor.js https://whyp.it/tracks/299350/shy-ghost-girl-possesses-you-to-feel-pleasure-again"
      );
      process.exit(1);
    }

    // Validate URLs
    const invalidUrls = urls.filter((url) => !url.includes("whyp.it"));
    if (invalidUrls.length > 0) {
      console.error("❌ Invalid Whyp.it URLs found:");
      invalidUrls.forEach((url) => console.error(`  ${url}`));
      process.exit(1);
    }

    // Initialize extractor
    const extractor = new WhypitExtractor(options.output);
    extractor.requestDelay = options.delay;

    await extractor.ensureOutputDir();
    await extractor.setupPlaywright();

    // Extract audio files
    const results = await extractor.extractFromUrls(urls);

    const successful = results.filter((r) => r.success).length;
    console.log(`\n🎉 Extraction complete!`);
    console.log(`📁 Results saved to: ${extractor.outputDir}`);
    console.log(`📊 Successfully processed ${successful} audio files`);

    // Close browser
    await extractor.closeBrowser();
  } catch (error) {
    if (error.name === "CommanderError") {
      // Commander error, already handled
      process.exit(1);
    }

    console.error(`\n❌ Error: ${error.message}`);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on("SIGINT", () => {
  console.log("\n⏹️ Extraction interrupted by user");
  process.exit(0);
});

if (require.main === module) {
  main().catch((error) => {
    console.error("❌ Unhandled error:", error);
    process.exit(1);
  });
}

module.exports = { WhypitExtractor };