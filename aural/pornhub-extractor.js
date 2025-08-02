#!/usr/bin/env node

/**
 * Pornhub Data Extractor - Node.js Version
 *
 * This script extracts audio/video files and metadata from Pornhub using yt-dlp.
 * It downloads files, extracts metadata, and organizes data similar to other extractors.
 *
 * Usage: node pornhub-extractor.js <url>
 *
 * Requirements:
 * 1. Install yt-dlp: https://github.com/yt-dlp/yt-dlp
 */

const { spawn } = require("child_process");
const fs = require("fs").promises;
const path = require("path");

class PornhubExtractor {
  constructor(outputDir = "pornhub_data") {
    this.outputDir = path.resolve(outputDir);
  }

  async ensureOutputDir(uploaderDir) {
    try {
      await fs.access(uploaderDir);
    } catch (error) {
      await fs.mkdir(uploaderDir, { recursive: true });
      console.log(`📁 Created output directory: ${uploaderDir}`);
    }
  }

  async checkYtDlp() {
    return new Promise((resolve) => {
      const ytDlp = spawn("yt-dlp", ["--version"]);
      
      ytDlp.on("close", (code) => {
        if (code === 0) {
          console.log("✅ yt-dlp is available");
          resolve(true);
        } else {
          console.error("❌ yt-dlp not found. Please install yt-dlp:");
          console.error("   https://github.com/yt-dlp/yt-dlp");
          resolve(false);
        }
      });

      ytDlp.on("error", () => {
        console.error("❌ yt-dlp not found. Please install yt-dlp:");
        console.error("   https://github.com/yt-dlp/yt-dlp");
        resolve(false);
      });
    });
  }

  async extractFromUrl(url) {
    console.log(`🎯 Processing: ${url}`);
    
    // yt-dlp command with the exact format you specified
    const outputTemplate = path.join(
      this.outputDir,
      "%(uploader)s",
      "%(upload_date>%Y-%m-%d)s - %(id)s - %(fulltitle)s.%(ext)s"
    );

    const args = [
      "--output", outputTemplate,
      "--write-info-json",
      url
    ];

    console.log("🚀 Starting yt-dlp extraction...");
    console.log(`📂 Output directory: ${this.outputDir}`);

    return new Promise((resolve, reject) => {
      const ytDlp = spawn("yt-dlp", args);
      
      let stdout = "";
      let stderr = "";

      ytDlp.stdout.on("data", (data) => {
        const output = data.toString();
        stdout += output;
        // Show yt-dlp progress
        if (output.includes("[download]") || output.includes("[info]")) {
          process.stdout.write(output);
        }
      });

      ytDlp.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      ytDlp.on("close", (code) => {
        if (code === 0) {
          console.log("✅ yt-dlp extraction completed successfully");
          resolve({ success: true, stdout: stdout });
        } else {
          console.error(`❌ yt-dlp failed with code ${code}`);
          console.error("STDERR:", stderr);
          reject(new Error(`yt-dlp failed: ${stderr}`));
        }
      });

      ytDlp.on("error", (error) => {
        console.error("❌ Failed to start yt-dlp:", error.message);
        reject(error);
      });
    });
  }

}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log("Usage: node pornhub-extractor.js <url>");
    console.log("Example: node pornhub-extractor.js https://www.pornhub.com/view_video.php?viewkey=123456");
    process.exit(1);
  }

  const url = args[0];
  const extractor = new PornhubExtractor();
  
  if (!(await extractor.checkYtDlp())) {
    process.exit(1);
  }
  
  try {
    const result = await extractor.extractFromUrl(url);
    console.log("\n✅ Extraction completed successfully");
  } catch (error) {
    console.error("\n❌ Extraction failed:", error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch(error => {
    console.error("❌ Fatal error:", error.message);
    process.exit(1);
  });
}

module.exports = { PornhubExtractor };