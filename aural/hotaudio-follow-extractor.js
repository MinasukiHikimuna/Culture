#!/usr/bin/env node

/**
 * HotAudio Follow Extractor
 * 
 * Advanced version that integrates with the existing extractor architecture
 * and can download the actual audio files while following the story tree.
 * 
 * This extractor is specifically designed for Choose Your Own Adventure
 * type audios where the story branches based on user choices.
 */

const playwright = require('playwright');
const path = require('path');
const fs = require('fs').promises;
const crypto = require('crypto');

// Import shared utilities if available
let transformationUtils;
try {
  transformationUtils = require('./transformation-utils.js');
} catch (e) {
  // Transformation utils not available, we'll implement basic versions
}

class HotAudioFollowExtractor {
  constructor(options = {}) {
    this.outputDir = options.outputDir || './data/audio/hotaudio';
    this.enrichmentDir = options.enrichmentDir || './data/enrichment/hotaudio';
    this.downloadAudio = options.downloadAudio !== false;
    this.headless = options.headless !== false;
    this.maxDepth = options.maxDepth || 10;
    this.browser = null;
    this.context = null;
  }

  /**
   * Initialize the browser
   */
  async initialize() {
    console.log('Initializing browser...');
    this.browser = await playwright.chromium.launch({
      headless: this.headless,
      args: ['--disable-blink-features=AutomationControlled']
    });
    
    this.context = await this.browser.newContext({
      viewport: { width: 1280, height: 720 }
    });
  }

  /**
   * Clean up resources
   */
  async cleanup() {
    if (this.browser) {
      await this.browser.close();
    }
  }

  /**
   * Extract all HotAudio links from a page
   */
  async extractHotAudioLinks(page) {
    return await page.evaluate(() => {
      const hotAudioLinks = [];
      const seenUrls = new Set();
      
      // Find all links to HotAudio
      const links = document.querySelectorAll('a[href*="hotaudio.net/u/"]');
      
      links.forEach(link => {
        const href = link.href;
        if (seenUrls.has(href)) return;
        
        const match = href.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
        if (match) {
          seenUrls.add(href);
          const [, user, audio] = match;
          
          // Get link context
          const linkText = link.textContent.trim();
          const parentText = link.parentElement?.textContent.trim() || '';
          
          hotAudioLinks.push({
            url: href,
            title: linkText || `${user}/${audio}`,
            user: user,
            audio: audio,
            context: {
              linkText,
              parentText: parentText.substring(0, 200)
            }
          });
        }
      });
      
      return hotAudioLinks;
    });
  }

  /**
   * Extract comprehensive page metadata
   */
  async extractPageMetadata(page, url) {
    const metadata = await page.evaluate((pageUrl) => {
      const data = {
        url: pageUrl,
        extractedAt: new Date().toISOString()
      };
      
      // Title extraction - prefer the main title in postbody
      const titleElement = document.querySelector('#postbody .text-4xl') || 
                          document.querySelector('h1') || 
                          document.querySelector('.title') ||
                          document.querySelector('title');
      if (titleElement) {
        data.title = titleElement.textContent.trim();
      }
      
      // Extract og:description meta tag
      const ogDescription = document.querySelector('meta[property="og:description"]');
      if (ogDescription && ogDescription.content) {
        data.description = ogDescription.content;
      } else {
        // Fallback to other description sources
        const descElement = document.querySelector('.description, [class*="description"], .prose p:first-of-type');
        if (descElement) {
          data.description = descElement.textContent.trim();
        }
      }
      
      // Duration extraction from player-progress-text
      const durationElement = document.querySelector('#player-progress-text');
      if (durationElement) {
        const durationText = durationElement.textContent.trim();
        // Extract the total duration after the slash (e.g., "0:00 / 2:30" -> "2:30")
        const durationMatch = durationText.match(/\d+:\d+\s*\/\s*(\d+):(\d+)/);
        if (durationMatch) {
          const [, minutes, seconds] = durationMatch;
          data.duration = `${minutes}:${seconds}`;
          data.durationSeconds = parseInt(minutes) * 60 + parseInt(seconds);
        }
      } else {
        // Fallback to length tag in metadata
        const lengthTags = document.querySelectorAll('.tagm');
        lengthTags.forEach(tag => {
          const firstSpan = tag.querySelector('span');
          if (firstSpan && firstSpan.textContent.trim() === 'length') {
            const valueSpan = tag.querySelectorAll('span')[2]; // Third span contains the value
            if (valueSpan) {
              data.duration = valueSpan.textContent.trim();
            }
          }
        });
      }
      
      // Extract detailed metadata from postbody
      const postBody = document.querySelector('#postbody');
      if (postBody) {
        // Extract credits (by, script, voice, edit)
        const credits = {};
        const creditElements = postBody.querySelectorAll('.tagm');
        creditElements.forEach(el => {
          const spans = el.querySelectorAll('span');
          if (spans.length >= 2) {
            const key = spans[0].textContent.trim();
            const link = el.querySelector('a');
            const value = link ? link.textContent.trim() : spans[spans.length - 1].textContent.trim();
            
            if (['by', 'script', 'voice', 'edit'].includes(key)) {
              if (!credits[key]) credits[key] = [];
              credits[key].push(value);
            } else if (key === 'length' && !data.duration) {
              data.duration = value;
            } else if (key === 'on') {
              data.publishedDate = value;
            }
          }
        });
        
        if (Object.keys(credits).length > 0) {
          data.credits = credits;
          // Add all voice actors to performers list
          if (credits.voice && credits.voice.length > 0) {
            data.performers = credits.voice;
          } else if (credits.by && credits.by.length > 0) {
            // Fallback to 'by' credit if no voice credits
            data.performers = credits.by;
          }
        }
        
        // Extract tags more intelligently
        const tags = [];
        const tagLinks = postBody.querySelectorAll('a[href^="/t/"] .tag');
        tagLinks.forEach(el => {
          const tag = el.textContent.trim();
          if (tag && !tags.includes(tag)) {
            tags.push(tag);
          }
        });
        if (tags.length > 0) {
          data.tags = tags;
        }
        
        // Extract script link if present
        const scriptLink = postBody.querySelector('a[href*="scriptbin.works"]');
        if (scriptLink) {
          data.scriptUrl = scriptLink.href;
        }
      }
      
      // Extract audio source if available
      const audioElement = document.querySelector('audio source, audio');
      if (audioElement) {
        data.audioSource = audioElement.src || audioElement.querySelector('source')?.src;
      }
      
      return data;
    }, url);
    
    return metadata;
  }

  /**
   * Download audio file if available
   */
  async downloadAudioFile(page, audioData) {
    if (!this.downloadAudio) return null;
    
    try {
      // Wait for audio player to be ready
      await page.waitForSelector('#player-playpause, audio', { timeout: 10000 });
      
      // Try to get the audio source URL
      const audioUrl = await page.evaluate(() => {
        const audio = document.querySelector('audio');
        if (audio && audio.src) return audio.src;
        
        const source = document.querySelector('audio source');
        if (source && source.src) return source.src;
        
        // Check for any data attributes or hidden inputs
        const playerEl = document.querySelector('[data-audio-url], [data-src]');
        if (playerEl) return playerEl.dataset.audioUrl || playerEl.dataset.src;
        
        return null;
      });
      
      if (!audioUrl) {
        console.log('  Could not find audio URL on page');
        return null;
      }
      
      // Create file path
      const fileName = `${audioData.user}_${audioData.audio}.mp3`;
      const filePath = path.join(this.outputDir, audioData.user, fileName);
      await fs.mkdir(path.dirname(filePath), { recursive: true });
      
      // Check if already downloaded
      try {
        await fs.access(filePath);
        console.log('  Audio already downloaded:', fileName);
        return {
          fileName,
          filePath,
          alreadyExists: true
        };
      } catch (e) {
        // File doesn't exist, continue with download
      }
      
      console.log('  Downloading audio:', fileName);
      
      // Download using page context to maintain cookies/auth
      const response = await page.context().request.get(audioUrl);
      const buffer = await response.body();
      await fs.writeFile(filePath, buffer);
      
      console.log('  Downloaded successfully');
      return {
        fileName,
        filePath,
        size: buffer.length,
        url: audioUrl
      };
      
    } catch (error) {
      console.error('  Error downloading audio:', error.message);
      return null;
    }
  }

  /**
   * Follow and extract a story tree starting from a URL
   */
  async followStoryTree(startUrl) {
    const visitedUrls = new Set();
    const page = await this.context.newPage();
    
    try {
      const storyTree = await this.recursiveFollow(page, startUrl, visitedUrls, 0);
      return storyTree;
    } finally {
      await page.close();
    }
  }

  /**
   * Recursively follow links and build story tree
   */
  async recursiveFollow(page, url, visitedUrls, depth) {
    if (visitedUrls.has(url)) {
      return { url, alreadyVisited: true };
    }
    
    if (depth > this.maxDepth) {
      return { url, maxDepthReached: true };
    }
    
    console.log(`${'  '.repeat(depth)}[${depth}] Processing: ${url}`);
    visitedUrls.add(url);
    
    const node = {
      url,
      depth,
      processedAt: new Date().toISOString()
    };
    
    try {
      // Navigate to page
      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(2000); // Wait for dynamic content
      
      // Extract metadata
      const metadata = await this.extractPageMetadata(page, url);
      Object.assign(node, metadata);
      
      // Parse URL for user/audio info
      const urlMatch = url.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
      if (urlMatch) {
        const [, user, audio] = urlMatch;
        node.user = user;
        node.audio = audio;
      }
      
      // Download audio if enabled
      if (this.downloadAudio && node.user && node.audio) {
        const downloadResult = await this.downloadAudioFile(page, node);
        if (downloadResult) {
          node.download = downloadResult;
        }
      }
      
      // Extract linked audios
      const links = await this.extractHotAudioLinks(page);
      console.log(`${'  '.repeat(depth)}  Found ${links.length} HotAudio links`);
      
      // Save page HTML for enrichment data
      if (node.user && node.audio) {
        const htmlPath = path.join(this.enrichmentDir, node.user, `${node.audio}.html`);
        await fs.mkdir(path.dirname(htmlPath), { recursive: true });
        const html = await page.content();
        await fs.writeFile(htmlPath, html);
        node.htmlSaved = true;
      }
      
      // Recursively follow each link
      node.children = [];
      for (const link of links) {
        console.log(`${'  '.repeat(depth + 1)}Following: ${link.title}`);
        const childNode = await this.recursiveFollow(page, link.url, visitedUrls, depth + 1);
        node.children.push({
          ...link,
          ...childNode
        });
      }
      
    } catch (error) {
      console.error(`${'  '.repeat(depth)}  Error:`, error.message);
      node.error = error.message;
    }
    
    return node;
  }

  /**
   * Generate a content hash for the story tree
   */
  generateContentHash(storyTree) {
    const content = JSON.stringify(storyTree, (key, value) => {
      // Exclude volatile fields from hash
      if (['processedAt', 'extractedAt', 'download'].includes(key)) {
        return undefined;
      }
      return value;
    });
    return crypto.createHash('sha256').update(content).digest('hex').substring(0, 12);
  }

  /**
   * Save story tree and metadata
   */
  async saveResults(storyTree, startUrl) {
    const urlMatch = startUrl.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
    if (!urlMatch) return;
    
    const [, user, audio] = urlMatch;
    const outputPath = path.join(this.enrichmentDir, user, audio);
    await fs.mkdir(outputPath, { recursive: true });
    
    // Save full story tree
    const treeFile = path.join(outputPath, 'story-tree.json');
    await fs.writeFile(treeFile, JSON.stringify(storyTree, null, 2));
    console.log(`\nStory tree saved to: ${treeFile}`);
    
    // Generate and save summary
    const summary = this.generateSummary(storyTree);
    const summaryFile = path.join(outputPath, 'story-summary.json');
    await fs.writeFile(summaryFile, JSON.stringify(summary, null, 2));
    
    // Save text visualization
    const textTree = this.generateTextTree(storyTree);
    const textFile = path.join(outputPath, 'story-tree.txt');
    await fs.writeFile(textFile, textTree);
    
    return {
      treeFile,
      summaryFile,
      textFile
    };
  }

  /**
   * Generate a summary of the story tree
   */
  generateSummary(storyTree) {
    const summary = {
      rootUrl: storyTree.url,
      title: storyTree.title,
      user: storyTree.user,
      processedAt: storyTree.processedAt,
      contentHash: this.generateContentHash(storyTree),
      stats: {
        totalNodes: 0,
        totalAudioFiles: 0,
        downloadedFiles: 0,
        totalDurationSeconds: 0,
        maxDepth: 0,
        performers: new Set(),
        tags: new Set()
      },
      audioFiles: []
    };
    
    // Recursive function to collect stats
    function collectStats(node, currentDepth = 0) {
      summary.stats.totalNodes++;
      summary.stats.maxDepth = Math.max(summary.stats.maxDepth, currentDepth);
      
      if (node.audio && !node.alreadyVisited) {
        summary.stats.totalAudioFiles++;
        
        const audioInfo = {
          url: node.url,
          user: node.user,
          audio: node.audio,
          title: node.title,
          duration: node.duration,
          depth: currentDepth
        };
        
        if (node.download) {
          summary.stats.downloadedFiles++;
          audioInfo.downloaded = true;
          audioInfo.filePath = node.download.filePath;
        }
        
        summary.audioFiles.push(audioInfo);
      }
      
      if (node.durationSeconds) {
        summary.stats.totalDurationSeconds += node.durationSeconds;
      }
      
      if (node.performers && Array.isArray(node.performers)) {
        node.performers.forEach(performer => summary.stats.performers.add(performer));
      }
      
      if (node.tags) {
        node.tags.forEach(tag => summary.stats.tags.add(tag));
      }
      
      if (node.children) {
        node.children.forEach(child => collectStats(child, currentDepth + 1));
      }
    }
    
    collectStats(storyTree);
    
    // Convert sets to arrays
    summary.stats.performers = Array.from(summary.stats.performers);
    summary.stats.tags = Array.from(summary.stats.tags);
    
    // Format total duration
    if (summary.stats.totalDurationSeconds > 0) {
      const hours = Math.floor(summary.stats.totalDurationSeconds / 3600);
      const minutes = Math.floor((summary.stats.totalDurationSeconds % 3600) / 60);
      summary.stats.formattedTotalDuration = `${hours}h ${minutes}m`;
    }
    
    return summary;
  }

  /**
   * Generate text representation of story tree
   */
  generateTextTree(node, depth = 0) {
    let text = '';
    const indent = '  '.repeat(depth);
    
    if (depth === 0) {
      text += 'HOTAUDIO STORY TREE\n';
      text += '==================\n\n';
    }
    
    // Node info
    const title = node.title || node.audio || 'Unknown';
    text += `${indent}[${depth}] ${title}\n`;
    text += `${indent}    URL: ${node.url}\n`;
    
    if (node.duration) {
      text += `${indent}    Duration: ${node.duration}\n`;
    }
    
    if (node.performers && node.performers.length > 0) {
      text += `${indent}    Performers: ${node.performers.join(', ')}\n`;
    }
    
    if (node.download) {
      text += `${indent}    Downloaded: ${node.download.fileName}\n`;
    }
    
    if (node.error) {
      text += `${indent}    ERROR: ${node.error}\n`;
    }
    
    if (node.alreadyVisited) {
      text += `${indent}    (Already visited)\n`;
    }
    
    text += '\n';
    
    // Children
    if (node.children && node.children.length > 0) {
      node.children.forEach(child => {
        text += this.generateTextTree(child, depth + 1);
      });
    }
    
    return text;
  }

  /**
   * Main extraction method
   */
  async extract(url, options = {}) {
    Object.assign(this, options);
    
    try {
      await this.initialize();
      
      console.log('Starting HotAudio story tree extraction...');
      console.log('URL:', url);
      console.log('Download audio:', this.downloadAudio);
      console.log('Max depth:', this.maxDepth);
      console.log('');
      
      const storyTree = await this.followStoryTree(url);
      
      const summary = this.generateSummary(storyTree);
      console.log('\n=== EXTRACTION COMPLETE ===');
      console.log(`Total nodes: ${summary.stats.totalNodes}`);
      console.log(`Total audio files: ${summary.stats.totalAudioFiles}`);
      console.log(`Downloaded files: ${summary.stats.downloadedFiles}`);
      console.log(`Max depth reached: ${summary.stats.maxDepth}`);
      if (summary.stats.formattedTotalDuration) {
        console.log(`Total duration: ${summary.stats.formattedTotalDuration}`);
      }
      
      const savedFiles = await this.saveResults(storyTree, url);
      console.log('\nResults saved to:', savedFiles.treeFile);
      
      return {
        storyTree,
        summary,
        savedFiles
      };
      
    } finally {
      await this.cleanup();
    }
  }
}

// CLI interface
if (require.main === module) {
  async function main() {
    const args = process.argv.slice(2);
    let url = null;
    const options = {
      downloadAudio: true,
      headless: true,
      maxDepth: 10
    };
    
    // Parse arguments
    for (let i = 0; i < args.length; i++) {
      const arg = args[i];
      
      if (arg === '--no-download') {
        options.downloadAudio = false;
      } else if (arg === '--show-browser') {
        options.headless = false;
      } else if (arg === '--max-depth' && i + 1 < args.length) {
        options.maxDepth = parseInt(args[++i]);
      } else if (arg === '--output-dir' && i + 1 < args.length) {
        options.outputDir = args[++i];
      } else if (arg === '--enrichment-dir' && i + 1 < args.length) {
        options.enrichmentDir = args[++i];
      } else if (arg.startsWith('http')) {
        url = arg;
      }
    }
    
    if (!url) {
      console.error('Usage: node hotaudio-follow-extractor.js [options] <hotaudio-url>');
      console.error('\nOptions:');
      console.error('  --no-download        Do not download audio files');
      console.error('  --show-browser       Show browser window');
      console.error('  --max-depth <n>      Maximum depth to follow (default: 10)');
      console.error('  --output-dir <dir>   Directory for audio files');
      console.error('  --enrichment-dir <dir> Directory for metadata files');
      console.error('\nExample:');
      console.error('  node hotaudio-follow-extractor.js https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up');
      process.exit(1);
    }
    
    const extractor = new HotAudioFollowExtractor();
    
    try {
      await extractor.extract(url, options);
    } catch (error) {
      console.error('Fatal error:', error);
      process.exit(1);
    }
  }
  
  main();
}

module.exports = HotAudioFollowExtractor;