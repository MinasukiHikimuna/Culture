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
      alternativeLinks: /\[[^\]]*audio[^\]]*\]\(([^)]+)\)/gi
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
  extractScriptInfo(content) {
    const result = {
      url: null,
      author: null,
      fillType: 'unknown'
    };

    // Check for private fill first (highest priority)
    const privateMatch = content.match(this.scriptPatterns.privatePattern) || 
                         content.match(this.scriptPatterns.scriptWrittenPattern);
    if (privateMatch) {
      result.author = privateMatch[1];
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
   * Extract alternative audio versions
   */
  extractAlternatives(content) {
    const alternatives = [];
    
    // Main audio
    const mainMatch = content.match(this.audioPatterns.mainAudio);
    if (mainMatch) {
      alternatives.push({
        type: 'main',
        url: mainMatch[1],
        description: 'Main audio'
      });
    }

    // Bloopers
    const bloopersMatch = content.match(this.audioPatterns.bloopers);
    if (bloopersMatch) {
      alternatives.push({
        type: 'bloopers',
        url: bloopersMatch[1], 
        description: 'Bloopers'
      });
    }

    // Other alternative audio links
    const altMatches = content.matchAll(this.audioPatterns.alternativeLinks);
    for (const match of altMatches) {
      // Skip if already captured as main or bloopers
      if (!alternatives.some(alt => alt.url === match[1])) {
        alternatives.push({
          type: 'alternative',
          url: match[1],
          description: 'Alternative version'
        });
      }
    }

    return alternatives;
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
    const { title, selftext, author } = postData.reddit_data;
    
    // Extract structured information
    const collaborators = this.extractCollaborators(title, selftext);
    const scriptInfo = this.extractScriptInfo(selftext);
    const alternatives = this.extractAlternatives(selftext);
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
      alternatives: {
        hasAlternatives: alternatives.length > 1,
        versions: alternatives.map(alt => alt.description),
        audioLinks: alternatives
      },
      series: seriesInfo,
      script: scriptInfo,
      preprocessing_metadata: {
        patterns_found: {
          collaborators: collaborators.length > 0,
          script_attribution: scriptInfo.author !== author,
          alternatives: alternatives.length > 1,
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