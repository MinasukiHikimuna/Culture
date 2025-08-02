#!/usr/bin/env node

/**
 * Soundgasm Data Extractor - Node.js Version
 *
 * This script extracts audio files and metadata from Soundgasm using Playwright.
 * It downloads audio files, extracts metadata, and saves HTML backups.
 *
 * Requirements:
 * 1. Install dependencies: npm install
 * 2. Install browser: npm run install-playwright
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const { Command } = require("commander");

class SoundgasmExtractor {
  constructor(outputDir = "soundgasm_data") {
    this.outputDir = path.resolve(outputDir);
    this.requestDelay = 2000; // Milliseconds between requests
    this.lastRequestTime = 0;

    // Playwright setup
    this.browser = null;
    this.page = null;
  }

  async setupPlaywright() {
    try {
      console.log("🚀 Starting Playwright browser...");
      this.browser = await chromium.launch({ headless: false });
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

  extractMetadata(soundgasmUrl, detailedTitle, description, author) {
    // Extract tags from description if available
    let tags = [];
    if (description) {
      const tagMatches = description.match(/\[([^\]]+)\]/g);
      if (tagMatches) {
        tags = tagMatches.map((tag) => tag.replace(/[\[\]]/g, "").trim());
      }
    }

    return {
      title: detailedTitle,
      author: author,
      description: description || null,
      tags: tags,
      url: soundgasmUrl,
      extracted_at: new Date().toISOString(),
    };
  }

  async extractSoundgasm(soundgasmUrl) {
    try {
      console.log(`🌐 Navigating to: ${soundgasmUrl}`);
      await this.rateLimit();
      await this.page.goto(soundgasmUrl, { waitUntil: "networkidle" });

      // Extract audio URL from the page
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

      console.log(`🎵 Found audio URL: ${audioUrl}`);

      // Extract metadata from URL
      const urlMatch = soundgasmUrl.match(
        /https?:\/\/(?:www\.)?soundgasm\.net\/u\/([A-Za-z0-9\-_]+)\/([A-Za-z0-9\-_]+)/
      );
      if (!urlMatch) {
        throw new Error("Invalid Soundgasm URL format");
      }

      const author = urlMatch[1];
      const titleFromUrl = urlMatch[2];

      // Extract detailed title and description from page
      const { detailedTitle, description } = await this.page.evaluate(() => {
        const titleElement = document.querySelector(".jp-title");
        const descriptionElement = document.querySelector(".jp-description");

        return {
          detailedTitle: titleElement ? titleElement.textContent.trim() : null,
          description: descriptionElement
            ? descriptionElement.textContent.trim()
            : null,
        };
      });

      // Use detailed title for metadata, but URL slug for filename
      const pageTitle = await this.page.title();
      const title = detailedTitle || pageTitle || titleFromUrl;

      console.log(`📊 Extracting from Soundgasm:`);
      console.log(`  🎭 Title: ${title}`);
      console.log(`  👤 Author: ${author}`);
      console.log(`  🏷️ URL Slug: ${titleFromUrl}`);

      // Create directory structure: soundgasm_data/<user>/
      const userDir = path.join(this.outputDir, author);
      await fs.mkdir(userDir, { recursive: true });

      // Use URL slug for filename (safer for filesystem)
      const filename = titleFromUrl; // Already clean from URL structure

      const dataFilename = path.join(userDir, `${filename}.json`);
      const audioFilename = path.join(userDir, `${filename}.m4a`);
      const htmlFilename = path.join(userDir, `${filename}.html`);

      // Check if files already exist
      const [audioExists, dataExists, htmlExists] = await Promise.all([
        fs.access(audioFilename).then(() => true).catch(() => false),
        fs.access(dataFilename).then(() => true).catch(() => false),
        fs.access(htmlFilename).then(() => true).catch(() => false),
      ]);

      if (audioExists && dataExists && htmlExists) {
        console.log(
          `⏭️ ${filename}.m4a, ${filename}.json, and ${filename}.html already exist! Skipping...`
        );
        return {
          skipped: true,
          title: title,
          author: author,
        };
      }

      // Extract metadata
      const metadata = this.extractMetadata(
        soundgasmUrl,
        title,
        description,
        author
      );
      metadata.audio_url = audioUrl;

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
      console.log(`📥 Downloading audio to: ${filename}.m4a`);
      const success = await this.downloadFile(audioUrl, audioFilename);

      if (success) {
        console.log(
          `✅ Successfully extracted: ${title} by ${author}`
        );
        return {
          success: true,
          title: title,
          author: author,
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
          author: author,
          error: "Audio download failed",
        };
      }
    } catch (error) {
      console.error(`❌ Error processing Soundgasm URL: ${error.message}`);
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
    console.log(`🚀 Starting Soundgasm extraction for ${urls.length} URLs...`);

    const results = [];
    const failedUrls = [];

    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      console.log(`\n📥 Processing audio ${i + 1}/${urls.length}: ${url}`);

      const result = await this.extractSoundgasm(url);
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
      const failedFilename = `failed_soundgasm_urls_${timestamp}.json`;
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
    .name("soundgasm-extractor")
    .description("Extract audio files and metadata from Soundgasm")
    .version("1.0.0")
    .argument("[urls...]", "Soundgasm URLs to extract")
    .option("-o, --output <dir>", "Output directory", "soundgasm_data")
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
      console.log("Usage: node soundgasm-extractor.js <soundgasm-url>");
      console.log(
        "Example: node soundgasm-extractor.js https://soundgasm.net/u/username/audioname"
      );
      process.exit(1);
    }

    // Validate URLs
    const invalidUrls = urls.filter((url) => !url.includes("soundgasm.net"));
    if (invalidUrls.length > 0) {
      console.error("❌ Invalid Soundgasm URLs found:");
      invalidUrls.forEach((url) => console.error(`  ${url}`));
      process.exit(1);
    }

    // Initialize extractor
    const extractor = new SoundgasmExtractor(options.output);
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

module.exports = { SoundgasmExtractor };