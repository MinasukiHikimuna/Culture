#!/usr/bin/env node

/**
 * Analyze, Download, and Import Pipeline
 *
 * Complete workflow script that:
 * 1. Analyzes Reddit posts using analyze-reddit-post.js
 * 2. Downloads audio files using the release orchestrator
 * 3. Imports to Stashapp using stashapp_importer.py
 *
 * Tracks processed posts to avoid duplicate work.
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync, spawn } = require('child_process');
const { ReleaseOrchestrator, Release, AudioSource } = require('./release-orchestrator');

// Tracking file for processed posts
const PROCESSED_FILE = 'data/processed_posts.json';

class AnalyzeDownloadImportPipeline {
  constructor(options = {}) {
    this.analysisDir = options.analysisDir || 'analysis_results';
    this.dataDir = options.dataDir || 'data';
    this.dryRun = options.dryRun || false;
    this.verbose = options.verbose || false;
    this.skipAnalysis = options.skipAnalysis || false;
    this.skipImport = options.skipImport || false;
    this.force = options.force || false;

    // Initialize release orchestrator
    this.releaseOrchestrator = new ReleaseOrchestrator({
      dataDir: this.dataDir,
      validateExtractions: true
    });

    // Processed posts tracking
    this.processedPosts = null;
  }

  /**
   * Load processed posts tracking data
   */
  async loadProcessedPosts() {
    if (this.processedPosts !== null) {
      return this.processedPosts;
    }

    const trackingPath = path.join(this.dataDir, 'processed_posts.json');
    try {
      const content = await fs.readFile(trackingPath, 'utf8');
      this.processedPosts = JSON.parse(content);
    } catch {
      this.processedPosts = {
        posts: {},
        lastUpdated: null
      };
    }
    return this.processedPosts;
  }

  /**
   * Save processed posts tracking data
   */
  async saveProcessedPosts() {
    const trackingPath = path.join(this.dataDir, 'processed_posts.json');
    this.processedPosts.lastUpdated = new Date().toISOString();
    await fs.mkdir(path.dirname(trackingPath), { recursive: true });
    await fs.writeFile(trackingPath, JSON.stringify(this.processedPosts, null, 2));
  }

  /**
   * Check if a post has already been processed
   */
  async isProcessed(postId) {
    await this.loadProcessedPosts();
    return !!this.processedPosts.posts[postId];
  }

  /**
   * Mark a post as processed
   */
  async markProcessed(postId, result) {
    await this.loadProcessedPosts();
    this.processedPosts.posts[postId] = {
      processedAt: new Date().toISOString(),
      releaseId: result.release?.id || null,
      releaseDir: result.releaseDir || null,
      stashSceneId: result.stashSceneId || null,
      audioSourceCount: result.release?.audioSources?.length || 0,
      success: result.success
    };
    await this.saveProcessedPosts();
  }

  /**
   * Get post ID from file path or content
   */
  async getPostId(postFilePath) {
    try {
      const content = await fs.readFile(postFilePath, 'utf8');
      const data = JSON.parse(content);
      return data.reddit_data?.id || path.basename(postFilePath, '.json').split('_')[0];
    } catch {
      return path.basename(postFilePath, '.json').split('_')[0];
    }
  }

  /**
   * Check if a post has content that can be analyzed
   */
  async hasAnalyzableContent(postFilePath) {
    try {
      const content = await fs.readFile(postFilePath, 'utf8');
      const data = JSON.parse(content);
      const selftext = data.reddit_data?.selftext || '';

      // Posts with empty selftext are crossposts or link posts - can't analyze
      if (!selftext.trim()) {
        return { ok: false, reason: 'empty selftext (crosspost or link post)' };
      }

      return { ok: true };
    } catch (error) {
      return { ok: false, reason: error.message };
    }
  }

  /**
   * Analyze a single Reddit post file
   */
  async analyzePost(postFilePath) {
    try {
      // Check if post has analyzable content
      const contentCheck = await this.hasAnalyzableContent(postFilePath);
      if (!contentCheck.ok) {
        return {
          success: false,
          postFile: postFilePath,
          error: contentCheck.reason,
          noContent: true
        };
      }

      await fs.mkdir(this.analysisDir, { recursive: true });

      const postFileName = path.basename(postFilePath, '.json');
      const analysisFileName = `${postFileName}_analysis.json`;
      const analysisFilePath = path.join(this.analysisDir, analysisFileName);

      // Check if analysis already exists
      if (this.skipAnalysis) {
        try {
          await fs.access(analysisFilePath);
          if (this.verbose) {
            console.log(`⏭️  Using existing analysis: ${analysisFilePath}`);
          }
          return {
            success: true,
            postFile: postFilePath,
            analysisFile: analysisFilePath,
            skipped: true
          };
        } catch {
          // Analysis doesn't exist, proceed
        }
      }

      if (this.verbose) {
        console.log(`🔍 Analyzing post: ${postFilePath}`);
      }

      const command = `node analyze-reddit-post.js "${postFilePath}" --output "${analysisFilePath}"`;

      execSync(command, {
        encoding: 'utf8',
        cwd: __dirname,
        stdio: this.verbose ? 'inherit' : 'pipe'
      });

      return {
        success: true,
        postFile: postFilePath,
        analysisFile: analysisFilePath
      };

    } catch (error) {
      console.error(`❌ Analysis failed for ${postFilePath}: ${error.message}`);
      return {
        success: false,
        postFile: postFilePath,
        error: error.message
      };
    }
  }

  /**
   * Process analysis through release orchestrator (download audio)
   */
  async processAnalysisWithOrchestrator(analysisFilePath, postFilePath = null) {
    try {
      const analysisContent = await fs.readFile(analysisFilePath, 'utf8');
      const analysis = JSON.parse(analysisContent);

      let postData = null;
      if (postFilePath) {
        try {
          const postContent = await fs.readFile(postFilePath, 'utf8');
          postData = JSON.parse(postContent);
        } catch (error) {
          console.warn(`⚠️  Could not load original post: ${error.message}`);
        }
      }

      const post = {
        id: analysis.metadata?.post_id || postData?.reddit_data?.id,
        title: analysis.metadata?.title || postData?.reddit_data?.title,
        author: analysis.metadata?.username || postData?.reddit_data?.author,
        created_utc: analysis.metadata?.created_utc || postData?.reddit_data?.created_utc,
        selftext: analysis.metadata?.content || postData?.reddit_data?.selftext || '',
        url: analysis.metadata?.url || postData?.reddit_data?.url,
        subreddit: analysis.metadata?.subreddit || postData?.reddit_data?.subreddit || 'gonewildaudio',
        original_metadata: analysis.metadata,
        reddit_data: postData?.reddit_data
      };

      if (this.dryRun) {
        console.log('[DRY RUN] Would process the following:');
        console.log(`  Post: ${post.title}`);
        console.log(`  Author: ${post.author}`);

        const audioUrls = this.extractAudioUrls(post, analysis);
        console.log(`  Audio URLs: ${audioUrls.length}`);
        audioUrls.forEach(url => console.log(`    - ${url}`));

        return {
          success: true,
          dryRun: true,
          analysisFile: analysisFilePath
        };
      }

      const release = await this.releaseOrchestrator.processPost(post, analysis);

      // Determine release directory
      let releaseDir;
      if (analysis.version_naming?.release_directory) {
        releaseDir = path.join(this.dataDir, 'releases', post.author, analysis.version_naming.release_directory);
      } else {
        releaseDir = path.join(this.dataDir, 'releases', post.author, release.id);
      }

      return {
        success: true,
        analysisFile: analysisFilePath,
        release: release,
        releaseDir: releaseDir,
        audioSourceCount: release.audioSources.length
      };

    } catch (error) {
      console.error(`❌ Processing failed for ${analysisFilePath}: ${error.message}`);
      if (this.verbose) {
        console.error(error.stack);
      }
      return {
        success: false,
        analysisFile: analysisFilePath,
        error: error.message
      };
    }
  }

  /**
   * Extract audio URLs from post and analysis
   */
  extractAudioUrls(post, analysis) {
    const urls = new Set();

    const urlRegex = /https?:\/\/(?:www\.)?(soundgasm\.net|whyp\.it|hotaudio\.net)[^\s\]]+/gi;
    const postUrls = (post.selftext || '').match(urlRegex) || [];
    postUrls.forEach(url => urls.add(url));

    if (analysis?.audio_versions) {
      for (const version of analysis.audio_versions) {
        if (version.urls) {
          version.urls.forEach(urlInfo => urls.add(urlInfo.url));
        }
      }
    }

    return Array.from(urls);
  }

  /**
   * Import release to Stashapp
   */
  async importToStashapp(releaseDir) {
    if (this.skipImport) {
      console.log('⏭️  Skipping Stashapp import (--skip-import)');
      return { success: true, skipped: true };
    }

    try {
      console.log(`📤 Importing to Stashapp: ${releaseDir}`);

      return new Promise((resolve, reject) => {
        const proc = spawn('uv', ['run', 'python', 'stashapp_importer.py', releaseDir], {
          cwd: __dirname,
          stdio: this.verbose ? 'inherit' : 'pipe'
        });

        let stdout = '';
        let stderr = '';

        if (!this.verbose) {
          proc.stdout.on('data', (data) => { stdout += data.toString(); });
          proc.stderr.on('data', (data) => { stderr += data.toString(); });
        }

        proc.on('close', (code) => {
          if (code === 0) {
            // Try to extract scene ID from output
            const sceneMatch = stdout.match(/Found scene ID: (\d+)/);
            const sceneId = sceneMatch ? sceneMatch[1] : null;

            console.log(`✅ Stashapp import completed`);
            resolve({ success: true, stashSceneId: sceneId });
          } else {
            console.error(`❌ Stashapp import failed (exit code ${code})`);
            if (!this.verbose && stderr) {
              console.error(stderr);
            }
            resolve({ success: false, error: `Exit code ${code}` });
          }
        });

        proc.on('error', (error) => {
          console.error(`❌ Failed to run stashapp_importer.py: ${error.message}`);
          resolve({ success: false, error: error.message });
        });
      });

    } catch (error) {
      console.error(`❌ Stashapp import failed: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  /**
   * Process a single Reddit post through the complete pipeline
   * @param {string} postFilePath - Path to the post JSON file
   * @param {string} progressPrefix - Optional prefix for progress display (e.g., "[1/247]")
   */
  async processPost(postFilePath, progressPrefix = '') {
    const postId = await this.getPostId(postFilePath);

    // Check if already processed
    if (!this.force && await this.isProcessed(postId)) {
      console.log(`${progressPrefix}⏭️  Already processed: ${postId} (${path.basename(postFilePath)})`);
      return { success: true, skipped: true, postId };
    }

    // Step 1: Analyze the post
    const analysisResult = await this.analyzePost(postFilePath);
    if (!analysisResult.success) {
      // Handle posts with no content (crossposts, link posts) as skipped, not failed
      if (analysisResult.noContent) {
        console.log(`${progressPrefix}⏭️  No content: ${postId} (${analysisResult.error})`);
        await this.markProcessed(postId, { success: true, stage: 'skipped', reason: analysisResult.error });
        return { success: true, skipped: true, postId, noContent: true };
      }

      console.log(`\n${'='.repeat(60)}`);
      console.log(`${progressPrefix}❌ Analysis failed: ${path.basename(postFilePath)}`);
      console.log(`${'='.repeat(60)}`);
      console.log(`Error: ${analysisResult.error}`);
      await this.markProcessed(postId, { success: false, stage: 'analysis', error: analysisResult.error });
      return {
        success: false,
        stage: 'analysis',
        postFile: postFilePath,
        error: analysisResult.error
      };
    }

    console.log(`\n${'='.repeat(60)}`);
    console.log(`${progressPrefix}🔄 Processing: ${path.basename(postFilePath)}`);
    console.log(`${'='.repeat(60)}`);

    // Step 2: Download audio through release orchestrator
    console.log('\n📥 Step 2: Downloading audio...');
    const processResult = await this.processAnalysisWithOrchestrator(
      analysisResult.analysisFile,
      postFilePath
    );

    if (!processResult.success) {
      await this.markProcessed(postId, { success: false, stage: 'download', error: processResult.error });
      return {
        success: false,
        stage: 'download',
        postFile: postFilePath,
        analysisFile: analysisResult.analysisFile,
        error: processResult.error
      };
    }

    if (processResult.dryRun) {
      return { success: true, dryRun: true };
    }

    // Step 3: Import to Stashapp
    console.log('\n📤 Step 3: Importing to Stashapp...');
    const importResult = await this.importToStashapp(processResult.releaseDir);

    // Mark as processed
    const result = {
      success: true,
      postFile: postFilePath,
      analysisFile: analysisResult.analysisFile,
      release: processResult.release,
      releaseDir: processResult.releaseDir,
      stashSceneId: importResult.stashSceneId,
      importSuccess: importResult.success
    };

    await this.markProcessed(postId, result);

    // Summary
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`✅ Release: ${processResult.release.id}`);
    console.log(`🎵 Audio sources: ${processResult.audioSourceCount}`);
    console.log(`📁 Directory: ${processResult.releaseDir}`);
    if (importResult.stashSceneId) {
      console.log(`🎬 Stashapp scene: ${importResult.stashSceneId}`);
    }

    return result;
  }

  /**
   * Process multiple Reddit posts
   */
  async processBatch(postFiles) {
    console.log(`\n📦 Processing batch of ${postFiles.length} Reddit posts`);
    console.log(`${'='.repeat(60)}\n`);

    const results = {
      processed: [],
      skipped: [],
      failed: []
    };

    for (let i = 0; i < postFiles.length; i++) {
      const postFile = postFiles[i];
      const progressPrefix = `[${i + 1}/${postFiles.length}] `;

      try {
        const result = await this.processPost(postFile, progressPrefix);

        if (result.skipped) {
          results.skipped.push({ file: postFile, postId: result.postId });
        } else if (result.success) {
          results.processed.push({ file: postFile, result });
        } else {
          results.failed.push({ file: postFile, stage: result.stage, error: result.error });
        }

        // Brief delay between posts
        if (i < postFiles.length - 1 && !result.skipped && !this.dryRun) {
          console.log('\n⏱️  Waiting 3 seconds before next post...');
          await new Promise(resolve => setTimeout(resolve, 3000));
        }
      } catch (error) {
        console.error(`❌ Unexpected error: ${error.message}`);
        results.failed.push({ file: postFile, error: error.message });
      }
    }

    // Batch summary
    console.log(`\n${'='.repeat(60)}`);
    console.log('📊 Batch Processing Summary');
    console.log(`${'='.repeat(60)}`);
    console.log(`✅ Processed: ${results.processed.length}`);
    console.log(`⏭️  Skipped (already done): ${results.skipped.length}`);
    console.log(`❌ Failed: ${results.failed.length}`);

    if (results.failed.length > 0) {
      console.log('\nFailed posts:');
      for (const fail of results.failed) {
        console.log(`  - ${path.basename(fail.file)}: ${fail.error || fail.stage}`);
      }
    }

    return results;
  }

  /**
   * Find all JSON files in a directory (Reddit posts)
   */
  async findRedditPosts(directory) {
    const posts = [];

    const searchDirectory = async (dir) => {
      const entries = await fs.readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
          await searchDirectory(fullPath);
        } else if (entry.isFile() && entry.name.endsWith('.json') && !entry.name.includes('_enriched')) {
          // Check if it looks like a Reddit post
          try {
            const content = await fs.readFile(fullPath, 'utf8');
            const data = JSON.parse(content);
            if (data.reddit_data && data.reddit_data.selftext !== undefined) {
              posts.push(fullPath);
            }
          } catch {
            // Skip invalid JSON files
          }
        }
      }
    };

    await searchDirectory(directory);
    return posts;
  }

  /**
   * Show processing status
   */
  async showStatus() {
    await this.loadProcessedPosts();

    const posts = this.processedPosts.posts;
    const total = Object.keys(posts).length;
    const successful = Object.values(posts).filter(p => p.success).length;
    const failed = Object.values(posts).filter(p => !p.success).length;

    console.log('📊 Processing Status');
    console.log(`${'='.repeat(40)}`);
    console.log(`Total processed: ${total}`);
    console.log(`  ✅ Successful: ${successful}`);
    console.log(`  ❌ Failed: ${failed}`);
    console.log(`Last updated: ${this.processedPosts.lastUpdated || 'Never'}`);

    if (failed > 0) {
      console.log('\nFailed posts:');
      for (const [postId, info] of Object.entries(posts)) {
        if (!info.success) {
          console.log(`  - ${postId}`);
        }
      }
    }
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Analyze, Download, and Import Pipeline
=======================================

Complete workflow that analyzes Reddit posts, downloads audio, and imports to Stashapp.

Usage: node analyze-download-import.js <post_file_or_directory> [options]

Arguments:
  post_file_or_directory   Reddit post JSON file or directory containing posts

Options:
  --analysis-dir <dir>   Directory for analysis results (default: analysis_results)
  --data-dir <dir>       Directory for all data (default: data)
  --dry-run              Show what would be done without actually processing
  --verbose              Show detailed progress information
  --skip-analysis        Skip analysis if already exists
  --skip-import          Skip Stashapp import step
  --force                Re-process even if already done
  --status               Show processing status and exit
  --help                 Show this help message

Examples:
  # Process single Reddit post
  node analyze-download-import.js extracted_data/reddit/SweetnEvil86/1bdg16n_post.json

  # Process all posts in directory
  node analyze-download-import.js extracted_data/reddit/SweetnEvil86/

  # Dry run to see what would be processed
  node analyze-download-import.js extracted_data/reddit/SweetnEvil86/ --dry-run

  # Re-process a specific post (ignore tracking)
  node analyze-download-import.js extracted_data/reddit/SweetnEvil86/1bdg16n_post.json --force

  # Process without importing to Stashapp
  node analyze-download-import.js extracted_data/reddit/SweetnEvil86/ --skip-import

  # Show current processing status
  node analyze-download-import.js --status
`);
    return 0;
  }

  const options = {
    analysisDir: 'analysis_results',
    dataDir: 'data',
    dryRun: false,
    verbose: false,
    skipAnalysis: false,
    skipImport: false,
    force: false
  };

  let inputPath = null;
  let showStatus = false;

  // Parse command line options
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--analysis-dir':
        options.analysisDir = args[++i];
        break;
      case '--data-dir':
        options.dataDir = args[++i];
        break;
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--verbose':
        options.verbose = true;
        break;
      case '--skip-analysis':
        options.skipAnalysis = true;
        break;
      case '--skip-import':
        options.skipImport = true;
        break;
      case '--force':
        options.force = true;
        break;
      case '--status':
        showStatus = true;
        break;
      default:
        if (!args[i].startsWith('--')) {
          inputPath = args[i];
        }
    }
  }

  try {
    const pipeline = new AnalyzeDownloadImportPipeline(options);

    // Show status
    if (showStatus) {
      await pipeline.showStatus();
      return 0;
    }

    if (!inputPath) {
      console.error('❌ Please provide a Reddit post file or directory');
      return 1;
    }

    // Check if input is file or directory
    const stat = await fs.stat(inputPath);

    if (stat.isFile()) {
      const result = await pipeline.processPost(inputPath);
      return result.success ? 0 : 1;
    } else if (stat.isDirectory()) {
      console.log(`🔍 Searching for Reddit posts in: ${inputPath}`);
      const postFiles = await pipeline.findRedditPosts(inputPath);

      if (postFiles.length === 0) {
        console.error('❌ No Reddit post files found in directory');
        return 1;
      }

      console.log(`📋 Found ${postFiles.length} Reddit post files`);
      const results = await pipeline.processBatch(postFiles);
      return results.failed.length === 0 ? 0 : 1;
    } else {
      console.error('❌ Input path must be a file or directory');
      return 1;
    }

  } catch (error) {
    console.error(`❌ Pipeline error: ${error.message}`);
    if (options.verbose) {
      console.error(error.stack);
    }
    return 1;
  }
}

if (require.main === module) {
  main().then(code => process.exit(code));
}

module.exports = AnalyzeDownloadImportPipeline;
