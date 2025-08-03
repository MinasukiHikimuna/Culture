#!/usr/bin/env node

/**
 * HotAudio Indexer - Node.js Version
 *
 * This script discovers and indexes audio releases from HotAudio using Playwright.
 * It crawls user profiles and creates JSON lists of releases for extraction.
 *
 * Requirements:
 * 1. Install dependencies: npm install
 * 2. Install browser: npm run install-playwright
 */

const { chromium } = require("playwright");
const fs = require("fs").promises;
const path = require("path");
const { Command } = require("commander");

class HotAudioIndexer {
  constructor(outputDir = "hotaudio_data") {
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

  async extractHotAudioLinks(page) {
    // Extract all HotAudio links from the current page
    const links = await page.evaluate(() => {
      const hotAudioLinks = [];
      const links = document.querySelectorAll('a[href*="hotaudio.net/u/"]');
      
      links.forEach(link => {
        const href = link.href;
        const match = href.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
        if (match) {
          const [, user, audio] = match;
          const title = link.textContent.trim() || `${user}/${audio}`;
          hotAudioLinks.push({
            id: `${user}/${audio}`,
            url: href,
            title: title,
            user: user,
            audioId: audio
          });
        }
      });
      
      return hotAudioLinks;
    });
    
    return links;
  }

  async indexUserProfile(userUrl, maxDepth = 3) {
    console.log(`🔍 Indexing user profile: ${userUrl}`);
    
    const releases = new Map(); // Use Map to avoid duplicates
    const visited = new Set();
    const storyMap = {
      title: "Root",
      url: userUrl,
      children: []
    };

    await this.crawlPage(userUrl, releases, visited, storyMap, 0, maxDepth);

    return {
      platform: "hotaudio",
      timestamp: new Date().toISOString(),
      user: this.extractUserFromUrl(userUrl),
      totalReleases: releases.size,
      storyMap: storyMap,
      releases: Array.from(releases.values())
    };
  }

  async crawlPage(url, releases, visited, storyMap, depth = 0, maxDepth = 3) {
    if (depth > maxDepth || visited.has(url)) {
      return;
    }

    visited.add(url);
    console.log(`${'  '.repeat(depth)}📄 Crawling: ${url} (depth ${depth})`);

    try {
      await this.rateLimit();
      await this.page.goto(url, { waitUntil: "networkidle" });

      // Extract links for this page
      const links = await this.extractHotAudioLinks(this.page);
      console.log(`${'  '.repeat(depth)}Found ${links.length} HotAudio links on this page`);

      // Add releases to our collection
      links.forEach(link => {
        if (!releases.has(link.id)) {
          releases.set(link.id, {
            ...link,
            discoveredAt: new Date().toISOString(),
            discoveredFrom: url,
            depth: depth
          });
        }
      });

      // Update story map
      if (!storyMap.children) {
        storyMap.children = [];
      }

      // Recursively crawl found links
      for (const link of links) {
        const childNode = {
          title: link.title,
          url: link.url,
          user: link.user,
          audioId: link.audioId
        };
        
        storyMap.children.push(childNode);
        
        if (depth < maxDepth) {
          await this.crawlPage(link.url, releases, visited, childNode, depth + 1, maxDepth);
        }
      }

    } catch (error) {
      console.error(`${'  '.repeat(depth)}❌ Error crawling ${url}:`, error.message);
    }
  }

  extractUserFromUrl(url) {
    const match = url.match(/hotaudio\.net\/u\/([^\/]+)/);
    return match ? match[1] : 'unknown';
  }

  async saveIndex(indexData, outputFile) {
    await fs.mkdir(path.dirname(outputFile), { recursive: true });
    await fs.writeFile(outputFile, JSON.stringify(indexData, null, 2));
    console.log(`📋 Index saved to: ${outputFile}`);
    console.log(`📊 Total releases found: ${indexData.totalReleases}`);
  }

  async saveStoryMap(indexData, outputFile) {
    const mapFile = outputFile.replace('.json', '.story-map.txt');
    let content = '';
    
    function buildMapContent(node, depth = 0) {
      const indent = '  '.repeat(depth);
      content += `${indent}${node.title}: ${node.url}\n`;
      
      if (node.children && node.children.length > 0) {
        node.children.forEach(child => {
          buildMapContent(child, depth + 1);
        });
      }
    }
    
    buildMapContent(indexData.storyMap);
    await fs.writeFile(mapFile, content);
    console.log(`🗺️  Story map saved to: ${mapFile}`);
  }
}

// CLI Setup
const program = new Command();

program
  .name("hotaudio-indexer")
  .description("Index HotAudio releases for extraction")
  .version("1.0.0");

program
  .option("-u, --user <username>", "HotAudio username to index")
  .option("-d, --depth <number>", "Maximum crawl depth", "3")
  .option("-o, --output <directory>", "Output directory", "hotaudio_data")
  .parse();

const options = program.opts();

async function main() {
  if (!options.user) {
    console.error("❌ Please provide a username with -u or --user");
    process.exit(1);
  }

  const indexer = new HotAudioIndexer(options.output);
  
  try {
    await indexer.setupPlaywright();
    
    const userUrl = `https://hotaudio.net/u/${options.user}`;
    const indexData = await indexer.indexUserProfile(userUrl, parseInt(options.depth));
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
    const outputFile = path.join(options.output, `${options.user}_index_${timestamp}.json`);
    
    await indexer.saveIndex(indexData, outputFile);
    await indexer.saveStoryMap(indexData, outputFile);
    
    console.log("✅ Indexing completed successfully!");
    
  } catch (error) {
    console.error("❌ Indexing failed:", error.message);
    process.exit(1);
  } finally {
    await indexer.closeBrowser();
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error("💥 Unexpected error:", error);
    process.exit(1);
  });
}

module.exports = { HotAudioIndexer };