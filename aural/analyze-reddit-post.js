#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

/**
 * Enhanced Reddit Post Analyzer with Script URL Resolution
 * 
 * Extends the original analyzer to use the enhanced preprocessor
 * that can resolve indirect script references.
 */
class EnhancedRedditPostAnalyzer {
  constructor(options = {}) {
    this.lmStudioUrl =
      options.lmStudioUrl || "http://localhost:1234/v1/chat/completions";
    this.model = options.model || "local-model";
    this.enableScriptResolution = options.enableScriptResolution !== false;
  }

  /**
   * Creates a simplified prompt using enhanced preprocessed data
   */
  createSimplifiedPrompt(postData, enhancedPreprocessedData) {
    const { title, selftext, author, link_flair_text } = postData.reddit_data;
    
    // Build script info summary including resolution details
    let scriptSummary = `${enhancedPreprocessedData.script.fillType} by ${enhancedPreprocessedData.script.author}`;
    if (enhancedPreprocessedData.script.url) {
      scriptSummary += ` (URL: ${enhancedPreprocessedData.script.url})`;
    }
    if (enhancedPreprocessedData.script.resolution_info) {
      scriptSummary += ` [Resolved via ${enhancedPreprocessedData.script.resolution_info.resolved_via}]`;
    }
    
    return `Analyze this Reddit post from r/gonewildaudio. 

CRITICAL: Your response must be ONLY valid JSON. Do not include reasoning or explanations.

POSTER USERNAME: ${author}
TITLE: ${title}
FLAIR: ${link_flair_text || 'No flair'}

POST CONTENT:
${selftext}

ENHANCED PREPROCESSED DATA (use this as guidance):
- Performers detected: ${enhancedPreprocessedData.performers.count} (${enhancedPreprocessedData.performers.primary} + ${enhancedPreprocessedData.performers.additional.join(', ')})
- Script info: ${scriptSummary}
- Audio versions: ${enhancedPreprocessedData.audio_versions.length} version(s) detected
- Script resolution: ${enhancedPreprocessedData.enhancement_metadata.script_resolution_successful ? 'Successful' : 'Not needed/failed'}

Focus only on:
1. Series information (part of series, sequels, prequels)
2. Analysis notes about the content and context
3. Confidence assessment for series detection

Return JSON with this structure:
{
  "series": {
    "isPartOfSeries": <boolean>,
    "hasPrequels": <boolean>, 
    "hasSequels": <boolean>,
    "seriesName": "<name if mentioned>",
    "partNumber": <number or null>,
    "confidence": "<high|medium|low>"
  },
  "analysis_notes": "<brief observations about the post content>"
}`;
  }

  /**
   * Creates version naming prompt for generating file/directory slugs
   */
  createVersionNamingPrompt(postData, audioVersions) {
    const { title, selftext, post_id } = postData.reddit_data;
    
    return `You are a file naming expert. Analyze this Reddit post and its audio versions to create optimal flat file naming within a single directory.

CRITICAL: Your response must be ONLY valid JSON. No reasoning or explanations.

POST: ${title}
CONTENT: ${selftext}
POST_ID: ${post_id}

AUDIO VERSIONS DETECTED:
${audioVersions.map((v, i) => `${i+1}. ${v.version_name || 'Version ' + (i+1)}: ${v.description || ''} | URLs: ${v.urls.map(u => u.url).join(', ')}`).join('\n')}

NAMING PATTERN: {post_id}_{release_slug}_-_{version_slug}.{ext}

RELEASE SLUG RULES:
- Extract core title, remove brackets and gender tags
- Convert to lowercase snake_case
- Maximum 40 characters
- Examples: "sweet_southern_hospitality", "anniversary_date", "let_me_cater_to_you"

VERSION SLUG RULES:
1. **Multi-scenario projects** (8+ audios, different stories):
   - Use scenario names: "intro", "learning_to_ride_horse", "southern_cookin"
   
2. **Gender variants** (F4M/F4F/M4F/M4M):
   - Use gender tags: "f4m", "f4f", "m4f", "m4m"
   
3. **Audio quality variants**:
   - "sfx + music" → "sfx_music"
   - "sfx + no music" → "sfx_no_music" 
   - "just vocals" → "vocals_only"
   - "with wet sounds" → "wet_sounds"
   
4. **Combined variants**: Combine with underscore
   - "f4m_sfx_music", "f4f_vocals_only"

5. **Single version**: Use primary gender tag or "default"

SANITIZATION:
- Lowercase only
- Replace spaces/punctuation with underscores
- Remove brackets, quotes, emojis
- Maximum 30 characters per version slug

Return JSON:
{
  "release_directory": "{post_id}_{release_slug}",
  "release_slug": "{sanitized_release_title}",
  "audio_files": [
    {
      "filename": "{post_id}_{release_slug}_-_{version_slug}.{ext}",
      "version_slug": "{sanitized_version_name}",
      "display_name": "{human_readable_version_name}",
      "detected_tags": ["{tag1}", "{tag2}"],
      "audio_urls": ["{url1}", "{url2}"],
      "metadata_file": "{post_id}_{release_slug}_-_{version_slug}.json"
    }
  ],
  "structure_type": "{multi_scenario|gender_variants|quality_variants|combined_variants|single_version}"
}`;
  }

  /**
   * Calls the local LLM API to analyze the post
   */
  async callLLM(prompt) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000);

      const response = await fetch(this.lmStudioUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.model,
          messages: [
            {
              role: "user",
              content: "Respond with valid JSON only. No reasoning. No explanations. No text outside JSON.\n\n" + prompt,
            },
          ],
          temperature: 0.1,
          max_tokens: 800
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.text();
        console.error('API Error Response:', response.status, response.statusText);
        console.error('Response data:', errorData);
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      return data.choices[0].message.content;
    } catch (error) {
      if (error.cause?.code === "ECONNREFUSED" || error.message?.includes("fetch failed")) {
        throw new Error(
          "Could not connect to LM Studio. Make sure LM Studio is running and serving on " +
            this.lmStudioUrl
        );
      }
      throw error;
    }
  }

  /**
   * Parses and validates the LLM response
   */
  parseResponse(responseText) {
    try {
      // Remove any reasoning tokens and other unwanted text
      let cleanText = responseText
        .replace(/<think>[\s\S]*?<\/think>/gi, '')
        .replace(/^[^{]*/, '') // Remove everything before first {
        .replace(/[^}]*$/, '') // Remove everything after last }
        .trim();
      
      // If we still don't have clean JSON, try to extract it
      if (!cleanText.startsWith('{')) {
        const jsonMatch = responseText.match(/\{[\s\S]*\}/);
        cleanText = jsonMatch ? jsonMatch[0] : responseText;
      }
      
      const jsonText = cleanText;

      const parsed = JSON.parse(jsonText);

      // For simplified parsing, just validate series and analysis_notes
      if (parsed.series === undefined) {
        throw new Error(`Missing required field: series`);
      }

      return parsed;
    } catch (error) {
      console.error("Failed to parse LLM response:", responseText);
      throw new Error("Invalid JSON response from LLM: " + error.message);
    }
  }

  /**
   * Parses and validates the version naming LLM response
   */
  parseVersionNamingResponse(responseText) {
    try {
      // Remove any reasoning tokens and other unwanted text
      let cleanText = responseText
        .replace(/<think>[\s\S]*?<\/think>/gi, '')
        .replace(/^[^{]*/, '') // Remove everything before first {
        .replace(/[^}]*$/, '') // Remove everything after last }
        .trim();
      
      // If we still don't have clean JSON, try to extract it
      if (!cleanText.startsWith('{')) {
        const jsonMatch = responseText.match(/\{[\s\S]*\}/);
        cleanText = jsonMatch ? jsonMatch[0] : responseText;
      }
      
      const jsonText = cleanText;

      const parsed = JSON.parse(jsonText);

      // Validate version naming response structure
      if (!parsed.release_directory || !parsed.release_slug || !parsed.audio_files) {
        throw new Error(`Missing required fields for version naming`);
      }

      return parsed;
    } catch (error) {
      console.error("Failed to parse version naming LLM response:", responseText);
      throw new Error("Invalid JSON response from LLM: " + error.message);
    }
  }

  /**
   * Generates version naming information using LLM
   */
  async generateVersionNaming(postData, audioVersions) {
    try {
      const prompt = this.createVersionNamingPrompt(postData, audioVersions);
      const llmResponse = await this.callLLM(prompt);
      const namingData = this.parseVersionNamingResponse(llmResponse);
      return namingData;
    } catch (error) {
      console.error(`Version naming generation failed: ${error.message}`);
      // Fallback to simple naming
      return this.generateFallbackNaming(postData, audioVersions);
    }
  }

  /**
   * Generates fallback naming when LLM fails
   */
  generateFallbackNaming(postData, audioVersions) {
    const postId = postData.reddit_data.post_id || postData.post_id;
    const title = postData.reddit_data.title || '';
    
    // Simple slug generation
    const releaseSlug = title
      .replace(/\[.*?\]/g, '') // Remove brackets
      .replace(/[^\w\s]/g, '') // Remove special chars
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_')
      .substring(0, 40);

    const audioFiles = audioVersions.map((version, index) => {
      const versionSlug = version.version_name 
        ? version.version_name.toLowerCase().replace(/\s+/g, '_').replace(/[^\w_]/g, '')
        : `version_${index + 1}`;
      
      return {
        filename: `${postId}_${releaseSlug}_-_${versionSlug}.m4a`,
        version_slug: versionSlug,
        display_name: version.version_name || `Version ${index + 1}`,
        detected_tags: [],
        audio_urls: version.urls.map(u => u.url),
        metadata_file: `${postId}_${releaseSlug}_-_${versionSlug}.json`
      };
    });

    return {
      release_directory: `${postId}_${releaseSlug}`,
      release_slug: releaseSlug,
      audio_files: audioFiles,
      structure_type: audioVersions.length > 1 ? 'multiple_versions' : 'single_version'
    };
  }

  /**
   * Analyzes a single Reddit post file with enhanced preprocessing
   */
  async analyzePost(filePath) {
    try {
      const postData = JSON.parse(fs.readFileSync(filePath, "utf8"));

      if (!postData.reddit_data || !postData.reddit_data.selftext) {
        throw new Error(
          "Post data missing required reddit_data.selftext field"
        );
      }

      console.log(`Analyzing post: ${postData.reddit_data.title}`);

      // Enhanced preprocessing with script resolution
      const EnhancedRedditPreprocessor = require('./enhanced-reddit-preprocessor.js');
      const preprocessor = new EnhancedRedditPreprocessor({
        enableScriptResolution: this.enableScriptResolution
      });
      const enhancedPreprocessedData = await preprocessor.preprocessEnhanced(postData);

      // Create simplified prompt with enhanced preprocessed data
      const prompt = this.createSimplifiedPrompt(postData, enhancedPreprocessedData);
      const llmResponse = await this.callLLM(prompt);
      const analysis = this.parseResponse(llmResponse);

      // Override with enhanced preprocessed data for accuracy
      analysis.performers = {
        ...enhancedPreprocessedData.performers,
        confidence: "high"
      };
      
      analysis.audio_versions = enhancedPreprocessedData.audio_versions;

      analysis.script = enhancedPreprocessedData.script;

      // Use series info from LLM or default from preprocessing
      if (analysis.series) {
        // LLM provided series analysis, keep it
      } else {
        // Fallback to preprocessed series data
        analysis.series = {
          ...enhancedPreprocessedData.series,
          confidence: "high"
        };
      }

      // Generate version naming information
      console.log(`Generating version naming for ${analysis.audio_versions.length} audio version(s)...`);
      const versionNaming = await this.generateVersionNaming(postData, analysis.audio_versions);
      
      // Enhance audio_versions with slug information
      if (versionNaming && versionNaming.audio_files) {
        analysis.audio_versions = analysis.audio_versions.map((version, index) => {
          const namingInfo = versionNaming.audio_files[index] || versionNaming.audio_files[0];
          return {
            ...version,
            slug: namingInfo ? namingInfo.version_slug : `version_${index + 1}`,
            filename: namingInfo ? namingInfo.filename : `${postData.post_id}_audio_${index + 1}.m4a`,
            metadata_file: namingInfo ? namingInfo.metadata_file : `${postData.post_id}_audio_${index + 1}.json`
          };
        });
      }

      // Add version naming metadata
      analysis.version_naming = versionNaming;

      // Add metadata including enhancement info
      analysis.metadata = {
        post_id: postData.post_id,
        username: postData.username,
        title: postData.reddit_data.title,
        date: postData.date,
        reddit_url: postData.reddit_url,
        analyzed_at: new Date().toISOString(),
        preprocessing_used: true,
        enhanced_preprocessing: true,
        script_resolution_enabled: this.enableScriptResolution,
        script_resolution_successful: enhancedPreprocessedData.enhancement_metadata.script_resolution_successful
      };

      // Add enhancement metadata
      analysis.enhancement_metadata = enhancedPreprocessedData.enhancement_metadata;

      return analysis;
    } catch (error) {
      throw new Error(`Failed to analyze ${filePath}: ${error.message}`);
    }
  }

  /**
   * Processes multiple post files in a directory
   */
  async analyzeDirectory(dirPath, outputPath = null) {
    const files = fs
      .readdirSync(dirPath)
      .filter((file) => file.endsWith(".json"))
      .map((file) => path.join(dirPath, file));

    const results = [];

    for (const file of files) {
      try {
        console.log(`Processing ${path.basename(file)}...`);
        const analysis = await this.analyzePost(file);
        results.push(analysis);

        // Small delay to avoid overwhelming the LLM and Reddit API
        await new Promise((resolve) => setTimeout(resolve, 2000));
      } catch (error) {
        console.error(`Error processing ${file}: ${error.message}`);
        results.push({
          error: error.message,
          file: file,
          analyzed_at: new Date().toISOString(),
        });
      }
    }

    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
      console.log(`Results saved to ${outputPath}`);
    }

    return results;
  }
}

// CLI usage
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log(`
Usage: node analyze-reddit-post.js <file_or_directory> [options]

Options:
  --output <path>          Output file for results (JSON)
  --url <url>             LM Studio API URL (default: http://localhost:1234/v1/chat/completions)
  --model <name>          Model name (default: local-model)
  --no-script-resolution  Disable script URL resolution
  --save-approved         Save result to llm_approved category in analysis storage
  --save-rejected         Save result to llm_rejected category in analysis storage
  --save-experimental     Save result to experimental category in analysis storage

Examples:
  node analyze-reddit-post.js reddit_data/alekirser/1amzk7q.json
  node analyze-reddit-post.js reddit_data/alekirser/ --output enhanced_analysis_results.json
  node analyze-reddit-post.js reddit_data/alekirser/1m9aefh*.json --save-approved --model mistralai/mistral-7b-instruct-v0.3
  node analyze-reddit-post.js reddit_data/BotanicalSpringVA/1mhsvf0*.json --no-script-resolution
`);
    process.exit(1);
  }

  const inputPath = args[0];
  const outputIndex = args.indexOf("--output");
  const urlIndex = args.indexOf("--url");
  const modelIndex = args.indexOf("--model");
  const saveApproved = args.includes("--save-approved");
  const saveRejected = args.includes("--save-rejected");
  const saveExperimental = args.includes("--save-experimental");
  const noScriptResolution = args.includes("--no-script-resolution");

  const options = {
    enableScriptResolution: !noScriptResolution
  };
  if (urlIndex !== -1 && args[urlIndex + 1]) {
    options.lmStudioUrl = args[urlIndex + 1];
  }
  if (modelIndex !== -1 && args[modelIndex + 1]) {
    options.model = args[modelIndex + 1];
  }

  const outputPath =
    outputIndex !== -1 && args[outputIndex + 1] ? args[outputIndex + 1] : null;

  const analyzer = new EnhancedRedditPostAnalyzer(options);

  try {
    const stats = fs.statSync(inputPath);
    let results;

    if (stats.isDirectory()) {
      results = await analyzer.analyzeDirectory(inputPath, outputPath);
    } else {
      results = await analyzer.analyzePost(inputPath);
      
      // Save to analysis storage if requested
      if (saveApproved || saveRejected || saveExperimental) {
        const { AnalysisStorage } = require('./create-analysis-directories.js');
        const storage = new AnalysisStorage();
        
        const originalPost = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
        const metadata = {
          analyzer: 'enhanced_llm_analysis_script',
          model: options.model || 'local-model',
          lm_studio_url: options.lmStudioUrl,
          type: 'automated_analysis_with_script_resolution',
          approved: saveApproved,
          rejected: saveRejected,
          experimental: saveExperimental,
          script_resolution_enabled: options.enableScriptResolution,
          script_resolution_successful: results.enhancement_metadata?.script_resolution_successful || false
        };
        
        storage.saveLLMAnalysis(results.metadata.post_id, results, metadata, originalPost);
        const status = saveApproved ? 'approved' : saveRejected ? 'rejected' : 'experimental';
        console.log(`✅ Saved enhanced LLM analysis (${status})`);
      }
      
      if (outputPath) {
        fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
        console.log(`Results saved to ${outputPath}`);
      } else {
        console.log(JSON.stringify(results, null, 2));
      }
    }

    console.log("Enhanced analysis complete!");
  } catch (error) {
    console.error("Error:", error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = EnhancedRedditPostAnalyzer;