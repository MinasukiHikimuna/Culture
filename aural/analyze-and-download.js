#!/usr/bin/env node

/**
 * Analyze and Download Pipeline
 * 
 * Complete workflow script that:
 * 1. Analyzes Reddit posts using analyze-reddit-post.js
 * 2. Downloads audio files using download-orchestrator.js
 * 
 * Supports both single posts and batch processing.
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');

class AnalyzeAndDownloadPipeline {
  constructor(options = {}) {
    this.analysisDir = options.analysisDir || 'analysis_results';
    this.downloadDir = options.downloadDir || 'downloads';
    this.dryRun = options.dryRun || false;
    this.verbose = options.verbose || false;
    this.saveApproved = options.saveApproved || false;
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
   * Download from analysis result
   */
  async downloadFromAnalysis(analysisFilePath) {
    try {
      if (this.verbose) {
        console.log(`📥 Starting download from: ${analysisFilePath}`);
      }
      
      // Build download command
      let command = `node download-orchestrator.js "${analysisFilePath}" --output "${this.downloadDir}"`;
      if (this.dryRun) {
        command += ' --dry-run';
      }
      if (this.verbose) {
        command += ' --verbose';
      }
      
      // Execute download
      const result = execSync(command, { 
        encoding: 'utf8',
        timeout: 600000, // 10 minute timeout for downloads
        cwd: __dirname
      });
      
      if (this.verbose) {
        console.log(`✅ Download completed`);
      }
      
      return {
        success: true,
        analysisFile: analysisFilePath,
        output: result.trim()
      };
      
    } catch (error) {
      console.error(`❌ Download failed for ${analysisFilePath}: ${error.message}`);
      return {
        success: false,
        analysisFile: analysisFilePath,
        error: error.message
      };
    }
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
    
    // Step 2: Download from analysis
    const downloadResult = await this.downloadFromAnalysis(analysisResult.analysisFile);
    if (!downloadResult.success) {
      return {
        success: false,
        stage: 'download', 
        postFile: postFilePath,
        analysisFile: analysisResult.analysisFile,
        error: downloadResult.error
      };
    }
    
    return {
      success: true,
      postFile: postFilePath,
      analysisFile: analysisResult.analysisFile,
      analysisOutput: analysisResult.output,
      downloadOutput: downloadResult.output
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
      if (i < postFiles.length - 1) {
        console.log('⏱️  Waiting 3 seconds before next post...');
        await new Promise(resolve => setTimeout(resolve, 3000));
      }
    }
    
    // Batch summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;
    const analysisFailures = results.filter(r => !r.success && r.stage === 'analysis').length;
    const downloadFailures = results.filter(r => !r.success && r.stage === 'download').length;
    
    console.log(`\n📊 Batch Processing Summary:`);
    console.log(`✅ Successful: ${successful}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`   └── Analysis failures: ${analysisFailures}`);
    console.log(`   └── Download failures: ${downloadFailures}`);
    console.log(`📁 Analysis results: ${this.analysisDir}`);
    console.log(`📁 Downloads: ${this.downloadDir}`);
    
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
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Analyze and Download Pipeline - Complete workflow from Reddit analysis to audio downloads

Usage: node analyze-and-download.js <post_file_or_directory> [options]

Arguments:
  post_file_or_directory   Reddit post JSON file or directory containing Reddit posts

Options:
  --analysis-dir <dir>     Directory for analysis results (default: analysis_results)
  --download-dir <dir>     Directory for downloads (default: downloads)
  --dry-run               Analyze posts but don't actually download files
  --verbose               Show detailed progress information
  --save-approved         Save analysis as approved (for LLM training)
  --help                  Show this help message

Examples:
  # Process single Reddit post
  node analyze-and-download.js reddit_data/alekirser/1lxhwbd_post.json

  # Process all posts in directory  
  node analyze-and-download.js reddit_data/alekirser/

  # Dry run to see what would be analyzed and downloaded
  node analyze-and-download.js reddit_data/alekirser/ --dry-run --verbose

  # Custom directories with analysis saving
  node analyze-and-download.js reddit_data/ --analysis-dir my_analysis --download-dir my_downloads --save-approved
`);
    return 0;
  }
  
  const inputPath = args[0];
  const options = {
    analysisDir: 'analysis_results',
    downloadDir: 'downloads',
    dryRun: false,
    verbose: false,
    saveApproved: false
  };
  
  // Parse command line options
  for (let i = 1; i < args.length; i++) {
    switch (args[i]) {
      case '--analysis-dir':
        options.analysisDir = args[++i];
        break;
      case '--download-dir':
        options.downloadDir = args[++i];
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
    }
  }
  
  try {
    const pipeline = new AnalyzeAndDownloadPipeline(options);
    
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
    return 1;
  }
}

if (require.main === module) {
  main().then(code => process.exit(code));
}

module.exports = AnalyzeAndDownloadPipeline;