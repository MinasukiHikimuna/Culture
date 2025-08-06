#!/usr/bin/env node

/**
 * Enhanced Reddit Post Preprocessor with Script URL Resolution
 * 
 * Extends the original preprocessor to handle indirect script references
 * by resolving Reddit shortlinks and extracting script URLs from linked posts.
 */

const fs = require('fs');
const { spawn } = require('child_process');
const path = require('path');

class EnhancedRedditPreprocessor {
  constructor(options = {}) {
    // Import the original preprocessor
    const RedditPostPreprocessor = require('./preprocess-reddit-post.js');
    this.originalPreprocessor = new RedditPostPreprocessor();
    
    // Script URL extraction utility path
    this.scriptExtractorPath = options.scriptExtractorPath || './script_url_extractor.py';
    this.enableScriptResolution = options.enableScriptResolution !== false;
    
    // Enhanced script patterns for detecting indirect references
    this.indirectScriptPatterns = {
      // Reddit shortlinks
      shortlink: /\[script\s*(?:here|link)?\]\(https:\/\/www\.reddit\.com\/r\/gonewildaudio\/s\/([a-zA-Z0-9]+)\)/i,
      // Reddit post links
      postLink: /\[script\s*(?:here|link)?\]\(https:\/\/www\.reddit\.com\/r\/gonewildaudio\/comments\/([a-z0-9]+)\/[^)]*\)/i,
      // Direct script platform links that might be hidden
      hiddenScript: /\[script\s*(?:here|link)?\]\(([^)]+)\)/i
    };
  }

  /**
   * Enhanced script extraction with URL resolution
   */
  async extractEnhancedScriptInfo(content, link_flair_text = null, postId = null) {
    // Start with original script extraction
    const baseScriptInfo = this.originalPreprocessor.extractScriptInfo(content, link_flair_text);
    
    // If we already have a script URL or this is not a public fill, return base info
    if (baseScriptInfo.url || baseScriptInfo.fillType !== 'public' || !this.enableScriptResolution) {
      return baseScriptInfo;
    }
    
    // Check for indirect script references
    const indirectRef = this.detectIndirectScriptReference(content);
    if (!indirectRef) {
      return baseScriptInfo;
    }
    
    console.log(`📋 Detected indirect script reference: ${indirectRef.type} - ${indirectRef.url}`);
    
    // Try to resolve the script URL
    try {
      const resolvedInfo = await this.resolveScriptUrl(postId, indirectRef);
      if (resolvedInfo) {
        return {
          ...baseScriptInfo,
          url: resolvedInfo.url,
          author: resolvedInfo.author || baseScriptInfo.author,
          fillType: 'public',
          resolution_info: {
            original_reference: indirectRef.url,
            resolved_via: indirectRef.type,
            resolved_post_id: resolvedInfo.resolved_post_id,
            resolved_title: resolvedInfo.resolved_title
          }
        };
      }
    } catch (error) {
      console.warn(`⚠️ Failed to resolve script URL: ${error.message}`);
      // Add resolution attempt info even if it failed
      baseScriptInfo.failed_resolution = {
        attempted_url: indirectRef.url,
        error: error.message
      };
    }
    
    return baseScriptInfo;
  }

  /**
   * Detect indirect script references in post content
   */
  detectIndirectScriptReference(content) {
    // Check for Reddit shortlinks
    const shortlinkMatch = content.match(this.indirectScriptPatterns.shortlink);
    if (shortlinkMatch) {
      return {
        type: 'reddit_shortlink',
        url: shortlinkMatch[0].match(/\(([^)]+)\)/)[1],
        shortcode: shortlinkMatch[1]
      };
    }
    
    // Check for Reddit post links
    const postLinkMatch = content.match(this.indirectScriptPatterns.postLink);
    if (postLinkMatch) {
      return {
        type: 'reddit_post_link',
        url: postLinkMatch[0].match(/\(([^)]+)\)/)[1],
        post_id: postLinkMatch[1]
      };
    }
    
    // Check for any [script](url) pattern that wasn't caught by original preprocessing
    const hiddenScriptMatch = content.match(this.indirectScriptPatterns.hiddenScript);
    if (hiddenScriptMatch && hiddenScriptMatch[1].includes('reddit.com')) {
      return {
        type: 'reddit_link',
        url: hiddenScriptMatch[1]
      };
    }
    
    return null;
  }

  /**
   * Use Python script to resolve script URLs
   */
  async resolveScriptUrl(postId, indirectRef) {
    if (!postId) {
      throw new Error('Post ID required for script resolution');
    }
    
    return new Promise((resolve, reject) => {
      // Run the Python script URL extractor
      const pythonProcess = spawn('python', [this.scriptExtractorPath, postId], {
        stdio: ['pipe', 'pipe', 'pipe']
      });
      
      let stdout = '';
      let stderr = '';
      
      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });
      
      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });
      
      pythonProcess.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Script extractor failed: ${stderr}`));
          return;
        }
        
        try {
          // Parse the output to extract script information
          const scriptInfo = this.parseScriptExtractorOutput(stdout);
          resolve(scriptInfo);
        } catch (error) {
          reject(new Error(`Failed to parse script extractor output: ${error.message}`));
        }
      });
      
      pythonProcess.on('error', (error) => {
        reject(new Error(`Failed to run script extractor: ${error.message}`));
      });
    });
  }

  /**
   * Parse output from Python script extractor
   */
  parseScriptExtractorOutput(output) {
    const lines = output.split('\n');
    let scriptAuthor = null;
    let scriptUrl = null;
    let resolvedPostId = null;
    let resolvedTitle = null;
    
    for (const line of lines) {
      if (line.includes('Script Author: u/')) {
        scriptAuthor = line.split('Script Author: u/')[1].trim();
      } else if (line.includes('-> Reddit post ')) {
        const match = line.match(/-> Reddit post (\w+)/);
        if (match) {
          resolvedPostId = match[1];
        }
      } else if (line.includes('Title: ')) {
        resolvedTitle = line.split('Title: ')[1].trim();
      } else if (line.includes('      - ')) {
        // This is likely a script URL from the linked post
        const url = line.split('      - ')[1].trim();
        if (url.includes('scriptbin.works') || url.includes('pastebin.com') || 
            url.includes('github.com') || url.includes('docs.google.com')) {
          scriptUrl = url;
        }
      }
    }
    
    if (scriptUrl) {
      return {
        url: scriptUrl,
        author: scriptAuthor,
        resolved_post_id: resolvedPostId,
        resolved_title: resolvedTitle
      };
    }
    
    return null;
  }

  /**
   * Enhanced preprocessing function with script resolution
   */
  async preprocessEnhanced(postData) {
    const { title, selftext, author, link_flair_text, post_id } = postData.reddit_data;
    
    // Get base preprocessing results
    const baseResult = this.originalPreprocessor.preprocess(postData);
    
    // Enhanced script information with URL resolution
    const enhancedScriptInfo = await this.extractEnhancedScriptInfo(
      selftext, 
      link_flair_text, 
      post_id
    );
    
    // Update the result with enhanced script info
    const enhancedResult = {
      ...baseResult,
      script: enhancedScriptInfo,
      enhancement_metadata: {
        script_resolution_attempted: this.enableScriptResolution,
        script_resolution_successful: !!enhancedScriptInfo.url && !!enhancedScriptInfo.resolution_info,
        indirect_reference_detected: !!enhancedScriptInfo.resolution_info,
        enhanced_at: new Date().toISOString()
      }
    };
    
    return enhancedResult;
  }

  /**
   * Batch process multiple posts with script resolution
   */
  async processPostsWithScriptResolution(postDataArray) {
    const results = [];
    
    for (const postData of postDataArray) {
      try {
        console.log(`🔄 Processing post ${postData.reddit_data.post_id}...`);
        const result = await this.preprocessEnhanced(postData);
        results.push(result);
        
        // Add delay to avoid overwhelming Reddit API
        await new Promise(resolve => setTimeout(resolve, 1000));
      } catch (error) {
        console.error(`❌ Error processing post ${postData.reddit_data.post_id}: ${error.message}`);
        results.push({
          error: error.message,
          post_id: postData.reddit_data.post_id,
          processed_at: new Date().toISOString()
        });
      }
    }
    
    return results;
  }

  /**
   * Update existing analysis files with resolved script URLs
   */
  async updateAnalysisWithScriptResolution(analysisFilePath) {
    try {
      // Load existing analysis
      const analysisData = JSON.parse(fs.readFileSync(analysisFilePath, 'utf8'));
      
      // Check if script resolution is needed
      if (analysisData.script && 
          analysisData.script.fillType === 'public' && 
          !analysisData.script.url &&
          analysisData.metadata && 
          analysisData.metadata.post_id) {
        
        console.log(`🔄 Attempting script resolution for ${analysisData.metadata.post_id}...`);
        
        // Try to resolve script URL
        const postId = analysisData.metadata.post_id;
        const indirectRef = { type: 'analysis_update', url: 'unknown' };
        
        try {
          const resolvedInfo = await this.resolveScriptUrl(postId, indirectRef);
          if (resolvedInfo) {
            // Update analysis with resolved script info
            analysisData.script.url = resolvedInfo.url;
            if (resolvedInfo.author) {
              analysisData.script.author = resolvedInfo.author;
            }
            analysisData.script.resolution_info = {
              resolved_via: 'post_analysis_update',
              resolved_post_id: resolvedInfo.resolved_post_id,
              resolved_title: resolvedInfo.resolved_title,
              resolved_at: new Date().toISOString()
            };
            
            // Save updated analysis
            fs.writeFileSync(analysisFilePath, JSON.stringify(analysisData, null, 2));
            console.log(`✅ Updated ${analysisFilePath} with resolved script URL: ${resolvedInfo.url}`);
            
            return true;
          }
        } catch (error) {
          console.warn(`⚠️ Script resolution failed for ${postId}: ${error.message}`);
        }
      }
      
      return false;
    } catch (error) {
      console.error(`❌ Error updating analysis file: ${error.message}`);
      return false;
    }
  }
}

// CLI usage
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log(`
Usage: node enhanced-reddit-preprocessor.js [command] [options]

Commands:
  preprocess <reddit_post.json>              Enhanced preprocessing with script resolution
  update-analysis <analysis_file.json>       Update existing analysis with script resolution
  batch-process <input_file.json>           Process multiple posts from JSON array
  
Options:
  --no-script-resolution                     Disable script URL resolution
  --script-extractor <path>                  Path to Python script extractor
  --output <file>                           Output file for results

Examples:
  node enhanced-reddit-preprocessor.js preprocess reddit_data/alekirser/1amzk7q.json
  node enhanced-reddit-preprocessor.js update-analysis analysis_results/1mhsvf0_*.json
  node enhanced-reddit-preprocessor.js batch-process posts_array.json --output enhanced_results.json
`);
    process.exit(1);
  }

  const command = args[0];
  const inputPath = args[1];
  const outputIndex = args.indexOf("--output");
  const outputPath = outputIndex !== -1 && args[outputIndex + 1] ? args[outputIndex + 1] : null;
  const noScriptResolution = args.includes("--no-script-resolution");
  const scriptExtractorIndex = args.indexOf("--script-extractor");
  const scriptExtractorPath = scriptExtractorIndex !== -1 && args[scriptExtractorIndex + 1] ? args[scriptExtractorIndex + 1] : undefined;

  const options = {
    enableScriptResolution: !noScriptResolution,
    scriptExtractorPath
  };

  const preprocessor = new EnhancedRedditPreprocessor(options);

  try {
    let result;

    switch (command) {
      case 'preprocess':
        if (!inputPath) {
          console.error('❌ Input file required for preprocess command');
          process.exit(1);
        }
        const postData = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
        result = await preprocessor.preprocessEnhanced(postData);
        break;

      case 'update-analysis':
        if (!inputPath) {
          console.error('❌ Analysis file required for update-analysis command');
          process.exit(1);
        }
        const updated = await preprocessor.updateAnalysisWithScriptResolution(inputPath);
        console.log(updated ? '✅ Analysis updated successfully' : 'ℹ️ No updates needed');
        return;

      case 'batch-process':
        if (!inputPath) {
          console.error('❌ Input file required for batch-process command');
          process.exit(1);
        }
        const postsArray = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
        result = await preprocessor.processPostsWithScriptResolution(postsArray);
        break;

      default:
        console.error(`❌ Unknown command: ${command}`);
        process.exit(1);
    }

    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
      console.log(`💾 Results saved to ${outputPath}`);
    } else {
      console.log(JSON.stringify(result, null, 2));
    }

  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = EnhancedRedditPreprocessor;