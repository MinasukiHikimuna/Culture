#!/usr/bin/env node

/**
 * Download Orchestrator
 * 
 * Reads analysis results from analyze-reddit-post.js and coordinates downloads
 * using the appropriate platform extractors (Soundgasm, Whyp.it, HotAudio).
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');

class DownloadOrchestrator {
  constructor(options = {}) {
    this.outputDir = options.outputDir || 'downloads';
    this.dryRun = options.dryRun || false;
    this.verbose = options.verbose || false;
    
    // Platform extractor configurations
    this.extractors = {
      'Soundgasm': {
        script: 'soundgasm-extractor.js',
        urlPattern: /soundgasm\.net/i
      },
      'Whyp.it': {
        script: 'whypit-extractor.js', 
        urlPattern: /whyp\.it/i
      },
      'HotAudio': {
        script: 'hotaudio-extractor.js',
        urlPattern: /hotaudio\.net/i
      }
    };
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
      
      if (!analysis.audio_versions || analysis.audio_versions.length === 0) {
        throw new Error('No audio versions found in analysis');
      }
      
      return analysis;
    } catch (error) {
      throw new Error(`Failed to load analysis file ${filePath}: ${error.message}`);
    }
  }

  /**
   * Extract all audio URLs from analysis
   */
  extractAudioUrls(analysis) {
    const audioUrls = [];
    
    for (const version of analysis.audio_versions) {
      if (version.urls && Array.isArray(version.urls)) {
        for (const urlInfo of version.urls) {
          audioUrls.push({
            url: urlInfo.url,
            platform: urlInfo.platform,
            version: version.version_name,
            description: version.description || ''
          });
        }
      }
    }
    
    return audioUrls;
  }

  /**
   * Determine which extractor to use for a platform
   */
  getExtractorForPlatform(platform, url) {
    // First try exact platform match
    if (this.extractors[platform]) {
      return this.extractors[platform];
    }
    
    // Fall back to URL pattern matching
    for (const [platformName, extractor] of Object.entries(this.extractors)) {
      if (extractor.urlPattern.test(url)) {
        return extractor;
      }
    }
    
    return null;
  }

  /**
   * Create organized output directory structure
   */
  async createOutputStructure(analysis) {
    const postId = analysis.metadata.post_id;
    const username = analysis.metadata.username;
    const title = this.sanitizeFilename(analysis.metadata.title);
    
    // Create directory structure: downloads/username/postid_title/
    const outputPath = path.join(this.outputDir, username, `${postId}_${title}`);
    
    try {
      await fs.mkdir(outputPath, { recursive: true });
      return outputPath;
    } catch (error) {
      throw new Error(`Failed to create output directory ${outputPath}: ${error.message}`);
    }
  }

  /**
   * Sanitize filename for filesystem compatibility
   */
  sanitizeFilename(filename) {
    return filename
      .replace(/[<>:"/\\|?*]/g, '-')  // Replace invalid chars with dash
      .replace(/\s+/g, '-')          // Replace spaces with dash
      .replace(/-+/g, '-')           // Replace multiple dashes with single dash
      .replace(/^-|-$/g, '')         // Remove leading/trailing dashes
      .substring(0, 100);            // Limit length
  }

  /**
   * Save metadata alongside downloads
   */
  async saveMetadata(outputPath, analysis, downloadResults) {
    const metadata = {
      ...analysis.metadata,
      downloads: downloadResults,
      downloaded_at: new Date().toISOString()
    };
    
    const metadataPath = path.join(outputPath, 'metadata.json');
    await fs.writeFile(metadataPath, JSON.stringify(metadata, null, 2));
    
    // Also save the full analysis
    const analysisPath = path.join(outputPath, 'analysis.json');
    await fs.writeFile(analysisPath, JSON.stringify(analysis, null, 2));
    
    return { metadataPath, analysisPath };
  }

  /**
   * Execute extractor for a specific URL
   */
  async downloadAudio(audioInfo, outputPath, analysis = null) {
    const { url, platform, version, description } = audioInfo;
    const extractor = this.getExtractorForPlatform(platform, url);
    
    if (!extractor) {
      return {
        url,
        platform,
        version,
        status: 'skipped',
        error: `No extractor found for platform: ${platform}`
      };
    }
    
    try {
      if (this.dryRun) {
        console.log(`[DRY RUN] Would download: ${url} using ${extractor.script}`);
        return {
          url,
          platform, 
          version,
          status: 'dry_run',
          extractor: extractor.script
        };
      }
      
      // Check if extractor script exists
      const extractorPath = path.join(__dirname, extractor.script);
      try {
        await fs.access(extractorPath);
      } catch (error) {
        return {
          url,
          platform,
          version, 
          status: 'error',
          error: `Extractor script not found: ${extractor.script}`
        };
      }
      
      if (this.verbose) {
        console.log(`📥 Downloading ${version} from ${platform}: ${url}`);
      }
      
      // Execute the extractor with correct command format
      let command = `node "${extractorPath}" extract "${url}" --output "${outputPath}"`;
      
      // Pass analysis metadata if available
      if (analysis) {
        const analysisFile = path.join(outputPath, 'temp_analysis.json');
        await fs.writeFile(analysisFile, JSON.stringify(analysis, null, 2));
        command += ` --analysis-metadata "${analysisFile}"`;
      }
      
      const result = execSync(command, { 
        encoding: 'utf8',
        timeout: 300000, // 5 minute timeout
        cwd: __dirname
      });
      
      // Clean up temp analysis file
      if (analysis) {
        const analysisFile = path.join(outputPath, 'temp_analysis.json');
        try {
          await fs.unlink(analysisFile);
        } catch (error) {
          // Ignore cleanup errors
        }
      }
      
      return {
        url,
        platform,
        version,
        status: 'success',
        extractor: extractor.script,
        output: result.trim()
      };
      
    } catch (error) {
      console.error(`❌ Download failed for ${url}: ${error.message}`);
      return {
        url,
        platform,
        version,
        status: 'error',
        error: error.message,
        extractor: extractor.script
      };
    }
  }

  /**
   * Download all audio files from analysis
   */
  async downloadFromAnalysis(analysisFilePath) {
    try {
      console.log(`📋 Loading analysis from: ${analysisFilePath}`);
      const analysis = await this.loadAnalysis(analysisFilePath);
      
      console.log(`🎯 Post: ${analysis.metadata.title}`);
      console.log(`👤 Author: ${analysis.metadata.username}`);
      console.log(`🆔 Post ID: ${analysis.metadata.post_id}`);
      
      // Extract audio URLs
      const audioUrls = this.extractAudioUrls(analysis);
      console.log(`🎵 Found ${audioUrls.length} audio URLs to download`);
      
      if (audioUrls.length === 0) {
        console.log('⚠️  No audio URLs found in analysis');
        return { success: false, error: 'No audio URLs found' };
      }
      
      // Create output directory structure
      const outputPath = await this.createOutputStructure(analysis);
      console.log(`📁 Output directory: ${outputPath}`);
      
      // Download each audio file
      const downloadResults = [];
      for (let i = 0; i < audioUrls.length; i++) {
        const audioInfo = audioUrls[i];
        console.log(`\n📥 [${i + 1}/${audioUrls.length}] ${audioInfo.version} (${audioInfo.platform})`);
        
        const result = await this.downloadAudio(audioInfo, outputPath, analysis);
        downloadResults.push(result);
        
        if (result.status === 'success') {
          console.log(`✅ Downloaded successfully`);
        } else if (result.status === 'dry_run') {
          console.log(`🔍 Dry run completed`);
        } else {
          console.log(`❌ Download failed: ${result.error}`);
        }
      }
      
      // Save metadata
      const { metadataPath, analysisPath } = await this.saveMetadata(outputPath, analysis, downloadResults);
      
      // Summary
      const successful = downloadResults.filter(r => r.status === 'success').length;
      const failed = downloadResults.filter(r => r.status === 'error').length;
      const skipped = downloadResults.filter(r => r.status === 'skipped').length;
      
      console.log(`\n📊 Download Summary:`);
      console.log(`✅ Successful: ${successful}`);
      console.log(`❌ Failed: ${failed}`);
      console.log(`⏭️  Skipped: ${skipped}`);
      console.log(`📁 Output: ${outputPath}`);
      console.log(`📄 Metadata: ${metadataPath}`);
      console.log(`📋 Analysis: ${analysisPath}`);
      
      return {
        success: true,
        outputPath,
        downloadResults,
        summary: { successful, failed, skipped }
      };
      
    } catch (error) {
      console.error(`❌ Download orchestration failed: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  /**
   * Process multiple analysis files
   */
  async downloadBatch(analysisFiles) {
    console.log(`📦 Processing batch of ${analysisFiles.length} analysis files`);
    
    const results = [];
    for (let i = 0; i < analysisFiles.length; i++) {
      const filePath = analysisFiles[i];
      console.log(`\n🔄 [${i + 1}/${analysisFiles.length}] Processing: ${filePath}`);
      
      const result = await this.downloadFromAnalysis(filePath);
      results.push({ filePath, ...result });
      
      // Brief delay between downloads to be respectful
      if (i < analysisFiles.length - 1) {
        console.log('⏱️  Waiting 2 seconds before next download...');
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }
    
    // Batch summary
    const totalSuccessful = results.filter(r => r.success).length;
    const totalFailed = results.filter(r => !r.success).length;
    
    console.log(`\n📊 Batch Summary:`);
    console.log(`✅ Files processed successfully: ${totalSuccessful}`);
    console.log(`❌ Files failed: ${totalFailed}`);
    
    return results;
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Download Orchestrator - Coordinate downloads from Reddit analysis results

Usage: node download-orchestrator.js <analysis_file_or_directory> [options]

Arguments:
  analysis_file_or_directory  Path to analysis JSON file or directory containing analysis files

Options:
  --output <dir>        Output directory for downloads (default: downloads)
  --dry-run            Show what would be downloaded without actually downloading
  --verbose            Show detailed download progress
  --help               Show this help message

Examples:
  # Download from single analysis file
  node download-orchestrator.js test_analysis.json

  # Download from all analysis files in directory
  node download-orchestrator.js analysis_results/

  # Dry run to see what would be downloaded
  node download-orchestrator.js test_analysis.json --dry-run

  # Custom output directory with verbose logging
  node download-orchestrator.js test_analysis.json --output my_downloads --verbose
`);
    return 0;
  }
  
  const inputPath = args[0];
  const options = {
    outputDir: 'downloads',
    dryRun: false,
    verbose: false
  };
  
  // Parse command line options
  for (let i = 1; i < args.length; i++) {
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
    }
  }
  
  try {
    const orchestrator = new DownloadOrchestrator(options);
    
    // Check if input is file or directory
    const stat = await fs.stat(inputPath);
    
    if (stat.isFile()) {
      // Single file
      const result = await orchestrator.downloadFromAnalysis(inputPath);
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
      
      const results = await orchestrator.downloadBatch(analysisFiles);
      const success = results.every(r => r.success);
      return success ? 0 : 1;
    } else {
      console.error('❌ Input path must be a file or directory');
      return 1;
    }
    
  } catch (error) {
    console.error(`❌ Error: ${error.message}`);
    return 1;
  }
}

if (require.main === module) {
  main().then(code => process.exit(code));
}

module.exports = DownloadOrchestrator;