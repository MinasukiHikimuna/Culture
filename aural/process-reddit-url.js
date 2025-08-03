#!/usr/bin/env node

/**
 * Process Reddit URL - Complete End-to-End Workflow
 * 
 * Takes a Reddit URL as input and:
 * 1. Fetches the Reddit post
 * 2. Analyzes it with LLM
 * 3. Extracts all audio files
 * 4. Creates a complete release
 */

const { execSync } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const { ReleaseOrchestrator } = require('./release-orchestrator');

class RedditProcessor {
  constructor(config = {}) {
    this.outputDir = config.outputDir || 'data';
    this.tempDir = path.join(this.outputDir, '.temp');
    this.orchestrator = new ReleaseOrchestrator({
      dataDir: this.outputDir,
      cacheEnabled: true,
      validateExtractions: true
    });
  }

  /**
   * Process a Reddit URL through the complete pipeline
   */
  async processRedditUrl(redditUrl) {
    console.log('🚀 Processing Reddit URL:', redditUrl);
    console.log('=' .repeat(60));
    
    try {
      // Ensure temp directory exists
      await fs.mkdir(this.tempDir, { recursive: true });
      
      // Step 1: Analyze Reddit post
      console.log('\n📝 Step 1: Analyzing Reddit post...');
      const analysis = await this.analyzeRedditPost(redditUrl);
      console.log(`✅ Analysis complete: ${analysis.metadata.title}`);
      
      // Step 2: Extract Reddit post data
      console.log('\n📊 Step 2: Extracting post metadata...');
      const redditPost = this.extractRedditData(analysis);
      console.log(`✅ Found ${analysis.audio_versions?.length || 0} audio version(s)`);
      
      // Step 3: Process into release
      console.log('\n🎵 Step 3: Extracting audio files...');
      const release = await this.orchestrator.processPost(redditPost, analysis);
      
      // Step 4: Generate summary
      console.log('\n📋 Step 4: Generating summary...');
      const summary = await this.generateSummary(release, redditUrl);
      
      // Cleanup temp directory
      try {
        await fs.rm(this.tempDir, { recursive: true });
      } catch (e) {
        // Ignore cleanup errors
      }
      
      return {
        success: true,
        release,
        summary
      };
      
    } catch (error) {
      console.error('\n❌ Processing failed:', error.message);
      throw error;
    }
  }

  /**
   * Analyze Reddit post using the existing analyze-reddit-post.js
   */
  async analyzeRedditPost(redditUrl) {
    const analysisOutput = path.join(this.tempDir, 'analysis.json');
    
    try {
      // Run the Reddit post analyzer
      const command = `node analyze-reddit-post.js "${redditUrl}" --output "${analysisOutput}"`;
      console.log('  Running:', command);
      
      const result = execSync(command, {
        encoding: 'utf8',
        stdio: 'pipe',
        cwd: __dirname
      });
      
      // Read the analysis result
      const analysisData = await fs.readFile(analysisOutput, 'utf8');
      return JSON.parse(analysisData);
      
    } catch (error) {
      // If analyze-reddit-post.js doesn't exist or fails, create a basic analysis
      console.warn('⚠️  Could not run analyze-reddit-post.js, using basic extraction');
      return await this.basicRedditAnalysis(redditUrl);
    }
  }

  /**
   * Basic Reddit analysis fallback
   */
  async basicRedditAnalysis(redditUrl) {
    // Extract post ID from URL
    const postIdMatch = redditUrl.match(/comments\/([a-z0-9]+)/);
    if (!postIdMatch) {
      throw new Error('Invalid Reddit URL format');
    }
    
    const postId = postIdMatch[1];
    
    // First, check if we have local Reddit data
    const localDataPaths = [
      path.join('reddit_data', '*', `${postId}_*.json`),
      path.join('data', 'reddit', '*', `${postId}_*.json`),
      path.join('H:', 'Git', 'gwasi-extractor', 'reddit_data', '*', `${postId}_*.json`)
    ];
    
    let post = null;
    
    for (const pattern of localDataPaths) {
      try {
        const glob = require('glob');
        const files = glob.sync(pattern);
        if (files.length > 0) {
          console.log('  Found local Reddit data:', files[0]);
          const localData = JSON.parse(await fs.readFile(files[0], 'utf8'));
          post = localData.reddit_data || localData;
          break;
        }
      } catch (e) {
        // Continue trying other paths
      }
    }
    
    // If no local data, try Reddit API
    if (!post) {
      const jsonUrl = redditUrl.replace(/\/$/, '') + '.json';
      console.log('  Fetching:', jsonUrl);
      
      const response = await fetch(jsonUrl, {
        headers: {
          'User-Agent': 'GWASIExtractor/1.0'
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch Reddit post: ${response.status}`);
      }
      
      const data = await response.json();
      post = data[0].data.children[0].data;
    }
    
    // Extract audio URLs from post content
    const content = post.selftext || '';
    const audioUrls = this.extractAudioUrls(content);
    
    // Build analysis structure
    return {
      metadata: {
        post_id: post.id,
        title: post.title,
        username: post.author,
        created_utc: new Date(post.created_utc * 1000).toISOString(),
        url: redditUrl
      },
      content: {
        title: post.title,
        selftext: content
      },
      audio_versions: audioUrls.length > 0 ? [{
        version_name: 'Main',
        urls: audioUrls.map(url => ({
          url: url,
          platform: this.detectPlatform(url)
        }))
      }] : [],
      tags: this.extractTags(post.title + ' ' + content)
    };
  }

  /**
   * Extract audio URLs from text
   */
  extractAudioUrls(text) {
    const urls = [];
    const patterns = [
      /https?:\/\/(?:www\.)?soundgasm\.net\/u\/[^\s\]\)]+/gi,
      /https?:\/\/(?:www\.)?whyp\.it\/tracks\/[^\s\]\)]+/gi,
      /https?:\/\/(?:www\.)?hotaudio\.net\/u\/[^\s\]\)]+/gi
    ];
    
    for (const pattern of patterns) {
      const matches = text.match(pattern) || [];
      // Clean up URLs that might have trailing parentheses
      const cleanedUrls = matches.map(url => {
        // Remove trailing ) if it's not part of the URL structure
        if (url.endsWith(')') && !url.includes('(')) {
          return url.slice(0, -1);
        }
        return url;
      });
      urls.push(...cleanedUrls);
    }
    
    return [...new Set(urls)]; // Remove duplicates
  }

  /**
   * Detect platform from URL
   */
  detectPlatform(url) {
    if (/soundgasm\.net/i.test(url)) return 'Soundgasm';
    if (/whyp\.it/i.test(url)) return 'Whyp.it';
    if (/hotaudio\.net/i.test(url)) return 'HotAudio';
    return 'Unknown';
  }

  /**
   * Extract tags from text
   */
  extractTags(text) {
    const tags = [];
    const tagRegex = /\[([^\]]+)\]/g;
    let match;
    
    while ((match = tagRegex.exec(text)) !== null) {
      tags.push(match[1]);
    }
    
    return tags;
  }

  /**
   * Convert analysis to Reddit post format for orchestrator
   */
  extractRedditData(analysis) {
    return {
      id: analysis.metadata.post_id,
      title: analysis.metadata.title,
      author: analysis.metadata.username,
      created_utc: analysis.metadata.created_utc,
      selftext: analysis.content?.selftext || '',
      url: analysis.metadata.url
    };
  }

  /**
   * Generate summary report
   */
  async generateSummary(release, redditUrl) {
    const summary = {
      reddit_url: redditUrl,
      release_id: release.id,
      title: release.title,
      performer: release.primaryPerformer,
      audio_sources: release.audioSources.length,
      platforms: [...new Set(release.audioSources.map(s => s.metadata.platform.name))],
      extracted_files: [],
      timestamp: new Date().toISOString()
    };
    
    // List extracted files
    for (const source of release.audioSources) {
      summary.extracted_files.push({
        platform: source.metadata.platform.name,
        file: source.audio.filePath,
        size: source.audio.fileSize,
        checksum: source.audio.checksum?.sha256
      });
    }
    
    // Save summary
    const summaryPath = path.join(
      this.outputDir,
      'releases',
      release.primaryPerformer,
      release.id,
      'summary.json'
    );
    
    await fs.writeFile(summaryPath, JSON.stringify(summary, null, 2));
    
    // Print summary
    console.log('\n' + '='.repeat(60));
    console.log('📊 EXTRACTION SUMMARY');
    console.log('='.repeat(60));
    console.log(`Release ID: ${release.id}`);
    console.log(`Title: ${release.title}`);
    console.log(`Performer: ${release.primaryPerformer}`);
    console.log(`Audio Sources: ${release.audioSources.length}`);
    console.log(`Platforms: ${summary.platforms.join(', ')}`);
    console.log('\nExtracted Files:');
    
    for (const file of summary.extracted_files) {
      console.log(`  - ${file.platform}: ${file.file}`);
      console.log(`    Size: ${(file.size / 1024 / 1024).toFixed(2)} MB`);
      if (file.checksum) {
        console.log(`    SHA256: ${file.checksum.substring(0, 16)}...`);
      }
    }
    
    console.log(`\n✅ Complete release saved to: ${path.dirname(summaryPath)}`);
    console.log('='.repeat(60));
    
    return summary;
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args[0] === '--help') {
    console.log(`
Process Reddit URL - Complete GWASI Extraction Pipeline

Usage: node process-reddit-url.js <reddit_url> [options]

Arguments:
  reddit_url    Full Reddit post URL (e.g., https://www.reddit.com/r/gonewildaudio/comments/...)

Options:
  --output <dir>    Output directory (default: data)
  --no-cache        Disable caching
  --help            Show this help message

Example:
  node process-reddit-url.js "https://www.reddit.com/r/gonewildaudio/comments/1lxhwbd/f4m_catching_a_shy_touchstarved_girl_masturbating/"

Output Structure:
  data/
  ├── audio/          # Downloaded audio files by platform
  ├── enrichment/     # Reddit post analysis
  └── releases/       # Complete releases with all metadata
`);
    return 0;
  }
  
  const redditUrl = args[0];
  const options = {
    outputDir: 'data'
  };
  
  // Parse options
  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--output' && args[i + 1]) {
      options.outputDir = args[++i];
    } else if (args[i] === '--no-cache') {
      options.cacheEnabled = false;
    }
  }
  
  try {
    const processor = new RedditProcessor(options);
    const result = await processor.processRedditUrl(redditUrl);
    
    if (result.success) {
      console.log('\n✅ Processing completed successfully!');
      return 0;
    } else {
      console.error('\n❌ Processing failed');
      return 1;
    }
    
  } catch (error) {
    console.error('\n❌ Fatal error:', error.message);
    if (error.stack) {
      console.error(error.stack);
    }
    return 1;
  }
}

if (require.main === module) {
  main().then(code => process.exit(code));
}

module.exports = RedditProcessor;