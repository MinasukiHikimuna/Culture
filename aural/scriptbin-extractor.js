#!/usr/bin/env node

/**
 * ScriptBin.works Data Extractor - Node.js Version
 *
 * This script extracts adult audio scripts from scriptbin.works using Playwright.
 * It handles the terms agreement page and extracts both metadata and script content.
 *
 * Requirements:
 * 1. Install dependencies: npm install
 * 2. Install browser: npm run install-playwright
 */

const { chromium } = require("playwright");
const cheerio = require("cheerio");
const fs = require("fs").promises;
const path = require("path");
const { Command } = require("commander");

class ScriptBinExtractor {
  constructor(outputDir = "scriptbin_data") {
    this.outputDir = path.resolve(outputDir);
    this.requestDelay = 2000; // Milliseconds between requests
    this.lastRequestTime = 0;

    // Playwright setup
    this.browser = null;
    this.page = null;
  }

  async setupPlaywright(headless = true) {
    try {
      console.log("🚀 Starting Playwright browser...");
      this.browser = await chromium.launch({ headless });
      this.page = await this.browser.newPage();

      console.log("✅ Playwright browser initialized successfully");
    } catch (error) {
      console.error("❌ Failed to initialize Playwright:", error.message);
      console.log('💡 Run "npm run install-playwright" to install browser');
      throw error;
    }
  }

  async closeBrowser() {
    if (this.browser) {
      await this.browser.close();
      console.log("🔧 Playwright browser closed");
    }
  }

  async rateLimit() {
    const currentTime = Date.now();
    const timeSinceLastRequest = currentTime - this.lastRequestTime;

    if (timeSinceLastRequest < this.requestDelay) {
      const sleepTime = this.requestDelay - timeSinceLastRequest;
      await new Promise((resolve) => setTimeout(resolve, sleepTime));
    }

    this.lastRequestTime = Date.now();
  }

  async handleTermsAgreement(url) {
    await this.rateLimit();

    try {
      await this.page.goto(url, { waitUntil: "networkidle" });

      // Check if we're on the terms agreement page
      if (this.page.url().includes("agree-terms")) {
        console.log("📋 Terms agreement page detected, clicking Agree...");

        try {
          // Wait for and click the Agree button
          const agreeButton = await this.page.waitForSelector(
            'input[name="agree"][value="Agree"]',
            { timeout: 5000 }
          );
          await agreeButton.click();

          // Wait for navigation away from terms page
          await this.page.waitForFunction(
            () => !window.location.href.includes("agree-terms"),
            { timeout: 10000 }
          );

          console.log(
            `✅ Successfully agreed to terms, redirected to: ${this.page.url()}`
          );
        } catch (agreeError) {
          console.log("⚠️ Could not find Agree button, continuing anyway...");
        }
      }

      // Wait for script content to load
      try {
        await this.page.waitForSelector(
          '.script-text-real, h3, p:has-text("words")',
          { timeout: 10000 }
        );
        await this.page.waitForTimeout(2000); // Additional wait for dynamic content
        console.log("✅ Script content loaded successfully");
      } catch (e) {
        console.warn(
          "⚠️ Script content may not have fully loaded, continuing..."
        );
      }

      return this.page.url();
    } catch (error) {
      console.error(`❌ Error handling page load: ${error.message}`);
      return url;
    }
  }

  extractScriptMetadata($, url) {
    const metadata = {
      url,
      extracted_at: new Date().toISOString(),
    };

    // Extract username from URL first (more reliable)
    const usernameMatch = url.match(/\/u\/([^\/]+)/);
    if (usernameMatch) {
      metadata.username = usernameMatch[1];
    }

    // Extract title from the specific span structure
    const titleElement = $("span.title-and-tags span").first();
    if (titleElement.length) {
      metadata.title = titleElement.text().trim();
    }
    
    // Extract tags from the script-audience span
    const tagsElement = $("span.script-audience").first();
    if (tagsElement.length) {
      metadata.tags = tagsElement.text().trim();
    }

    // Extract author from the breadcrumb (fallback if username not in URL)
    const authorLink = $('a[href*="/u/"]').first();
    if (authorLink.length) {
      const authorFromLink = authorLink.text().replace("‹ ", "").trim();
      metadata.author = authorFromLink;
      metadata.author_url = new URL(authorLink.attr("href"), url).href;

      // Use author from link if username wasn't extracted from URL
      if (!metadata.username) {
        metadata.username = authorFromLink;
      }
    }

    // Extract performers/listeners info - handle <br> tags properly
    $("p").each((_, element) => {
      const $element = $(element);
      const html = $element.html();
      
      if (html && html.includes("Performers:") && html.includes("Listeners:")) {
        // Split by <br> tag to handle the line break
        const parts = html.split(/<br\s*\/?>/i);
        
        parts.forEach(part => {
          // Clean the part and get text content safely
          const cleanPart = part.replace(/(<([^>]+)>)/gi, "").trim();
          
          if (cleanPart.startsWith("Performers:")) {
            metadata.performers = cleanPart.replace("Performers:", "").trim();
          } else if (cleanPart.startsWith("Listeners:")) {
            metadata.listeners = cleanPart.replace("Listeners:", "").trim();
          }
        });
      }
    });

    // Extract word count and character count
    const statsText = $('p:contains("words"):contains("characters")').text();
    if (statsText) {
      const wordMatch = statsText.match(/(\d+)\s+words/);
      const charMatch = statsText.match(/(\d+)\s+characters/);

      if (wordMatch) {
        metadata.word_count = parseInt(wordMatch[1]);
      }
      if (charMatch) {
        metadata.character_count = parseInt(charMatch[1]);
      }
    }

    // Extract short link
    const shortLinkText = $('p:contains("Short link:")').text();
    if (shortLinkText) {
      const shortLinkMatch = shortLinkText.match(
        /https:\/\/scriptbin\.works\/s\/\w+/
      );
      if (shortLinkMatch) {
        metadata.short_link = shortLinkMatch[0];
      }
    }

    // Try to extract the script ID from URL
    const scriptIdMatch = url.match(/\/([^/]+)$/);
    if (scriptIdMatch) {
      metadata.script_id = scriptIdMatch[1];
    }

    return metadata;
  }

  extractScriptContent($) {
    const scriptLines = [];

    // Target the specific script container based on the HTML structure
    const scriptContainer = $(".script-text-real");

    if (scriptContainer.length) {
      console.log("✅ Found script container, extracting content...");

      // Extract from .line-raw divs within the script container
      scriptContainer.find(".line-raw").each((_, element) => {
        const $element = $(element);
        const text = $element.text().trim();

        // Skip blank lines (marked with &nbsp; or very short)
        if (
          text.length < 2 ||
          text === "\u00A0" ||
          $element.attr("data-isblank") === "yes"
        ) {
          return;
        }

        scriptLines.push(text);
      });

      // If line-raw approach didn't work, try direct text extraction
      if (scriptLines.length === 0) {
        const allText = scriptContainer.text().trim();
        if (allText) {
          // Split by common line breaks and clean up
          const lines = allText
            .split(/\n+/)
            .map((line) => line.trim())
            .filter((line) => line.length > 2);
          scriptLines.push(...lines);
        }
      }
    }

    // Fallback: look for other potential script containers
    if (scriptLines.length === 0) {
      console.log(
        "⚠️ No content in script-text-real, trying fallback methods..."
      );

      // Try pre elements that might contain script text
      $("pre").each((_, element) => {
        const $element = $(element);
        const text = $element.text().trim();

        if (text.length > 50) {
          // Substantial content
          const lines = text
            .split(/\n+/)
            .map((line) => line.trim())
            .filter((line) => line.length > 2);
          if (lines.length > 5) {
            // Looks like script content
            scriptLines.push(...lines);
          }
        }
      });

      // Last resort: look for divs with substantial dialogue-like content
      if (scriptLines.length === 0) {
        $("div").each((_, element) => {
          const $element = $(element);
          const text = $element.text().trim();

          // Skip common metadata patterns
          const skipPatterns = [
            "performers:",
            "listeners:",
            "words",
            "characters",
            "short link:",
            "show line numbers",
            "font size:",
            "additional width:",
            "scriptbin",
            "copyright",
            "log in with reddit",
            "agree below",
            "legal age",
            "fictional depictions",
            "consensually",
            "generated in",
            "site:",
            "individual works",
            "‹",
            "prompter",
            "script fill",
          ];

          const lowerText = text.toLowerCase();
          const isMetadata = skipPatterns.some((pattern) =>
            lowerText.includes(pattern)
          );

          if (!isMetadata && text.length > 20 && text.length < 500) {
            // Check if this looks like dialogue or stage direction
            const hasDialogueMarkers =
              text.includes("(") ||
              text.includes(":") ||
              text.includes("<") ||
              text.includes("[") ||
              /^[A-Z]/.test(text) ||
              text.includes("...");

            if (hasDialogueMarkers && !scriptLines.includes(text)) {
              scriptLines.push(text);
            }
          }
        });
      }
    }

    console.log(`📄 Extracted ${scriptLines.length} script lines`);
    return scriptLines.slice(0, 500); // Reasonable limit for script length
  }

  async getScriptData(url) {
    try {
      console.log(`🌐 Fetching script from: ${url}`);

      // Handle terms agreement if needed
      const finalUrl = await this.handleTermsAgreement(url);

      // Get page source after JavaScript execution
      const pageSource = await this.page.content();
      const $ = cheerio.load(pageSource);

      // Extract metadata
      const metadata = this.extractScriptMetadata($, finalUrl);

      // Extract script content
      const scriptContent = this.extractScriptContent($);

      if (!scriptContent || scriptContent.length === 0) {
        console.warn("⚠️ No script content found");
        return null;
      }

      const scriptData = {
        ...metadata,
        script_content: scriptContent,
        content_preview:
          scriptContent.slice(0, 3).join(" ").substring(0, 200) +
          (scriptContent.join(" ").length > 200 ? "..." : ""),
        html_backup_saved: true
      };

      // Save HTML backup
      await this.saveHtmlBackup(scriptData, pageSource);

      console.log(
        `✅ Successfully extracted script: ${metadata.title || "Unknown Title"}`
      );
      console.log(
        `📊 Content: ${scriptContent.length} lines, ${
          metadata.word_count || "unknown"
        } words`
      );

      return scriptData;
    } catch (error) {
      console.error(`❌ Error extracting script from ${url}: ${error.message}`);
      return null;
    }
  }

  async ensureOutputDir() {
    try {
      await fs.mkdir(this.outputDir, { recursive: true });
    } catch (error) {
      // Directory might already exist, ignore error
    }
  }

  async saveIndividualScript(scriptData) {
    // Use username first, then author, then fallback
    const username = scriptData.username || scriptData.author || "unknown";
    const cleanUsername = username.replace(/\s+/g, "_");
    const scriptId = scriptData.script_id || "unknown";

    // Create username directory
    const userDir = path.join(this.outputDir, cleanUsername);
    await fs.mkdir(userDir, { recursive: true });

    // Save script as JSON
    const filename = `${scriptId}.json`;
    const filepath = path.join(userDir, filename);

    try {
      await fs.writeFile(filepath, JSON.stringify(scriptData, null, 2), "utf8");
      console.log(`💾 Saved individual script to ${filepath}`);
    } catch (error) {
      console.error(
        `❌ Error saving individual script ${scriptId}: ${error.message}`
      );
    }
  }

  async saveHtmlBackup(scriptData, pageSource) {
    // Use username first, then author, then fallback
    const username = scriptData.username || scriptData.author || "unknown";
    const cleanUsername = username.replace(/\s+/g, "_");
    const scriptId = scriptData.script_id || "unknown";

    // Create username directory
    const userDir = path.join(this.outputDir, cleanUsername);
    await fs.mkdir(userDir, { recursive: true });

    // Save HTML backup
    const htmlFilename = `${scriptId}.html`;
    const htmlFilepath = path.join(userDir, htmlFilename);

    try {
      await fs.writeFile(htmlFilepath, pageSource, "utf8");
      console.log(`💾 Saved HTML backup to ${htmlFilepath}`);
    } catch (error) {
      console.error(
        `❌ Error saving HTML backup ${scriptId}: ${error.message}`
      );
    }
  }

  async saveToJson(data, filename) {
    if (!data || data.length === 0) {
      console.warn("⚠️ No data to save");
      return;
    }

    const filepath = path.join(this.outputDir, filename);

    try {
      await fs.writeFile(filepath, JSON.stringify(data, null, 2), "utf8");
      console.log(`💾 Saved ${data.length} entries to ${filepath}`);
    } catch (error) {
      console.error(`❌ Error saving to JSON: ${error.message}`);
    }
  }

  async saveToCSV(data, filename) {
    if (!data || data.length === 0) {
      console.warn("⚠️ No data to save");
      return;
    }

    const filepath = path.join(this.outputDir, filename);

    try {
      // Flatten script_content for CSV
      const flattenedData = data.map((entry) => {
        const flattened = { ...entry };
        if (flattened.script_content) {
          flattened.script_content = flattened.script_content.join("\n");
        }
        return flattened;
      });

      // Get all columns
      const allColumns = new Set();
      flattenedData.forEach((entry) => {
        Object.keys(entry).forEach((key) => allColumns.add(key));
      });

      const columns = Array.from(allColumns).sort();

      // Create CSV content
      const csvHeader = columns.join(",");
      const csvRows = flattenedData.map((entry) => {
        return columns
          .map((col) => {
            const value = entry[col] || "";
            // Escape commas and quotes in CSV
            const escaped = String(value).replace(/"/g, '""');
            return `"${escaped}"`;
          })
          .join(",");
      });

      const csvContent = [csvHeader, ...csvRows].join("\n");
      await fs.writeFile(filepath, csvContent, "utf8");
      console.log(`💾 Saved ${data.length} entries to ${filepath}`);
    } catch (error) {
      console.error(`❌ Error saving to CSV: ${error.message}`);
    }
  }

  async extractFromUrls(urls, maxScripts = null) {
    console.log(`🚀 Starting ScriptBin extraction for ${urls.length} URLs...`);

    const extractedData = [];
    const failedUrls = [];

    // Apply limit if specified
    const urlsToProcess = maxScripts ? urls.slice(0, maxScripts) : urls;

    if (maxScripts && urls.length > maxScripts) {
      console.log(
        `📊 Processing ${urlsToProcess.length} URLs (limited by max-scripts=${maxScripts})`
      );
    }

    for (let i = 0; i < urlsToProcess.length; i++) {
      const url = urlsToProcess[i];
      console.log(
        `📥 Processing script ${i + 1}/${urlsToProcess.length}: ${url}`
      );

      const scriptData = await this.getScriptData(url);
      if (scriptData) {
        extractedData.push(scriptData);
        await this.saveIndividualScript(scriptData);
      } else {
        failedUrls.push(url);
      }
    }

    console.log(`\n📊 Extraction Summary:`);
    console.log(`✅ Successfully processed: ${extractedData.length}`);
    console.log(`❌ Failed: ${failedUrls.length}`);

    // Save failed URLs if any
    if (failedUrls.length > 0) {
      const timestamp =
        new Date().toISOString().replace(/[:.]/g, "-").split("T")[0] +
        "_" +
        new Date().toTimeString().slice(0, 8).replace(/:/g, "");
      await this.saveToJson(failedUrls, `failed_urls_${timestamp}.json`);
    }

    return extractedData;
  }
}

async function main() {
  const program = new Command();

  program
    .name("scriptbin-extractor")
    .description("Extract scripts from scriptbin.works")
    .version("1.0.0")
    .argument("[urls...]", "ScriptBin.works URLs to extract")
    .option("-o, --output <dir>", "Output directory", "scriptbin_data")
    .option(
      "-m, --max-scripts <number>",
      "Maximum number of scripts to process",
      parseInt
    )
    .option(
      "-d, --delay <number>",
      "Delay between requests in milliseconds",
      parseInt,
      2000
    )
    .option("-f, --url-file <file>", "File containing URLs (one per line)")
    .parse();

  const options = program.opts();
  let urls = program.args;

  try {
    // Get URLs from file if specified
    if (options.urlFile) {
      const urlFile = path.resolve(options.urlFile);
      try {
        const fileContent = await fs.readFile(urlFile, "utf8");
        urls = fileContent
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line && !line.startsWith("#"));
        console.log(`📂 Loaded ${urls.length} URLs from ${options.urlFile}`);
      } catch (error) {
        console.error(`❌ URL file not found: ${options.urlFile}`);
        process.exit(1);
      }
    }

    if (!urls || urls.length === 0) {
      console.error("❌ No URLs provided");
      program.help();
    }

    // Initialize extractor
    const extractor = new ScriptBinExtractor(options.output);
    extractor.requestDelay = options.delay;

    await extractor.ensureOutputDir();
    await extractor.setupPlaywright();

    // Extract scripts
    const extractedData = await extractor.extractFromUrls(
      urls,
      options.maxScripts
    );

    console.log(`\n🎉 Extraction complete!`);
    console.log(`📁 Results saved to: ${extractor.outputDir}`);
    console.log(`📊 Processed ${extractedData.length} scripts successfully`);

    // Close browser
    await extractor.closeBrowser();
  } catch (error) {
    if (error.name === "CommanderError") {
      // Commander error, already handled
      process.exit(1);
    }

    console.error(`\n❌ Error: ${error.message}`);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on("SIGINT", () => {
  console.log("\n⏹️ Extraction interrupted by user");
  process.exit(0);
});

if (require.main === module) {
  main().catch((error) => {
    console.error("❌ Unhandled error:", error);
    process.exit(1);
  });
}

module.exports = { ScriptBinExtractor };
