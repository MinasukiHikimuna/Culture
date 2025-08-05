#!/usr/bin/env node

/**
 * Reddit Post Preprocessor
 * 
 * Extracts structured information from Reddit posts using reliable regex patterns
 * before sending to LLM for analysis. This improves accuracy and consistency.
 */

class RedditPostPreprocessor {
  constructor() {
    // Collaboration patterns
    this.collabPatterns = [
      /collab w\/ u\/([a-zA-Z0-9_-]+)/g,
      /collab w\/ u\/([a-zA-Z0-9_-]+) & u\/([a-zA-Z0-9_-]+)/g,
      /& u\/([a-zA-Z0-9_-]+)/g,
      /with u\/([a-zA-Z0-9_-]+)/g,
      /featuring u\/([a-zA-Z0-9_-]+)/g
    ];

    // Script attribution patterns
    this.scriptPatterns = {
      urlPattern: /\[script\]\(([^)]+)\)/i,
      authorPattern: /by u\/([a-zA-Z0-9_-]+)/i,
      privatePattern: /written privately by u\/([a-zA-Z0-9_-]+)/i,
      scriptWrittenPattern: /script was written privately by u\/([a-zA-Z0-9_-]+)/i,
      thanksPattern: /thanks to the lovely and very talented u\/([a-zA-Z0-9_-]+)/i,
      editorPattern: /Edited by u\/([a-zA-Z0-9_-]+)/i,
      originalPatterns: [
        /my own stuff/i,
        /something I came up with/i,
        /trying to write more/i,
        /I wrote/i,
        /my script/i
      ]
    };

    // Audio link patterns
    this.audioPatterns = {
      mainAudio: /\[AUDIO HERE\]\(([^)]+)\)/i,
      bloopers: /\[bloopers[^\]]*\]\(([^)]+)\)/i,
      alternativeLinks: /\[[^\]]*audio[^\]]*\]\(([^)]+)\)/gi,
      soundgasmLinks: /https?:\/\/soundgasm\.net\/u\/[^\/]+\/[^\s)]+/gi,
      whypitLinks: /https?:\/\/whyp\.it\/tracks\/[^\s)]+/gi,
      hotaudioLinks: /https?:\/\/hotaudio\.net\/u\/[^\/]+\/[^\s)]+/gi
    };

    // Platform detection patterns
    this.platformPatterns = {
      soundgasm: /soundgasm\.net/i,
      whypit: /whyp\.it/i,
      hotaudio: /hotaudio\.net/i
    };
  }

  /**
   * Extract collaborators from title and content
   */
  extractCollaborators(title, content) {
    const collaborators = new Set();
    const text = `${title} ${content}`;

    // Extract from "collab w/" patterns
    const collabMatch = text.match(/collab w\/ u\/([a-zA-Z0-9_-]+)(?:\s*&\s*u\/([a-zA-Z0-9_-]+))*/i);
    if (collabMatch) {
      if (collabMatch[1]) collaborators.add(collabMatch[1]);
      if (collabMatch[2]) collaborators.add(collabMatch[2]);
    }

    // Extract additional collaborators from & patterns
    const ampersandMatches = text.matchAll(/&\s*u\/([a-zA-Z0-9_-]+)/g);
    for (const match of ampersandMatches) {
      collaborators.add(match[1]);
    }

    return Array.from(collaborators);
  }

  /**
   * Extract script information
   */
  extractScriptInfo(content, link_flair_text = null) {
    const result = {
      url: null,
      author: null,
      fillType: 'unknown'
    };

    // Check flair first (highest priority)
    if (link_flair_text) {
      if (link_flair_text === 'OC') {
        result.fillType = 'original';
        result.url = null;
        // For OC, the author is the poster (will be set later)
        return result;
      } else if (link_flair_text === 'Script Fill') {
        result.fillType = 'public';
      } else if (link_flair_text === 'Private Script Fill') {
        result.fillType = 'private';
        result.url = null;
      }
    }

    // Check for private fill patterns (overrides flair if explicit)
    const privateMatch = content.match(this.scriptPatterns.privatePattern) || 
                         content.match(this.scriptPatterns.scriptWrittenPattern);
    if (privateMatch) {
      result.author = privateMatch[1];
      result.fillType = 'private';
      result.url = null;
      return result;
    }

    // Check for thanks pattern (often indicates script author)
    const thanksMatch = content.match(this.scriptPatterns.thanksPattern);
    if (thanksMatch) {
      result.author = thanksMatch[1];
      result.fillType = 'private';
      result.url = null;
      return result;
    }

    // Check for original content patterns
    for (const pattern of this.scriptPatterns.originalPatterns) {
      if (pattern.test(content)) {
        result.fillType = 'original';
        result.url = null;
        return result;
      }
    }

    // Check for public script with URL
    const urlMatch = content.match(this.scriptPatterns.urlPattern);
    if (urlMatch) {
      result.url = urlMatch[1];
      result.fillType = 'public';
    }

    // Extract author
    const authorMatch = content.match(this.scriptPatterns.authorPattern);
    if (authorMatch) {
      result.author = authorMatch[1];
    }

    return result;
  }

  /**
   * Detect platform from URL
   */
  detectPlatform(url) {
    for (const [platform, pattern] of Object.entries(this.platformPatterns)) {
      if (pattern.test(url)) {
        return platform.charAt(0).toUpperCase() + platform.slice(1);
      }
    }
    return 'Unknown';
  }

  /**
   * Extract all audio URLs from content
   */
  extractAllAudioUrls(content) {
    const urls = [];
    
    // Extract all soundgasm URLs
    const soundgasmMatches = content.matchAll(this.audioPatterns.soundgasmLinks);
    for (const match of soundgasmMatches) {
      urls.push(match[0]);
    }
    
    // Extract all whyp.it URLs
    const whypitMatches = content.matchAll(this.audioPatterns.whypitLinks);
    for (const match of whypitMatches) {
      urls.push(match[0]);
    }
    
    // Extract all hotaudio URLs
    const hotaudioMatches = content.matchAll(this.audioPatterns.hotaudioLinks);
    for (const match of hotaudioMatches) {
      urls.push(match[0]);
    }
    
    return [...new Set(urls)]; // Remove duplicates
  }

  /**
   * Extract audio versions with URLs and platform detection
   */
  extractAudioVersions(content) {
    const audioVersions = [];
    const allUrls = this.extractAllAudioUrls(content);
    
    if (allUrls.length === 0) {
      return audioVersions;
    }

    // Categorize URLs
    const f4mVersions = [];
    const f4fVersions = [];
    const mainVersions = [];
    const blooperVersions = [];
    
    for (const url of allUrls) {
      const platform = this.detectPlatform(url);
      const category = this.categorizeUrl(content, url);
      
      switch (category) {
        case 'f4m':
          f4mVersions.push({ platform, url });
          break;
        case 'f4f':
          f4fVersions.push({ platform, url });
          break;
        case 'bloopers':
          blooperVersions.push({ platform, url });
          break;
        default:
          mainVersions.push({ platform, url });
          break;
      }
    }

    // Create version objects
    if (f4mVersions.length > 0) {
      audioVersions.push({
        version_name: "F4M Version",
        description: "Version for male listeners",
        urls: f4mVersions
      });
    }
    
    if (f4fVersions.length > 0) {
      audioVersions.push({
        version_name: "F4F Version", 
        description: "Version for female listeners",
        urls: f4fVersions
      });
    }
    
    if (mainVersions.length > 0) {
      audioVersions.unshift({ // Put main audio first
        version_name: "Main Audio",
        description: "Primary audio version",
        urls: mainVersions
      });
    }
    
    if (blooperVersions.length > 0) {
      audioVersions.push({
        version_name: "Bloopers",
        description: "Outtakes and mistakes from recording",
        urls: blooperVersions
      });
    }

    return audioVersions;
  }

  /**
   * Get context around a URL to determine its version type
   */
  getUrlContext(content, url) {
    const urlIndex = content.indexOf(url);
    if (urlIndex === -1) return '';
    
    // Get a smaller, more specific context just around this URL
    const start = Math.max(0, urlIndex - 50);
    const end = Math.min(content.length, urlIndex + url.length + 10);
    return content.substring(start, end);
  }

  /**
   * Improved version detection that looks at text structure
   */
  categorizeUrl(content, url) {
    const context = this.getUrlContext(content, url);
    const lines = content.split('\n');
    
    // Find the line containing this URL
    let urlLine = '';
    let beforeLine = '';
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].includes(url)) {
        urlLine = lines[i];
        beforeLine = i > 0 ? lines[i-1] : '';
        break;
      }
    }
    
    const fullContext = `${beforeLine} ${urlLine}`;
    
    // Check for bloopers first (most specific)
    if (/\[bloopers[^\]]*\]/i.test(fullContext) || /bloopers?/i.test(context)) {
      return 'bloopers';
    }
    
    // Check for main audio indicators
    if (/\[AUDIO HERE\]/i.test(fullContext) || /\[audio\]/i.test(fullContext)) {
      return 'main';
    }
    
    // Check for F4M
    if (fullContext.toLowerCase().includes('f4m') || fullContext.toLowerCase().includes('(f4m)')) {
      return 'f4m';
    }
    
    // Check for F4F  
    if (fullContext.toLowerCase().includes('f4f') || fullContext.toLowerCase().includes('(f4f)')) {
      return 'f4f';
    }
    
    return 'main';
  }

  /**
   * Check for series information
   */
  extractSeriesInfo(title, content) {
    const text = `${title} ${content}`;
    
    const seriesPatterns = [
      /part\s+(\d+)/i,
      /episode\s+(\d+)/i,
      /chapter\s+(\d+)/i,
      /\[part\s+(\d+)\]/i,
      /continued from/i,
      /sequel to/i,
      /prequel to/i
    ];

    for (const pattern of seriesPatterns) {
      const match = text.match(pattern);
      if (match) {
        return {
          isPartOfSeries: true,
          partNumber: match[1] ? parseInt(match[1]) : null,
          hasSequels: /sequel to/i.test(text),
          hasPrequels: /prequel to/i.test(text) || /continued from/i.test(text)
        };
      }
    }

    return {
      isPartOfSeries: false,
      partNumber: null,
      hasSequels: false,
      hasPrequels: false
    };
  }

  /**
   * Main preprocessing function
   */
  preprocess(postData) {
    const { title, selftext, author, link_flair_text } = postData.reddit_data;
    
    // Extract structured information
    const collaborators = this.extractCollaborators(title, selftext);
    const scriptInfo = this.extractScriptInfo(selftext, link_flair_text);
    const audioVersions = this.extractAudioVersions(selftext);
    const seriesInfo = this.extractSeriesInfo(title, selftext);

    // If no explicit script author found, default to poster for original content
    if (!scriptInfo.author && scriptInfo.fillType === 'original') {
      scriptInfo.author = author;
    } else if (!scriptInfo.author && scriptInfo.fillType === 'unknown') {
      scriptInfo.author = author;
      scriptInfo.fillType = 'original'; // Assume original if no clear attribution
    }

    return {
      performers: {
        count: 1 + collaborators.length, // Poster + collaborators
        primary: author,
        additional: collaborators
      },
      audio_versions: audioVersions,
      series: seriesInfo,
      script: scriptInfo,
      preprocessing_metadata: {
        patterns_found: {
          collaborators: collaborators.length > 0,
          script_attribution: scriptInfo.author !== author,
          audio_versions: audioVersions.length > 0,
          multiple_versions: audioVersions.length > 1,
          series_indicators: seriesInfo.isPartOfSeries
        },
        processed_at: new Date().toISOString()
      }
    };
  }
}

// CLI usage
function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log(`
Usage: node preprocess-reddit-post.js <reddit_post.json>

Preprocesses Reddit post data to extract structured information:
- Collaborators and performer count
- Script attribution and fill type  
- Alternative audio versions
- Series information

Output: JSON with extracted structured data
`);
    process.exit(1);
  }

  const inputPath = args[0];
  
  try {
    const fs = require('fs');
    const postData = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
    
    const preprocessor = new RedditPostPreprocessor();
    const result = preprocessor.preprocess(postData);
    
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = RedditPostPreprocessor;