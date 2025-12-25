#!/usr/bin/env node

/**
 * LLM-based Metadata Extractor
 *
 * Uses a local LLM (via LM Studio) to extract structured metadata from Reddit posts.
 * This replaces the regex-based approach for more accurate and flexible extraction.
 */

class LLMMetadataExtractor {
  constructor(options = {}) {
    this.lmStudioUrl = options.lmStudioUrl || "http://localhost:1234/v1/chat/completions";
    this.model = options.model || "local-model";
  }

  /**
   * Creates the extraction prompt for the LLM
   */
  createExtractionPrompt(postData) {
    const { title, selftext, author, link_flair_text } = postData.reddit_data;

    return `Extract metadata from this Reddit post from r/gonewildaudio.

CRITICAL: Respond with ONLY valid JSON. No explanations.

POST AUTHOR (the person who posted): ${author}
TITLE: ${title}
FLAIR: ${link_flair_text || 'No flair'}

POST BODY:
${selftext}

EXTRACTION RULES:

1. PERFORMERS:
   - The post author is always the PRIMARY performer
   - Look for ADDITIONAL performers (collaborators) in:
     * Title patterns: "w Username", "w/ Username", "; w Username", "with Username"
     * Body patterns: "recorded with u/Username", "collab with u/Username", "live with u/Username"
     * Role assignments: "Character: ~ u/Username"
   - Do NOT include script authors as performers unless they also performed

2. SCRIPT AUTHOR:
   - Look for the person who WROTE the script (not performed):
     * Title patterns: "by Username", "by u/Username" (at end of title, after tags)
     * Body patterns: "Thanks to u/Username for... script", "script by u/Username", "Written by u/Username"
   - If flair is "OC" (Original Content), the script author is the post author
   - If it's a "Script Fill", someone else wrote the script

3. AUDIO URLS:
   - Extract all audio platform URLs: soundgasm.net, whyp.it, hotaudio.net
   - Identify version types from context (F4M, F4F, with SFX, without SFX, bloopers, etc.)

4. SCRIPT URL:
   - Look for links to: scriptbin.works, pastebin, google docs, reddit script posts
   - Pattern: [script](url) or direct mentions

Return this JSON structure:
{
  "performers": {
    "primary": "${author}",
    "additional": ["username1", "username2"],
    "notes": "explanation of how collaborators were identified"
  },
  "script": {
    "author": "username or null",
    "url": "script url or null",
    "fillType": "original|public|private",
    "notes": "explanation of script attribution"
  },
  "audioVersions": [
    {
      "name": "Main Audio",
      "description": "description",
      "urls": [{"platform": "Soundgasm", "url": "..."}],
      "versionType": "default|f4m|f4f|sfx|no_sfx|bloopers"
    }
  ],
  "series": {
    "isPartOfSeries": false,
    "seriesName": null,
    "partNumber": null
  }
}`;
  }

  /**
   * Calls the local LLM API
   */
  async callLLM(prompt) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000);

      const response = await fetch(this.lmStudioUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.model,
          messages: [
            {
              role: "system",
              content: "You are a metadata extraction assistant. Extract structured information from Reddit posts. Respond with valid JSON only."
            },
            {
              role: "user",
              content: prompt,
            },
          ],
          temperature: 0.1,
          max_tokens: 1500
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      return data.choices[0].message.content;
    } catch (error) {
      if (error.cause?.code === "ECONNREFUSED" || error.message?.includes("fetch failed")) {
        throw new Error(
          "Could not connect to LM Studio. Make sure LM Studio is running on " + this.lmStudioUrl
        );
      }
      throw error;
    }
  }

  /**
   * Parses the LLM response into structured data
   */
  parseResponse(responseText) {
    try {
      // Remove reasoning tokens and extract JSON
      let cleanText = responseText
        .replace(/<think>[\s\S]*?<\/think>/gi, '')
        .replace(/^[^{]*/, '')
        .replace(/[^}]*$/, '')
        .trim();

      if (!cleanText.startsWith('{')) {
        const jsonMatch = responseText.match(/\{[\s\S]*\}/);
        cleanText = jsonMatch ? jsonMatch[0] : responseText;
      }

      return JSON.parse(cleanText);
    } catch (error) {
      console.error("Failed to parse LLM response:", responseText);
      throw new Error("Invalid JSON response from LLM: " + error.message);
    }
  }

  /**
   * Extract metadata from a post using LLM
   */
  async extractMetadata(postData) {
    const prompt = this.createExtractionPrompt(postData);
    const response = await this.callLLM(prompt);
    const parsed = this.parseResponse(response);

    // Add extraction metadata
    parsed.extractionMetadata = {
      extractedAt: new Date().toISOString(),
      method: "llm",
      model: this.model
    };

    return parsed;
  }
}

// CLI usage
async function main() {
  const args = process.argv.slice(2);
  const fs = require('fs');

  if (args.length === 0) {
    console.log(`
Usage: node llm-metadata-extractor.js <reddit_post.json> [options]

Options:
  --url <url>     LM Studio API URL (default: http://localhost:1234/v1/chat/completions)
  --model <name>  Model name (default: local-model)

Extracts metadata using LLM:
- Performers (primary + collaborators)
- Script author and URL
- Audio versions and URLs
- Series information
`);
    process.exit(1);
  }

  const inputPath = args[0];
  const urlIndex = args.indexOf("--url");
  const modelIndex = args.indexOf("--model");

  const options = {};
  if (urlIndex !== -1 && args[urlIndex + 1]) {
    options.lmStudioUrl = args[urlIndex + 1];
  }
  if (modelIndex !== -1 && args[modelIndex + 1]) {
    options.model = args[modelIndex + 1];
  }

  try {
    const postData = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
    const extractor = new LLMMetadataExtractor(options);
    const result = await extractor.extractMetadata(postData);

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = LLMMetadataExtractor;
