#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const axios = require("axios");

/**
 * Analyzes Reddit post data using local LLM via LM Studio
 * to extract structured information about audio releases
 */
class RedditPostAnalyzer {
  constructor(options = {}) {
    this.lmStudioUrl =
      options.lmStudioUrl || "http://localhost:1234/v1/chat/completions";
    this.model = options.model || "local-model";
  }

  /**
   * Creates a structured prompt for the LLM to analyze the Reddit post
   */
  createAnalysisPrompt(postData) {
    const { title, selftext, author, comments } = postData.reddit_data;
    
    // Get first few comments for collaboration detection
    const topComments = comments ? comments.slice(0, 5).map(c => 
      `${c.author}: ${c.body.substring(0, 200)}${c.body.length > 200 ? '...' : ''}`
    ).join('\n\n') : 'No comments available';

    return `Analyze this Reddit post from r/gonewildaudio and extract specific information. 

CRITICAL: Your response must be ONLY valid JSON. Do not include <think> tags, reasoning, explanations, or any other text. Start directly with { and end with }.

POSTER USERNAME: ${author}
TITLE: ${title}

POST CONTENT:
${selftext}

TOP COMMENTS (for collaboration detection):
${topComments}

Please analyze and return JSON with this exact structure:
{
  "performers": {
    "count": <number>,
    "primary": "<poster username>",
    "additional": ["<username1>", "<username2>"],
    "confidence": "<high|medium|low>"
  },
  "alternatives": {
    "hasAlternatives": <boolean>,
    "versions": ["<version1>", "<version2>"],
    "description": "<brief description of alternatives>",
    "confidence": "<high|medium|low>"
  },
  "series": {
    "isPartOfSeries": <boolean>,
    "hasPrequels": <boolean>,
    "hasSequels": <boolean>,
    "seriesName": "<name if mentioned>",
    "partNumber": <number or null>,
    "confidence": "<high|medium|low>"
  },
  "script": {
    "url": "<direct URL to script if available, null if none>",
    "fillType": "<'original', 'public', 'private', or 'unknown'>",
    "author": "<username of script author>"
  },
  "analysis_notes": "<any additional relevant observations>"
}

CRITICAL SCRIPT ANALYSIS RULES - READ CAREFULLY:
1. URL IDENTIFICATION - Look for these EXACT patterns:
   - **"[script](URL)"** = script URL (extract this URL immediately!)
   - **"script:" followed by URL** = script URL 
   - **"[AUDIO HERE](URL)"** = audio URL (NOT script URL - ignore for script analysis)
   - **"audio:" followed by URL** = audio URL (NOT script URL - ignore for script analysis)
   - Script URLs are typically Reddit links (/r/gonewildaudio/comments/)
   - Audio URLs are typically soundgasm.net, whyp.it, hotaudio.net (DO NOT use these as script URLs)
   - For original content: script URL should be null (no separate script exists)

2. AUTHOR IDENTIFICATION - Search for these EXACT patterns in order:
   - **"[script](URL) by u/[username]"** = script author is [username] (most common!)
   - **"by u/[username]"** anywhere in post = script author is [username]
   - **"script by u/[username]"** = script author is [username]
   - **"written by u/[username]"** = script author is [username]
   - **"written privately by u/[username]"** = script author is [username], fillType "private", url null
   - **"script was written privately by u/[username]"** = script author is [username], fillType "private", url null
   - If NO "by u/[username]" found AND poster says "my script"/"I wrote"/"my own stuff"/"trying to write more" = script author is poster
   - If NO clear attribution = fillType "unknown", author: poster username

3. FILL TYPE CLASSIFICATION - CHECK IN ORDER:
   - **"written privately" OR "script was written privately"** = "private" (NO URL, script shared privately)
   - **"private fill"** = "private" (NO URL)
   - **Poster says "my script"/"I wrote"/"something I came up with"/"my own stuff"/"trying to write more"** = "original"
   - **Script URL present + "by u/[username]"** = "public" (public script with URL)
   - **"[Script Fill]" in title + script attribution** = "public" 
   - **No script reference AND no attribution** = "original" (likely original content)
   - **Cannot determine** = "unknown"

IMPORTANT: If "written privately" is mentioned, it's ALWAYS "private" fillType with url: null

4. ALTERNATIVE VERSION DETECTION:
   - Look for multiple audio links in post content
   - **"[AUDIO HERE](URL)"** = main audio
   - **"[bloopers](URL)" OR "(bloopers URL)"** = alternative version
   - **"bonus" audio links** = alternative version
   - **"with SFX" and "without SFX"** = alternative versions
   - Count distinct audio URLs for alternatives

STEP-BY-STEP ANALYSIS:
1. FIRST: Check for "written privately" - if found, set fillType "private" and url null immediately
2. IF NOT private: scan post for "[script](URL)" pattern - if found, extract URL 
3. Then, scan post for "by u/username" pattern - if found, that's the script author
4. Count only VOICE ACTORS (poster + collaborators), NOT script writers
5. Count alternatives by finding multiple audio links

EXAMPLE WALKTHROUGH:
1. Script Fill: "[script](https://reddit.com/r/gwa/comments/abc/) by u/CuteEmUp || [AUDIO HERE](https://soundgasm.net/u/alekirser/audio)"
   - Script URL: https://reddit.com/r/gwa/comments/abc/ (extract from [script](URL))
   - Script Author: CuteEmUp (from "by u/CuteEmUp")
   - Fill Type: public (has script URL + attribution)
   - DO NOT use the soundgasm URL as script URL

2. Original Content: "i'm trying to write more of my own stuff || [AUDIO HERE](https://soundgasm.net/audio)"
   - Script URL: null (no separate script exists)
   - Script Author: alekirser (poster wrote it)
   - Fill Type: original (poster created the content)

DOUBLE-CHECK YOUR WORK:
- Is the URL you extracted from [script](URL) or similar pattern?
- Does the author come from "by u/[username]" pattern?
- Are you distinguishing script links from audio links?

Focus on:
- Performers: Look for mentions of other voice actors, collaborations, or "with [username]"
  * Check title for collaboration indicators: "collab w/", "with u/", "& u/", "featuring"
  * Look for thanks/credits in post text: "thank you u/", "thanks to u/", "working with u/"
  * Check comments for collaborator responses (first comment often from collaborators)
  * Parse title tags like [FFF4M] = 3 female performers, [M4F] = 1 male performer
- Alternatives: Different versions (M4F/F4M, with/without SFX, different endings, etc.)
  * Look for multiple audio links with different descriptions
  * Check for "versions available", "also posted", "alternative", "bonus"
- Series: References to previous parts, sequels, ongoing storylines, numbered episodes
  * Look for "Part 1", "Episode 2", "continued from", "sequel to"
  * Check for mentions of previous posts or upcoming content

CONFIDENCE LEVELS - VERY IMPORTANT:
- **high**: When you have clear evidence FOR or AGAINST something
- **medium**: When evidence is unclear or ambiguous  
- **low**: Only when you cannot determine at all

EXAMPLES:
- No collaboration mentioned = "count": 1, "confidence": "high" (high confidence it's solo)
- No series references = "isPartOfSeries": false, "confidence": "high" (high confidence it's standalone)
- No alternative versions = "hasAlternatives": false, "confidence": "high" (high confidence single version)
- Unclear script attribution = "confidence": "medium" or "low"

PERFORMER DETECTION RULES:
1. Title Analysis: Extract performers from title patterns:
   - "collab w/ u/username" = collaboration with username
   - "collab w/ u/user1 & u/user2" = collaboration with user1 AND user2
   - "[FFF4M]" = 3 female performers total (count FFF = 3)
   - "& u/username" = additional performer
2. Post Content: Look for collaboration acknowledgments:
   - "thank you u/username" = likely collaborator
   - "working with u/username" = confirmed collaborator
3. Comments: Check first few comments for collaborator responses

PERFORMER COUNTING - CRITICAL:
- **ONLY count VOICE ACTORS, not script writers**
- Primary performer = poster (always 1) 
- Additional performers = voice actor collaborators ONLY (from "collab w/" patterns)
- Script authors are NOT performers (they write, don't perform audio)
- Title tags like [FFF4F] are just format indicators, count actual collaborators
- Total count = 1 + number of people mentioned in "collab w/" 
- Example: "collab w/ u/user1 & u/user2" = 1 poster + 2 collaborators = 3 total
- Example: "script by u/writer" = writer is NOT a performer, exclude from count

IMPORTANT: The poster's username is ${author}. When they refer to themselves with nicknames or signatures, always use their actual username for consistency.`;
  }

  /**
   * Creates a simplified prompt using preprocessed data
   */
  createSimplifiedPrompt(postData, preprocessedData) {
    const { title, selftext, author } = postData.reddit_data;
    
    return `Analyze this Reddit post from r/gonewildaudio. 

CRITICAL: Your response must be ONLY valid JSON. Do not include reasoning or explanations.

POSTER USERNAME: ${author}
TITLE: ${title}

POST CONTENT:
${selftext}

PREPROCESSED DATA (use this as guidance):
- Performers detected: ${preprocessedData.performers.count} (${preprocessedData.performers.primary} + ${preprocessedData.performers.additional.join(', ')})
- Script info: ${preprocessedData.script.fillType} by ${preprocessedData.script.author}
- Alternatives: ${preprocessedData.alternatives.hasAlternatives ? 'Yes' : 'No'}

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
   * Calls the local LLM API to analyze the post
   */
  async callLLM(prompt) {
    try {
      const response = await axios.post(
        this.lmStudioUrl,
        {
          model: this.model,
          messages: [
            {
              role: "user",
              content: "Respond with valid JSON only. No reasoning. No explanations. No text outside JSON.\n\n" + prompt,
            },
          ],
          temperature: 0.1,
          max_tokens: 800
        },
        {
          timeout: 300000,
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      return response.data.choices[0].message.content;
    } catch (error) {
      if (error.code === "ECONNREFUSED") {
        throw new Error(
          "Could not connect to LM Studio. Make sure LM Studio is running and serving on " +
            this.lmStudioUrl
        );
      }
      if (error.response) {
        console.error('API Error Response:', error.response.status, error.response.statusText);
        console.error('Response data:', error.response.data);
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
   * Analyzes a single Reddit post file with preprocessing
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

      // Preprocess to extract structured data
      const RedditPostPreprocessor = require('./preprocess-reddit-post.js');
      const preprocessor = new RedditPostPreprocessor();
      const preprocessedData = preprocessor.preprocess(postData);

      // Create simplified prompt with preprocessed data
      const prompt = this.createSimplifiedPrompt(postData, preprocessedData);
      const llmResponse = await this.callLLM(prompt);
      const analysis = this.parseResponse(llmResponse);

      // Override with preprocessed data for accuracy
      analysis.performers = {
        ...preprocessedData.performers,
        confidence: "high"
      };
      
      analysis.alternatives = {
        hasAlternatives: preprocessedData.alternatives.hasAlternatives,
        versions: preprocessedData.alternatives.versions,
        description: preprocessedData.alternatives.hasAlternatives ? 
          preprocessedData.alternatives.versions.join(" and ") : "Single version audio",
        confidence: "high"
      };

      analysis.script = preprocessedData.script;

      // Use series info from LLM or default from preprocessing
      if (analysis.series) {
        // LLM provided series analysis, keep it
      } else {
        // Fallback to preprocessed series data
        analysis.series = {
          ...preprocessedData.series,
          confidence: "high"
        };
      }

      // Add metadata
      analysis.metadata = {
        post_id: postData.post_id,
        username: postData.username,
        title: postData.reddit_data.title,
        date: postData.date,
        reddit_url: postData.reddit_url,
        analyzed_at: new Date().toISOString(),
        preprocessing_used: true
      };

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

        // Small delay to avoid overwhelming the LLM
        await new Promise((resolve) => setTimeout(resolve, 1000));
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
  --output <path>        Output file for results (JSON)
  --url <url>           LM Studio API URL (default: http://localhost:1234/v1/chat/completions)
  --model <name>        Model name (default: local-model)
  --save-approved       Save result to llm_approved category in analysis storage
  --save-rejected       Save result to llm_rejected category in analysis storage
  --save-experimental   Save result to experimental category in analysis storage

Examples:
  node analyze-reddit-post.js reddit_data/alekirser/1amzk7q.json
  node analyze-reddit-post.js reddit_data/alekirser/ --output analysis_results.json
  node analyze-reddit-post.js reddit_data/alekirser/1m9aefh*.json --save-approved --model mistralai/mistral-7b-instruct-v0.3
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

  const options = {};
  if (urlIndex !== -1 && args[urlIndex + 1]) {
    options.lmStudioUrl = args[urlIndex + 1];
  }
  if (modelIndex !== -1 && args[modelIndex + 1]) {
    options.model = args[modelIndex + 1];
  }

  const outputPath =
    outputIndex !== -1 && args[outputIndex + 1] ? args[outputIndex + 1] : null;

  const analyzer = new RedditPostAnalyzer(options);

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
          analyzer: 'llm_analysis_script',
          model: options.model || 'local-model',
          lm_studio_url: options.lmStudioUrl,
          type: 'automated_analysis',
          approved: saveApproved,
          rejected: saveRejected,
          experimental: saveExperimental
        };
        
        storage.saveLLMAnalysis(results.metadata.post_id, results, metadata, originalPost);
        const status = saveApproved ? 'approved' : saveRejected ? 'rejected' : 'experimental';
        console.log(`✅ Saved LLM analysis (${status})`);
      }
      
      if (outputPath) {
        fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
        console.log(`Results saved to ${outputPath}`);
      } else {
        console.log(JSON.stringify(results, null, 2));
      }
    }

    console.log("Analysis complete!");
  } catch (error) {
    console.error("Error:", error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = RedditPostAnalyzer;
