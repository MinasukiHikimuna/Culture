#!/usr/bin/env node

/**
 * Reset Post Script
 *
 * Finds and optionally deletes all files associated with a Reddit post ID,
 * allowing it to be re-processed from scratch.
 *
 * Usage:
 *   node reset-post.js <post_id> [post_id...] [--execute]
 *
 * By default runs in dry-run mode showing what would be deleted.
 * Use --execute to actually delete the files.
 */

const fs = require('fs').promises;
const path = require('path');

const AURAL_STASH_PATH = '/Volumes/Culture 1/Aural_Stash';
const DATA_DIR = 'data';
const ANALYSIS_DIR = 'analysis_results';
const EXTRACTED_DATA_DIR = 'extracted_data/reddit';

async function findSourcePostFile(postId) {
  // Search extracted_data/reddit/<author>/<postId>_*.json
  try {
    const authors = await fs.readdir(EXTRACTED_DATA_DIR);
    for (const author of authors) {
      const authorDir = path.join(EXTRACTED_DATA_DIR, author);
      const stat = await fs.stat(authorDir);
      if (!stat.isDirectory()) continue;

      const files = await fs.readdir(authorDir);
      for (const f of files) {
        if (f.startsWith(postId + '_') && f.endsWith('.json') && !f.includes('_enriched')) {
          return path.join(authorDir, f);
        }
      }
    }
  } catch { /* dir doesn't exist */ }
  return null;
}

async function findFilesForPost(postId) {
  const files = {
    analysisFiles: [],
    releaseDir: null,
    auralStashFiles: [],
    processedEntry: false
  };

  // 1. Find analysis files matching the post ID
  try {
    const analysisFiles = await fs.readdir(ANALYSIS_DIR);
    for (const f of analysisFiles) {
      if (f.startsWith(postId + '_') && f.endsWith('_analysis.json')) {
        files.analysisFiles.push(path.join(ANALYSIS_DIR, f));
      }
    }
  } catch { /* dir doesn't exist */ }

  // 2. Find release directory - search through all authors
  const releasesDir = path.join(DATA_DIR, 'releases');
  try {
    const authors = await fs.readdir(releasesDir);
    for (const author of authors) {
      const authorDir = path.join(releasesDir, author);
      const stat = await fs.stat(authorDir);
      if (!stat.isDirectory()) continue;

      const releases = await fs.readdir(authorDir);
      for (const release of releases) {
        if (release.startsWith(postId + '_')) {
          files.releaseDir = path.join(authorDir, release);
          break;
        }
      }
      if (files.releaseDir) break;
    }
  } catch { /* dir doesn't exist */ }

  // 3. Find Aural_Stash MP4 files containing the post ID
  try {
    const stashFiles = await fs.readdir(AURAL_STASH_PATH);
    for (const f of stashFiles) {
      if (f.includes(postId) && f.endsWith('.mp4')) {
        files.auralStashFiles.push(path.join(AURAL_STASH_PATH, f));
      }
    }
  } catch { /* dir doesn't exist */ }

  // 4. Check processed_posts.json
  try {
    const processed = JSON.parse(
      await fs.readFile(path.join(DATA_DIR, 'processed_posts.json'), 'utf8')
    );
    if (processed.posts && processed.posts[postId]) {
      files.processedEntry = true;
    }
  } catch { /* file doesn't exist */ }

  return files;
}

async function deleteFiles(files, postId, dryRun) {
  const action = dryRun ? 'Would delete' : 'Deleting';
  let count = 0;

  // Analysis files
  for (const f of files.analysisFiles) {
    console.log(`  ${action}: ${f}`);
    if (!dryRun) await fs.unlink(f);
    count++;
  }

  // Release directory
  if (files.releaseDir) {
    console.log(`  ${action}: ${files.releaseDir}/`);
    if (!dryRun) await fs.rm(files.releaseDir, { recursive: true });
    count++;
  }

  // Aural_Stash files
  for (const f of files.auralStashFiles) {
    console.log(`  ${action}: ${f}`);
    if (!dryRun) await fs.unlink(f);
    count++;
  }

  // Processed entry
  if (files.processedEntry) {
    console.log(`  ${action}: processed_posts.json entry for ${postId}`);
    if (!dryRun) {
      const processedPath = path.join(DATA_DIR, 'processed_posts.json');
      const processed = JSON.parse(await fs.readFile(processedPath, 'utf8'));
      delete processed.posts[postId];
      await fs.writeFile(processedPath, JSON.stringify(processed, null, 2));
    }
    count++;
  }

  return count;
}

async function main() {
  const args = process.argv.slice(2);
  const execute = args.includes('--execute');
  const postIds = args.filter(a => !a.startsWith('--'));

  if (postIds.length === 0) {
    console.log(`Reset Post - Clear all files for a Reddit post ID

Usage: node reset-post.js <post_id> [post_id...] [--execute]

By default, shows what would be deleted (dry-run).
Use --execute to actually delete the files.

Files checked:
  - analysis_results/<post_id>_*_analysis.json
  - data/releases/<author>/<post_id>_*/
  - /Volumes/Culture 1/Aural_Stash/*<post_id>*.mp4
  - data/processed_posts.json entry

Examples:
  node reset-post.js 1e1olrf              # Show what would be deleted
  node reset-post.js 1e1olrf --execute    # Actually delete
  node reset-post.js 1dknr0o 1e1olrf 1e109z3 --execute  # Multiple posts`);
    return;
  }

  const dryRun = !execute;
  if (dryRun) {
    console.log('DRY RUN - No files will be deleted\n');
  }

  let totalCount = 0;
  const reimportCommands = [];

  for (const postId of postIds) {
    console.log(`\n📋 Post: ${postId}`);
    const files = await findFilesForPost(postId);
    const sourceFile = await findSourcePostFile(postId);

    const hasFiles = files.analysisFiles.length > 0 ||
                     files.releaseDir ||
                     files.auralStashFiles.length > 0 ||
                     files.processedEntry;

    if (!hasFiles) {
      console.log('  No files found for this post ID');
      continue;
    }

    const count = await deleteFiles(files, postId, dryRun);
    console.log(`  Total: ${count} item(s)`);
    totalCount += count;

    if (sourceFile) {
      reimportCommands.push(`node analyze-download-import.js ./${sourceFile} --force`);
    }
  }

  if (postIds.length > 1) {
    console.log(`\n${'─'.repeat(40)}`);
    console.log(`Grand total: ${totalCount} item(s)`);
  }

  if (dryRun && totalCount > 0) {
    console.log('\nRun with --execute to delete these files');
  }

  // Show re-import commands
  if (reimportCommands.length > 0) {
    console.log(`\n${'═'.repeat(60)}`);
    console.log('To re-import after reset:');
    console.log(`${'═'.repeat(60)}`);
    for (const cmd of reimportCommands) {
      console.log(cmd);
    }
  }
}

main().catch(err => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
