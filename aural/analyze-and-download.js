#!/usr/bin/env node

/**
 * Analyze and Download Pipeline V2 - Uses new Release Orchestrator
 * 
 * Complete workflow script that:
 * 1. Analyzes Reddit posts using analyze-reddit-post.js
 * 2. Downloads audio files using the new release orchestrator
 * 
 * Supports both single posts and batch processing.
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');
const { ReleaseOrchestrator, Release, AudioSource } = require('./release-orchestrator');

class AnalyzeAndDownloadPipelineV2 {
  constructor(options = {}) {
    this.analysisDir = options.analysisDir || 'analysis_results';
    this.dataDir = options.dataDir || 'data';
    this.dryRun = options.dryRun || false;
    this.verbose = options.verbose || false;
    this.saveApproved = options.saveApproved || false;
    this.skipAnalysis = options.skipAnalysis || false;
    
    // Initialize release orchestrator
    this.releaseOrchestrator = new ReleaseOrchestrator({
      dataDir: this.dataDir,
      validateExtractions: true
    });
  }

  /**
   * Analyze a single Reddit post file
   */
  async analyzePost(postFilePath) {
    try {
      // Create analysis directory
      await fs.mkdir(this.analysisDir, { recursive: true });
      
      // Generate analysis filename based on post file
      const postFileName = path.basename(postFilePath, '.json');
      const analysisFileName = `${postFileName}_analysis.json`;
      const analysisFilePath = path.join(this.analysisDir, analysisFileName);
      
      // Check if analysis already exists
      if (this.skipAnalysis) {
        try {
          await fs.access(analysisFilePath);
          console.log(`⏭️  Using existing analysis: ${analysisFilePath}`);
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
      
      // Build analyze command
      let command = `node analyze-reddit-post.js "${postFilePath}" --output "${analysisFilePath}"`;
      if (this.saveApproved) {
        command += ' --save-approved';
      }
      
      // Execute analysis
      const result = execSync(command, { 
        encoding: 'utf8',
        cwd: __dirname
      });
      
      if (this.verbose) {
        console.log(`✅ Analysis completed: ${analysisFilePath}`);
      }
      
      return {
        success: true,
        postFile: postFilePath,
        analysisFile: analysisFilePath,
        output: result.trim()
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
   * Process analysis through release orchestrator
   */
  async processAnalysisWithOrchestrator(analysisFilePath, postFilePath = null) {
    try {
      // Load analysis
      const analysisContent = await fs.readFile(analysisFilePath, 'utf8');
      const analysis = JSON.parse(analysisContent);
      
      if (this.verbose) {
        console.log(`📥 Processing analysis: ${analysisFilePath}`);
      }
      
      // If we have the original post file, load it for complete data
      let postData = null;
      if (postFilePath) {
        try {
          const postContent = await fs.readFile(postFilePath, 'utf8');
          postData = JSON.parse(postContent);
        } catch (error) {
          console.warn(`⚠️  Could not load original post: ${error.message}`);
        }
      }
      
      // Create post object combining data
      const post = {
        id: analysis.metadata?.post_id || postData?.reddit_data?.id,
        title: analysis.metadata?.title || postData?.reddit_data?.title,
        author: analysis.metadata?.username || postData?.reddit_data?.author,
        created_utc: analysis.metadata?.created_utc || postData?.reddit_data?.created_utc,
        selftext: analysis.metadata?.content || postData?.reddit_data?.selftext || '',
        url: analysis.metadata?.url || postData?.reddit_data?.url,
        subreddit: analysis.metadata?.subreddit || postData?.reddit_data?.subreddit || 'gonewildaudio',
        
        // Preserve all metadata
        original_metadata: analysis.metadata,
        reddit_data: postData?.reddit_data
      };
      
      if (this.dryRun) {
        console.log('[DRY RUN] Would process the following:');
        console.log(`  Post: ${post.title}`);
        console.log(`  Author: ${post.author}`);
        
        // Extract audio URLs for dry run display
        const audioUrls = this.extractAudioUrls(post, analysis);
        console.log(`  Audio URLs: ${audioUrls.length}`);
        audioUrls.forEach(url => console.log(`    - ${url}`));
        
        return {
          success: true,
          dryRun: true,
          analysisFile: analysisFilePath
        };
      }
      
      // Process through release orchestrator
      const release = await this.releaseOrchestrator.processPost(post, analysis);
      
      return {
        success: true,
        analysisFile: analysisFilePath,
        release: release,
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
    
    // From post content
    const urlRegex = /https?:\/\/(?:www\.)?(soundgasm\.net|whyp\.it|hotaudio\.net)[^\s\]]+/gi;
    const postUrls = (post.selftext || '').match(urlRegex) || [];
    postUrls.forEach(url => urls.add(url));
    
    // From analysis
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
   * Process a single Reddit post through the complete pipeline
   */
  async processPost(postFilePath) {
    console.log(`\n🔄 Processing: ${path.basename(postFilePath)}`);
    
    // Step 1: Analyze the post
    const analysisResult = await this.analyzePost(postFilePath);
    if (!analysisResult.success) {
      return {
        success: false,
        stage: 'analysis',
        postFile: postFilePath,
        error: analysisResult.error
      };
    }
    
    // Step 2: Process through release orchestrator
    const processResult = await this.processAnalysisWithOrchestrator(
      analysisResult.analysisFile,
      postFilePath
    );
    
    if (!processResult.success) {
      return {
        success: false,
        stage: 'processing', 
        postFile: postFilePath,
        analysisFile: analysisResult.analysisFile,
        error: processResult.error
      };
    }
    
    // Summary
    if (!processResult.dryRun) {
      console.log(`✅ Release created: ${processResult.release.id}`);
      console.log(`🎵 Audio sources: ${processResult.audioSourceCount}`);
    }
    
    return {
      success: true,
      postFile: postFilePath,
      analysisFile: analysisResult.analysisFile,
      release: processResult.release,
      analysisSkipped: analysisResult.skipped
    };
  }

  /**
   * Process multiple Reddit posts
   */
  async processBatch(postFiles) {
    console.log(`📦 Processing batch of ${postFiles.length} Reddit posts`);
    
    const results = [];
    for (let i = 0; i < postFiles.length; i++) {
      const postFile = postFiles[i];
      console.log(`\n🔄 [${i + 1}/${postFiles.length}] Processing: ${path.basename(postFile)}`);
      
      const result = await this.processPost(postFile);
      results.push(result);
      
      if (result.success) {
        console.log(`✅ Completed successfully`);
      } else {
        console.log(`❌ Failed at ${result.stage} stage: ${result.error}`);
      }
      
      // Brief delay between posts to be respectful
      if (i < postFiles.length - 1 && !this.dryRun) {
        console.log('⏱️  Waiting 3 seconds before next post...');
        await new Promise(resolve => setTimeout(resolve, 3000));
      }
    }
    
    // Batch summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;
    const analysisFailures = results.filter(r => !r.success && r.stage === 'analysis').length;
    const processingFailures = results.filter(r => !r.success && r.stage === 'processing').length;
    
    console.log(`\n📊 Batch Processing Summary:`);
    console.log(`✅ Successful: ${successful}`);
    console.log(`❌ Failed: ${failed}`);
    if (failed > 0) {
      console.log(`   └── Analysis failures: ${analysisFailures}`);
      console.log(`   └── Processing failures: ${processingFailures}`);
    }
    console.log(`📁 Analysis results: ${this.analysisDir}`);
    console.log(`📁 Data directory: ${this.dataDir}`);
    
    // Show release index location
    const indexPath = path.join(this.dataDir, 'releases', 'index.json');
    console.log(`📋 Release index: ${indexPath}`);
    
    return results;
  }

  /**
   * Find all JSON files in a directory (Reddit posts)
   */
  async findRedditPosts(directory) {
    const posts = [];
    
    async function searchDirectory(dir) {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory()) {
          await searchDirectory(fullPath);
        } else if (entry.isFile() && entry.name.endsWith('.json')) {
          // Check if it looks like a Reddit post (has reddit_data)
          try {
            const content = await fs.readFile(fullPath, 'utf8');
            const data = JSON.parse(content);
            if (data.reddit_data && data.reddit_data.selftext) {
              posts.push(fullPath);
            }
          } catch (error) {
            // Skip invalid JSON files
          }
        }
      }
    }
    
    await searchDirectory(directory);
    return posts;
  }

  /**
   * Process existing analysis files directly
   */
  async processAnalysisDirectory(directory) {
    console.log(`📋 Processing existing analysis files from: ${directory}`);
    
    const files = await fs.readdir(directory);
    const analysisFiles = files
      .filter(f => f.endsWith('_analysis.json'))
      .map(f => path.join(directory, f));
    
    console.log(`📊 Found ${analysisFiles.length} analysis files`);
    
    const results = [];
    for (let i = 0; i < analysisFiles.length; i++) {
      const analysisFile = analysisFiles[i];
      console.log(`\n🔄 [${i + 1}/${analysisFiles.length}] Processing: ${path.basename(analysisFile)}`);
      
      const result = await this.processAnalysisWithOrchestrator(analysisFile);
      results.push(result);
      
      if (result.success && !result.dryRun) {
        console.log(`✅ Created release with ${result.audioSourceCount} audio sources`);
      }
      
      // Brief delay
      if (i < analysisFiles.length - 1 && !this.dryRun) {
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }
    
    return results;
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Analyze and Download Pipeline V2 - Complete workflow using new Release Orchestrator

Usage: node analyze-and-download-v2.js <post_file_or_directory> [options]

Arguments:
  post_file_or_directory   Reddit post JSON file or directory containing Reddit posts

Options:
  --analysis-dir <dir>     Directory for analysis results (default: analysis_results)
  --data-dir <dir>         Directory for all data (default: data)
  --dry-run               Analyze posts but don't actually download files
  --verbose               Show detailed progress information
  --save-approved         Save analysis as approved (for LLM training)
  --skip-analysis         Skip analysis if already exists (useful for re-runs)
  --process-analysis <dir> Process existing analysis files directly
  --help                  Show this help message

Examples:
  # Process single Reddit post
  node analyze-and-download-v2.js reddit_data/alekirser/1lxhwbd_post.json

  # Process all posts in directory  
  node analyze-and-download-v2.js reddit_data/alekirser/

  # Dry run to see what would be analyzed and downloaded
  node analyze-and-download-v2.js reddit_data/alekirser/ --dry-run --verbose

  # Skip re-analyzing posts that already have analysis
  node analyze-and-download-v2.js reddit_data/ --skip-analysis

  # Process existing analysis files directly (no Reddit posts needed)
  node analyze-and-download-v2.js --process-analysis analysis_results/

  # Custom directories with analysis saving
  node analyze-and-download-v2.js reddit_data/ --analysis-dir my_analysis --data-dir extracted_data --save-approved
`);
    return 0;
  }
  
  const options = {
    analysisDir: 'analysis_results',
    dataDir: 'data',
    dryRun: false,
    verbose: false,
    saveApproved: false,
    skipAnalysis: false
  };
  
  let inputPath = null;
  let processAnalysisDir = null;
  
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
      case '--save-approved':
        options.saveApproved = true;
        break;
      case '--skip-analysis':
        options.skipAnalysis = true;
        break;
      case '--process-analysis':
        processAnalysisDir = args[++i];
        break;
      default:
        if (!args[i].startsWith('--')) {
          inputPath = args[i];
        }
    }
  }
  
  try {
    const pipeline = new AnalyzeAndDownloadPipelineV2(options);
    
    // Process existing analysis files
    if (processAnalysisDir) {
      const results = await pipeline.processAnalysisDirectory(processAnalysisDir);
      const success = results.filter(r => r.success).length > 0;
      return success ? 0 : 1;
    }
    
    // Regular processing
    if (!inputPath) {
      console.error('❌ Please provide a Reddit post file or directory');
      return 1;
    }
    
    // Check if input is file or directory
    const stat = await fs.stat(inputPath);
    
    if (stat.isFile()) {
      // Single file
      const result = await pipeline.processPost(inputPath);
      return result.success ? 0 : 1;
    } else if (stat.isDirectory()) {
      // Directory - find all Reddit post files
      console.log(`🔍 Searching for Reddit posts in: ${inputPath}`);
      const postFiles = await pipeline.findRedditPosts(inputPath);
      
      if (postFiles.length === 0) {
        console.error('❌ No Reddit post files found in directory');
        return 1;
      }
      
      console.log(`📋 Found ${postFiles.length} Reddit post files`);
      const results = await pipeline.processBatch(postFiles);
      const success = results.filter(r => r.success).length > 0;
      return success ? 0 : 1;
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

module.exports = AnalyzeAndDownloadPipelineV2;