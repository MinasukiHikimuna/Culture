#!/usr/bin/env node

/**
 * Migrate audio SHA256 fingerprints to existing Stashapp scenes
 *
 * This script reads release.json files and sets audio_sha256 fingerprints
 * on matching Stashapp scenes. It matches scenes by:
 * 1. Reddit post ID in scene URLs
 * 2. Reddit post ID in scene file basename
 *
 * Usage:
 *   node stashapp-migrate-fingerprints.js                    # Migrate all
 *   node stashapp-migrate-fingerprints.js --dry-run          # Preview only
 *   node stashapp-migrate-fingerprints.js --scene 215        # Single scene
 *   node stashapp-migrate-fingerprints.js --verbose          # Show more details
 */

const fs = require('fs').promises;
const path = require('path');

// Load .env from project root
require('dotenv').config({ path: path.join(__dirname, '.env') });

const { StashappClient } = require('./stashapp-importer');

/**
 * Recursively find all files matching a pattern
 */
async function findFiles(dir, pattern) {
  const results = [];

  async function walk(currentDir) {
    let entries;
    try {
      entries = await fs.readdir(currentDir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (entry.name === pattern) {
        results.push(fullPath);
      }
    }
  }

  await walk(dir);
  return results;
}

/**
 * Find release.json files matching a post ID pattern
 */
async function findReleasesByPostId(postId) {
  const releasesDir = path.join(__dirname, 'data', 'releases');
  const allReleases = await findFiles(releasesDir, 'release.json');

  return allReleases.filter(releasePath => {
    const dirName = path.basename(path.dirname(releasePath));
    return dirName.startsWith(postId);
  });
}

// Stats tracking
const stats = {
  releasesProcessed: 0,
  audioSourcesProcessed: 0,
  fingerprintsSet: 0,
  fingerprintsAlreadySet: 0,
  scenesNotFound: 0,
  noChecksum: 0,
  errors: 0
};

/**
 * Format date from Unix timestamp to YYYY-MM-DD
 */
function formatDate(unixTimestamp) {
  if (!unixTimestamp) return null;
  const date = new Date(unixTimestamp * 1000);
  return date.toISOString().split('T')[0];
}

/**
 * Process a single release and set fingerprints on matching scenes
 */
async function processRelease(client, releasePath, options) {
  let release;

  try {
    const content = await fs.readFile(releasePath, 'utf8');
    release = JSON.parse(content);
  } catch (e) {
    console.error(`  Error reading ${releasePath}: ${e.message}`);
    stats.errors++;
    return;
  }

  const redditData = release.enrichmentData?.reddit || {};
  const postId = redditData.id;
  const performer = release.primaryPerformer;
  const date = formatDate(release.releaseDate);

  if (options.verbose) {
    console.log(`\nProcessing: ${release.title?.substring(0, 60)}...`);
    console.log(`  Post ID: ${postId}, Performer: ${performer}, Date: ${date}`);
  } else {
    console.log(`\nProcessing: ${postId} (${performer})`);
  }

  stats.releasesProcessed++;

  // Get all scenes for this performer (without date filter due to timezone issues)
  let scenes = [];
  if (performer) {
    scenes = await client.findScenesByPerformer(performer);
    if (options.verbose) {
      console.log(`  Found ${scenes.length} scenes for ${performer}`);
    }
  }

  // Process each audio source
  const audioSources = release.audioSources || [];
  for (let i = 0; i < audioSources.length; i++) {
    const source = audioSources[i];
    const sha256 = source.audio?.checksum?.sha256;
    const versionSlug = source.versionInfo?.slug || `v${i}`;

    stats.audioSourcesProcessed++;

    if (!sha256) {
      if (options.verbose) {
        console.log(`  [${versionSlug}] No SHA256 checksum, skipping`);
      }
      stats.noChecksum++;
      continue;
    }

    // Try to find matching scene
    // First by URL containing post ID, then by filename
    let matchedScene = null;
    for (const scene of scenes) {
      // Check URLs
      const hasUrlMatch = scene.urls?.some(url => url.includes(postId));
      // Check filename
      const hasFilenameMatch = scene.files?.some(f =>
        f.basename?.includes(postId)
      );

      if (hasUrlMatch || hasFilenameMatch) {
        // For multi-version releases, try to match by version slug too
        if (audioSources.length > 1 && versionSlug) {
          const hasVersionMatch = scene.files?.some(f =>
            f.basename?.toLowerCase().includes(versionSlug.toLowerCase())
          );
          // If this is a multi-version and we have a slug, prefer version-matched scenes
          if (hasVersionMatch) {
            matchedScene = scene;
            break;
          }
          // If no version match, only use this scene if we haven't found one yet
          if (!matchedScene) {
            matchedScene = scene;
          }
        } else {
          matchedScene = scene;
          break;
        }
      }
    }

    if (!matchedScene) {
      console.log(`  [${versionSlug}] No matching scene found for post ${postId}`);
      stats.scenesNotFound++;
      continue;
    }

    // Get the file and check existing fingerprints
    const file = matchedScene.files?.[0];
    if (!file) {
      console.log(`  [${versionSlug}] Scene ${matchedScene.id} has no files`);
      stats.errors++;
      continue;
    }

    const existingFp = file.fingerprints?.find(fp => fp.type === 'audio_sha256');
    if (existingFp) {
      if (existingFp.value === sha256) {
        console.log(`  [${versionSlug}] Scene ${matchedScene.id}: fingerprint already set correctly`);
        stats.fingerprintsAlreadySet++;
      } else {
        console.log(`  [${versionSlug}] Scene ${matchedScene.id}: WARNING - existing fingerprint differs!`);
        console.log(`    Existing: ${existingFp.value.substring(0, 16)}...`);
        console.log(`    Expected: ${sha256.substring(0, 16)}...`);
        stats.errors++;
      }
      continue;
    }

    // Set the fingerprint
    if (options.dryRun) {
      console.log(`  [${versionSlug}] [DRY RUN] Would set fingerprint on scene ${matchedScene.id}: ${sha256.substring(0, 16)}...`);
    } else {
      try {
        await client.setFileFingerprint(file.id, 'audio_sha256', sha256);
        console.log(`  [${versionSlug}] Set fingerprint on scene ${matchedScene.id}: ${sha256.substring(0, 16)}...`);
        stats.fingerprintsSet++;
      } catch (e) {
        console.error(`  [${versionSlug}] Error setting fingerprint on scene ${matchedScene.id}: ${e.message}`);
        stats.errors++;
      }
    }
  }
}

/**
 * Process a single scene by ID
 */
async function processSceneById(client, sceneId, options) {
  console.log(`\nFetching scene ${sceneId}...`);

  const scene = await client.getSceneWithFiles(sceneId);
  if (!scene) {
    console.error(`Error: Scene ${sceneId} not found`);
    return;
  }

  console.log(`Scene: ${scene.title?.substring(0, 60)}...`);

  // Extract post ID from URLs or filename
  let postId = null;
  for (const url of scene.urls || []) {
    const match = url.match(/comments\/([a-z0-9]+)\//i);
    if (match) {
      postId = match[1];
      break;
    }
  }

  if (!postId) {
    // Try filename
    const file = scene.files?.[0];
    if (file?.basename) {
      // Format: "performer - date - postId - title.mp4"
      const parts = file.basename.split(' - ');
      if (parts.length >= 3) {
        postId = parts[2];
      }
    }
  }

  if (!postId) {
    console.error('Could not extract post ID from scene URLs or filename');
    return;
  }

  console.log(`Post ID: ${postId}`);

  // Find the release.json
  const releases = await findReleasesByPostId(postId);

  if (releases.length === 0) {
    console.error(`No release.json found matching post ID ${postId}`);
    return;
  }

  for (const releasePath of releases) {
    await processRelease(client, releasePath, options);
  }
}

/**
 * Main migration function
 */
async function migrateFingerprints(options) {
  const client = new StashappClient();

  // Test connection
  console.log('Connecting to Stashapp...');
  const version = await client.getVersion();
  console.log(`Connected to Stashapp ${version}`);

  if (options.dryRun) {
    console.log('\n*** DRY RUN MODE - No changes will be made ***\n');
  }

  if (options.sceneId) {
    // Process single scene
    await processSceneById(client, options.sceneId, options);
  } else {
    // Process all releases
    console.log('\nFinding all release.json files...');
    const releasesDir = path.join(__dirname, 'data', 'releases');
    const releases = await findFiles(releasesDir, 'release.json');
    console.log(`Found ${releases.length} releases`);

    for (const releasePath of releases) {
      await processRelease(client, releasePath, options);
    }
  }

  // Print summary
  console.log('\n' + '='.repeat(60));
  console.log('Migration Summary');
  console.log('='.repeat(60));
  console.log(`Releases processed:        ${stats.releasesProcessed}`);
  console.log(`Audio sources processed:   ${stats.audioSourcesProcessed}`);
  console.log(`Fingerprints set:          ${stats.fingerprintsSet}`);
  console.log(`Already set correctly:     ${stats.fingerprintsAlreadySet}`);
  console.log(`Scenes not found:          ${stats.scenesNotFound}`);
  console.log(`Missing checksums:         ${stats.noChecksum}`);
  console.log(`Errors:                    ${stats.errors}`);
  console.log('='.repeat(60));
}

// Parse CLI arguments
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    dryRun: false,
    sceneId: null,
    verbose: false
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--scene':
        options.sceneId = args[++i];
        break;
      case '--verbose':
      case '-v':
        options.verbose = true;
        break;
      case '--help':
      case '-h':
        console.log(`
Stashapp Fingerprint Migration
==============================

Migrate audio SHA256 fingerprints from release.json files to Stashapp scenes.

Usage:
  node stashapp-migrate-fingerprints.js [options]

Options:
  --dry-run       Preview changes without making them
  --scene <id>    Migrate a single scene by ID
  --verbose, -v   Show more detailed output
  --help, -h      Show this help message

Examples:
  node stashapp-migrate-fingerprints.js                    # Migrate all
  node stashapp-migrate-fingerprints.js --dry-run          # Preview only
  node stashapp-migrate-fingerprints.js --scene 215        # Single scene
`);
        process.exit(0);
    }
  }

  return options;
}

// Main entry point
const options = parseArgs();
migrateFingerprints(options).catch(error => {
  console.error('Error:', error.message);
  process.exit(1);
});
