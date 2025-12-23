#!/usr/bin/env node

/**
 * Download Orchestrator V2 - Uses new Release Orchestrator
 * 
 * Bridges the existing analyze-reddit-post.js output format with 
 * the new release-orchestrator.js architecture.
 */

const fs = require('fs').promises;
const path = require('path');
const { ReleaseOrchestrator, Release, AudioSource } = require('./release-orchestrator');

class DownloadOrchestratorV2 {
  constructor(options = {}) {
    this.outputDir = options.outputDir || 'data';
    this.dryRun = options.dryRun || false;
    this.verbose = options.verbose || false;
    
    // Initialize release orchestrator
    this.releaseOrchestrator = new ReleaseOrchestrator({
      dataDir: this.outputDir,
      cacheEnabled: !this.dryRun,
      validateExtractions: true
    });
  }

  /**
   * Load analysis result from JSON file
   */
  async loadAnalysis(filePath) {
    try {
      const content = await fs.readFile(filePath, 'utf8');
      const analysis = JSON.parse(content);
      
      if (!analysis.metadata || !analysis.metadata.post_id) {
        throw new Error('Invalid analysis file: missing metadata.post_id');
      }
      
      return analysis;
    } catch (error) {
      throw new Error(`Failed to load analysis file ${filePath}: ${error.message}`);
    }
  }

  /**
   * Convert analysis format to post format for release orchestrator
   */
  convertAnalysisToPost(analysis) {
    return {
      id: analysis.metadata.post_id,
      title: analysis.metadata.title,
      author: analysis.metadata.username,
      created_utc: analysis.metadata.created_utc || new Date().toISOString(),
      selftext: analysis.metadata.content || '',
      url: analysis.metadata.url,
      subreddit: analysis.metadata.subreddit || 'gonewildaudio',
      
      // Preserve original metadata
      original_metadata: analysis.metadata
    };
  }

  /**
   * Process analysis file through release orchestrator
   */
  async processAnalysisFile(analysisFilePath) {
    try {
      console.log(`📋 Loading analysis from: ${analysisFilePath}`);
      const analysis = await this.loadAnalysis(analysisFilePath);
      
      console.log(`🎯 Post: ${analysis.metadata.title}`);
      console.log(`👤 Author: ${analysis.metadata.username}`);
      console.log(`🆔 Post ID: ${analysis.metadata.post_id}`);
      
      if (this.dryRun) {
        console.log('[DRY RUN] Would process the following audio URLs:');
        if (analysis.audio_versions) {
          for (const version of analysis.audio_versions) {
            if (version.urls) {
              version.urls.forEach(urlInfo => {
                console.log(`  - ${urlInfo.url} (${urlInfo.platform})`);
              });
            }
          }
        }
        return { success: true, dryRun: true };
      }
      
      // Convert to post format
      const post = this.convertAnalysisToPost(analysis);
      
      // Process through release orchestrator
      const release = await this.releaseOrchestrator.processPost(post, analysis);
      
      // Summary
      console.log(`\n📊 Download Summary:`);
      console.log(`✅ Release ID: ${release.id}`);
      console.log(`🎵 Audio sources: ${release.audioSources.length}`);
      
      const platforms = [...new Set(release.audioSources.map(s => s.metadata.platform.name))];
      console.log(`🌐 Platforms: ${platforms.join(', ')}`);
      
      // List downloaded files
      console.log(`\n📁 Downloaded files:`);
      for (const source of release.audioSources) {
        if (source.audio.filePath) {
          console.log(`  - ${source.audio.filePath}`);
        }
      }
      
      return {
        success: true,
        release: release,
        audioSourceCount: release.audioSources.length
      };
      
    } catch (error) {
      console.error(`❌ Processing failed: ${error.message}`);
      if (this.verbose) {
        console.error(error.stack);
      }
      return { success: false, error: error.message };
    }
  }

  /**
   * Process multiple analysis files
   */
  async processBatch(analysisFiles) {
    console.log(`📦 Processing batch of ${analysisFiles.length} analysis files`);
    
    const results = [];
    for (let i = 0; i < analysisFiles.length; i++) {
      const filePath = analysisFiles[i];
      console.log(`\n🔄 [${i + 1}/${analysisFiles.length}] Processing: ${filePath}`);
      
      const result = await this.processAnalysisFile(filePath);
      results.push({ filePath, ...result });
      
      // Brief delay between downloads to be respectful
      if (i < analysisFiles.length - 1 && !this.dryRun) {
        console.log('⏱️  Waiting 2 seconds before next download...');
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }
    
    // Batch summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;
    
    console.log(`\n📊 Batch Summary:`);
    console.log(`✅ Files processed successfully: ${successful}`);
    console.log(`❌ Files failed: ${failed}`);
    
    return results;
  }

  /**
   * Migrate existing downloads to new structure
   */
  async migrateExistingDownloads(downloadsDir) {
    console.log(`🔄 Migrating existing downloads from: ${downloadsDir}`);
    
    try {
      const users = await fs.readdir(downloadsDir);
      let migratedCount = 0;
      
      for (const user of users) {
        const userPath = path.join(downloadsDir, user);
        const stat = await fs.stat(userPath);
        
        if (!stat.isDirectory()) continue;
        
        const posts = await fs.readdir(userPath);
        
        for (const post of posts) {
          const postPath = path.join(userPath, post);
          const postStat = await fs.stat(postPath);
          
          if (!postStat.isDirectory()) continue;
          
          // Look for analysis.json
          const analysisPath = path.join(postPath, 'analysis.json');
          try {
            await fs.access(analysisPath);
            console.log(`📄 Found analysis: ${analysisPath}`);
            
            // Process through new system
            const result = await this.processAnalysisFile(analysisPath);
            if (result.success) {
              migratedCount++;
            }
          } catch {
            // No analysis.json in this directory
          }
        }
      }
      
      console.log(`✅ Migrated ${migratedCount} releases`);
      return { success: true, migratedCount };
      
    } catch (error) {
      console.error(`❌ Migration failed: ${error.message}`);
      return { success: false, error: error.message };
    }
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Download Orchestrator V2 - Uses new Release Orchestrator architecture

Usage: node download-orchestrator-v2.js <analysis_file_or_directory> [options]

Arguments:
  analysis_file_or_directory  Path to analysis JSON file or directory containing analysis files

Options:
  --output <dir>        Output directory for downloads (default: data)
  --dry-run            Show what would be downloaded without actually downloading
  --verbose            Show detailed progress and errors
  --migrate <dir>      Migrate existing downloads from old structure
  --help               Show this help message

Examples:
  # Download from single analysis file
  node download-orchestrator-v2.js test_analysis.json

  # Download from all analysis files in directory
  node download-orchestrator-v2.js analysis_results/

  # Dry run to see what would be downloaded
  node download-orchestrator-v2.js test_analysis.json --dry-run

  # Migrate existing downloads
  node download-orchestrator-v2.js --migrate downloads/

  # Custom output directory with verbose logging
  node download-orchestrator-v2.js test_analysis.json --output extracted_data --verbose
`);
    return 0;
  }
  
  const options = {
    outputDir: 'data',
    dryRun: false,
    verbose: false
  };
  
  let inputPath = null;
  let migrateDir = null;
  
  // Parse command line options
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--output':
        options.outputDir = args[++i];
        break;
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--verbose':
        options.verbose = true;
        break;
      case '--migrate':
        migrateDir = args[++i];
        break;
      default:
        if (!args[i].startsWith('--')) {
          inputPath = args[i];
        }
    }
  }
  
  try {
    const orchestrator = new DownloadOrchestratorV2(options);
    
    // Handle migration
    if (migrateDir) {
      const result = await orchestrator.migrateExistingDownloads(migrateDir);
      return result.success ? 0 : 1;
    }
    
    // Regular processing
    if (!inputPath) {
      console.error('❌ Please provide an analysis file or directory');
      return 1;
    }
    
    // Check if input is file or directory
    const stat = await fs.stat(inputPath);
    
    if (stat.isFile()) {
      // Single file
      const result = await orchestrator.processAnalysisFile(inputPath);
      return result.success ? 0 : 1;
    } else if (stat.isDirectory()) {
      // Directory - find all JSON files
      const files = await fs.readdir(inputPath);
      const analysisFiles = files
        .filter(f => f.endsWith('.json'))
        .map(f => path.join(inputPath, f));
      
      if (analysisFiles.length === 0) {
        console.error('❌ No JSON files found in directory');
        return 1;
      }
      
      const results = await orchestrator.processBatch(analysisFiles);
      const success = results.every(r => r.success);
      return success ? 0 : 1;
    } else {
      console.error('❌ Input path must be a file or directory');
      return 1;
    }
    
  } catch (error) {
    console.error(`❌ Error: ${error.message}`);
    if (options.verbose) {
      console.error(error.stack);
    }
    return 1;
  }
}

if (require.main === module) {
  main().then(code => process.exit(code));
}

module.exports = DownloadOrchestratorV2;