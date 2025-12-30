#!/usr/bin/env node

/**
 * CYOA Import Script
 *
 * Imports Choose Your Own Adventure releases to Stashapp with decision tree navigation.
 * This is a specialized script for complex CYOA releases that need linked scene descriptions.
 *
 * Usage:
 *   node cyoa-import.js <cyoa-json-file> [options]
 *
 * Options:
 *   --download-only    Only download audio files, don't import to Stashapp
 *   --update-only      Only update scene descriptions (requires scene-mapping.json)
 *   --dry-run          Show what would be done without making changes
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');

// Load .env from project root
require('dotenv').config({ path: path.join(__dirname, '.env') });

// Import Stashapp client from existing importer
const { StashappClient, STASH_BASE_URL } = require('./stashapp-importer');

// Configuration
const STASH_OUTPUT_DIR = '/Volumes/Culture 1/Aural_Stash';
const STATIC_IMAGE = path.join(__dirname, 'gwa.png');

/**
 * Download audio from Soundgasm
 */
async function downloadSoundgasmAudio(url, outputPath) {
  console.log(`  Downloading: ${url}`);

  // Extract audio URL from Soundgasm page
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch Soundgasm page: ${response.status}`);
  }

  const html = await response.text();
  const audioMatch = html.match(/m4a:\s*"([^"]+)"/);
  if (!audioMatch) {
    throw new Error('Could not find audio URL in Soundgasm page');
  }

  const audioUrl = audioMatch[1];
  console.log(`  Audio URL: ${audioUrl}`);

  // Download the audio file
  const audioResponse = await fetch(audioUrl);
  if (!audioResponse.ok) {
    throw new Error(`Failed to download audio: ${audioResponse.status}`);
  }

  const buffer = Buffer.from(await audioResponse.arrayBuffer());
  await fs.writeFile(outputPath, buffer);
  console.log(`  Downloaded: ${outputPath}`);

  return outputPath;
}

/**
 * Convert audio to video with static image
 */
async function convertAudioToVideo(audioPath, outputPath) {
  // Check if static image exists
  try {
    await fs.access(STATIC_IMAGE);
  } catch {
    console.log(`  Warning: Static image not found at ${STATIC_IMAGE}`);
    console.log('  Creating a simple black image...');
    execSync(`ffmpeg -f lavfi -i color=c=black:s=1280x720:d=1 -frames:v 1 "${STATIC_IMAGE}"`, {
      stdio: 'pipe'
    });
  }

  const cmd = [
    'ffmpeg',
    '-y',
    '-loop', '1',
    '-i', STATIC_IMAGE,
    '-i', audioPath,
    '-c:v', 'libx264',
    '-tune', 'stillimage',
    '-c:a', 'aac',
    '-b:a', '192k',
    '-pix_fmt', 'yuv420p',
    '-shortest',
    outputPath
  ].map(arg => `"${arg}"`).join(' ');

  console.log('  Running ffmpeg conversion...');

  try {
    execSync(cmd, { stdio: 'pipe' });
  } catch (e) {
    console.log(`  ffmpeg error: ${e.message}`);
    return false;
  }

  try {
    await fs.access(outputPath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Generate scene description with decision tree links
 */
function generateDescription(audioData, cyoaData, sceneMapping, startSceneId) {
  const lines = [];

  // Title
  lines.push(`# ${audioData.title}`);
  lines.push('');

  // Ending indicator
  if (audioData.isEnding) {
    const endingLabel = {
      'bad': '**BAD ENDING**',
      'good': '**GOOD ENDING**',
      'best': '**BEST ENDING**'
    }[audioData.endingType] || '**ENDING**';

    lines.push(endingLabel);
    lines.push('');
  }

  // Tags
  if (audioData.tags && audioData.tags.length > 0) {
    // Filter out ending type tags
    const displayTags = audioData.tags.filter(t =>
      !['Bad Ending', 'Good Ending', 'Best Ending'].includes(t)
    );
    if (displayTags.length > 0) {
      lines.push(`Tags: ${displayTags.join(', ')}`);
      lines.push('');
    }
  }

  // Choices (if not an ending)
  if (audioData.choices && audioData.choices.length > 0) {
    lines.push('## Choose your path:');
    lines.push('');

    for (const choice of audioData.choices) {
      const targetSceneId = sceneMapping[choice.leadsTo];
      if (targetSceneId) {
        const targetAudio = cyoaData.audios[choice.leadsTo];
        const targetTitle = targetAudio?.title || `Audio ${choice.leadsTo}`;
        lines.push(`- [${choice.label}](/scenes/${targetSceneId})`);
      } else {
        lines.push(`- ${choice.label} (scene not yet imported)`);
      }
    }
    lines.push('');
  }

  // Navigation
  lines.push('---');
  if (startSceneId) {
    lines.push(`[Start Over](/scenes/${startSceneId})`);
  }

  return lines.join('\n');
}

/**
 * Main CYOA import class
 */
class CYOAImporter {
  constructor(options = {}) {
    this.client = new StashappClient();
    this.outputDir = options.outputDir || STASH_OUTPUT_DIR;
    this.dryRun = options.dryRun || false;
    this.downloadOnly = options.downloadOnly || false;
    this.updateOnly = options.updateOnly || false;
  }

  /**
   * Load CYOA data from JSON file
   */
  async loadCYOAData(jsonPath) {
    const content = await fs.readFile(jsonPath, 'utf8');
    return JSON.parse(content);
  }

  /**
   * Load or create scene mapping
   */
  async loadSceneMapping(mappingPath) {
    try {
      const content = await fs.readFile(mappingPath, 'utf8');
      return JSON.parse(content);
    } catch {
      return {};
    }
  }

  /**
   * Save scene mapping
   */
  async saveSceneMapping(mappingPath, mapping) {
    await fs.writeFile(mappingPath, JSON.stringify(mapping, null, 2));
  }

  /**
   * Process a single audio
   */
  async processAudio(audioKey, audioData, cyoaData, downloadDir, performer, date, postId) {
    console.log(`\n[${audioKey}] ${audioData.title}`);

    // Generate filenames
    const audioFilename = `${audioKey}_${audioData.title.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 30)}.m4a`;
    const audioPath = path.join(downloadDir, audioFilename);

    const videoFilename = `${performer} - ${date} - ${postId} - CYOA ${audioKey} - ${audioData.title.replace(/[^a-zA-Z0-9 ]/g, '').substring(0, 40)}.mp4`;
    const videoPath = path.join(this.outputDir, videoFilename);

    // Download audio if needed
    try {
      await fs.access(audioPath);
      console.log('  Audio already downloaded');
    } catch {
      if (this.dryRun) {
        console.log(`  [DRY RUN] Would download: ${audioData.url}`);
      } else {
        await downloadSoundgasmAudio(audioData.url, audioPath);
      }
    }

    if (this.downloadOnly) {
      return { audioPath, videoPath: null, sceneId: null };
    }

    // Convert to video if needed
    try {
      await fs.access(videoPath);
      console.log('  Video already exists');
    } catch {
      if (this.dryRun) {
        console.log(`  [DRY RUN] Would convert to video: ${videoFilename}`);
      } else {
        const success = await convertAudioToVideo(audioPath, videoPath);
        if (!success) {
          console.log('  Error: Failed to convert audio to video');
          return { audioPath, videoPath: null, sceneId: null };
        }
      }
    }

    return { audioPath, videoPath, sceneId: null };
  }

  /**
   * Import all audios and collect scene IDs
   */
  async importAudios(cyoaData, downloadDir) {
    const performer = cyoaData.performer;
    const postId = cyoaData.reddit_post_id;

    // Get date from Reddit post (assume current date if not available)
    const date = new Date().toISOString().split('T')[0];

    const results = {};
    const audioKeys = Object.keys(cyoaData.audios);

    console.log(`\nProcessing ${audioKeys.length} audios...`);

    for (const audioKey of audioKeys) {
      const audioData = cyoaData.audios[audioKey];
      const result = await this.processAudio(
        audioKey, audioData, cyoaData, downloadDir, performer, date, postId
      );
      results[audioKey] = result;

      // Small delay between downloads
      if (!this.dryRun) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }

    return results;
  }

  /**
   * Trigger scan and find scenes
   */
  async scanAndFindScenes(cyoaData, downloadDir) {
    console.log('\nTriggering Stashapp scan...');

    if (this.dryRun) {
      console.log('[DRY RUN] Would trigger scan');
      return {};
    }

    await this.client.triggerScan();
    console.log('Waiting for scan to complete...');
    await this.client.waitForScan(120); // Wait up to 2 minutes

    // Wait a bit more for indexing
    await new Promise(resolve => setTimeout(resolve, 5000));

    // Find scenes by searching for the CYOA prefix
    const sceneMapping = {};
    const performer = cyoaData.performer;
    const postId = cyoaData.reddit_post_id;

    console.log('\nFinding imported scenes...');

    for (const audioKey of Object.keys(cyoaData.audios)) {
      const searchTerm = `CYOA ${audioKey}`;

      // Search by path
      const query = `
        query FindScenes($scene_filter: SceneFilterType!, $filter: FindFilterType!) {
          findScenes(scene_filter: $scene_filter, filter: $filter) {
            scenes { id title files { basename } }
          }
        }
      `;

      const result = await this.client.query(query, {
        scene_filter: {
          path: {
            value: `${postId}`,
            modifier: 'INCLUDES'
          }
        },
        filter: { per_page: 100 }
      });

      const scenes = result.findScenes?.scenes || [];

      // Find the scene matching this audio key
      for (const scene of scenes) {
        for (const file of scene.files || []) {
          if (file.basename.includes(`CYOA ${audioKey} -`)) {
            sceneMapping[audioKey] = scene.id;
            console.log(`  Found [${audioKey}]: Scene ${scene.id}`);
            break;
          }
        }
        if (sceneMapping[audioKey]) break;
      }

      if (!sceneMapping[audioKey]) {
        console.log(`  Warning: Scene not found for [${audioKey}]`);
      }
    }

    return sceneMapping;
  }

  /**
   * Create group and add scenes
   */
  async createGroup(cyoaData, sceneMapping) {
    const groupName = `CYOA: ${cyoaData.title.replace('Choose Your Own Adventure: ', '')}`;

    console.log(`\nCreating group: ${groupName}`);

    if (this.dryRun) {
      console.log('[DRY RUN] Would create group');
      return null;
    }

    const group = await this.client.findOrCreateGroup(groupName, {
      synopsis: `Choose Your Own Adventure with ${cyoaData.total_audios} audios and ${cyoaData.total_endings} endings.`
    });

    // Add scenes to group with ordering
    const audioKeys = Object.keys(cyoaData.audios);
    for (let i = 0; i < audioKeys.length; i++) {
      const audioKey = audioKeys[i];
      const sceneId = sceneMapping[audioKey];

      if (sceneId) {
        await this.client.addSceneToGroup(sceneId, group.id, i + 1);
        console.log(`  Added [${audioKey}] to group at index ${i + 1}`);
      }
    }

    return group;
  }

  /**
   * Update scene with metadata
   */
  async updateSceneMetadata(sceneId, audioData, cyoaData, performer) {
    const updates = {
      title: `[CYOA] ${cyoaData.title.replace('Choose Your Own Adventure: ', '')} - ${audioData.title}`
    };

    // Add performer
    const performerObj = await this.client.findPerformer(performer);
    if (performerObj) {
      updates.performer_ids = [performerObj.id];
    }

    // Add studio
    const studio = await this.client.findStudio(performer);
    if (studio) {
      updates.studio_id = studio.id;
    }

    await this.client.updateScene(sceneId, updates);
  }

  /**
   * Update all scene descriptions with decision tree links
   */
  async updateDescriptions(cyoaData, sceneMapping) {
    console.log('\nUpdating scene descriptions with decision tree links...');

    const startSceneId = sceneMapping['0'];

    for (const [audioKey, audioData] of Object.entries(cyoaData.audios)) {
      const sceneId = sceneMapping[audioKey];

      if (!sceneId) {
        console.log(`  Skipping [${audioKey}]: No scene ID`);
        continue;
      }

      const description = generateDescription(audioData, cyoaData, sceneMapping, startSceneId);

      if (this.dryRun) {
        console.log(`  [DRY RUN] Would update [${audioKey}] (Scene ${sceneId})`);
        console.log(`    Description preview: ${description.substring(0, 100)}...`);
      } else {
        await this.client.updateScene(sceneId, { details: description });
        console.log(`  Updated [${audioKey}] (Scene ${sceneId})`);
      }
    }
  }

  /**
   * Run the full import process
   */
  async run(jsonPath) {
    // Load CYOA data
    console.log(`Loading CYOA data from: ${jsonPath}`);
    const cyoaData = await this.loadCYOAData(jsonPath);

    console.log(`\nCYOA: ${cyoaData.title}`);
    console.log(`Performer: ${cyoaData.performer}`);
    console.log(`Audios: ${cyoaData.total_audios}`);
    console.log(`Endings: ${cyoaData.total_endings}`);

    // Setup directories
    const baseDir = path.dirname(jsonPath);
    const downloadDir = path.join(baseDir, cyoaData.reddit_post_id);
    const mappingPath = path.join(baseDir, `${cyoaData.reddit_post_id}_scene_mapping.json`);

    // Create download directory
    try {
      await fs.mkdir(downloadDir, { recursive: true });
    } catch {}

    let sceneMapping = await this.loadSceneMapping(mappingPath);

    if (this.updateOnly) {
      // Only update descriptions
      if (Object.keys(sceneMapping).length === 0) {
        console.error('Error: No scene mapping found. Run import first.');
        return;
      }

      await this.updateDescriptions(cyoaData, sceneMapping);
      console.log('\nDescription update complete!');
      return;
    }

    // Test connection
    console.log('\nTesting Stashapp connection...');
    if (!this.dryRun && !this.downloadOnly) {
      const version = await this.client.getVersion();
      console.log(`Connected to Stashapp ${version}`);
    }

    // Download and convert all audios
    await this.importAudios(cyoaData, downloadDir);

    if (this.downloadOnly) {
      console.log('\nDownload complete!');
      return;
    }

    // Scan and find scenes
    sceneMapping = await this.scanAndFindScenes(cyoaData, downloadDir);

    // Save mapping
    if (!this.dryRun) {
      await this.saveSceneMapping(mappingPath, sceneMapping);
      console.log(`\nScene mapping saved to: ${mappingPath}`);
    }

    // Create group
    const group = await this.createGroup(cyoaData, sceneMapping);

    // Update scene metadata and descriptions
    console.log('\nUpdating scene metadata...');
    for (const [audioKey, audioData] of Object.entries(cyoaData.audios)) {
      const sceneId = sceneMapping[audioKey];
      if (sceneId && !this.dryRun) {
        await this.updateSceneMetadata(sceneId, audioData, cyoaData, cyoaData.performer);
      }
    }

    await this.updateDescriptions(cyoaData, sceneMapping);

    // Summary
    console.log(`\n${'='.repeat(60)}`);
    console.log('CYOA Import Complete!');
    console.log(`${'='.repeat(60)}`);
    console.log(`Scenes imported: ${Object.keys(sceneMapping).length}`);
    if (group) {
      console.log(`Group URL: ${STASH_BASE_URL}/groups/${group.id}`);
    }
    if (sceneMapping['0']) {
      console.log(`Start scene: ${STASH_BASE_URL}/scenes/${sceneMapping['0']}`);
    }
  }
}

// CLI
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help')) {
    console.log(`
CYOA Import Script
==================

Imports Choose Your Own Adventure releases to Stashapp with decision tree navigation.

Usage:
  node cyoa-import.js <cyoa-json-file> [options]

Options:
  --download-only    Only download audio files, don't import to Stashapp
  --update-only      Only update scene descriptions (requires existing scene mapping)
  --dry-run          Show what would be done without making changes
  --help             Show this help message

Example:
  node cyoa-import.js data/cyoa/ni2wma_high_school_reunion.json
  node cyoa-import.js data/cyoa/ni2wma_high_school_reunion.json --download-only
  node cyoa-import.js data/cyoa/ni2wma_high_school_reunion.json --update-only
`);
    process.exit(0);
  }

  const jsonPath = args.find(a => !a.startsWith('--'));
  const options = {
    downloadOnly: args.includes('--download-only'),
    updateOnly: args.includes('--update-only'),
    dryRun: args.includes('--dry-run')
  };

  if (!jsonPath) {
    console.error('Error: No CYOA JSON file specified');
    process.exit(1);
  }

  try {
    await fs.access(jsonPath);
  } catch {
    console.error(`Error: File not found: ${jsonPath}`);
    process.exit(1);
  }

  // Check output directory (unless download-only)
  if (!options.downloadOnly) {
    try {
      await fs.access(STASH_OUTPUT_DIR);
    } catch {
      console.error(`Error: Stash output directory not found: ${STASH_OUTPUT_DIR}`);
      console.error('Make sure the volume is mounted.');
      process.exit(1);
    }
  }

  const importer = new CYOAImporter(options);

  try {
    await importer.run(jsonPath);
  } catch (e) {
    console.error(`Error: ${e.message}`);
    if (e.stack) {
      console.error(e.stack);
    }
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { CYOAImporter };
