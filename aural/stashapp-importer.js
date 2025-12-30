#!/usr/bin/env node

/**
 * Stashapp Importer - Import releases to Stashapp
 *
 * This module transforms audio files to video and imports them into Stashapp
 * with full metadata including performers, studios, and tags.
 *
 * Usage (CLI):
 *   node stashapp-importer.js <release_directory>
 *
 * Usage (Module):
 *   const { StashappImporter } = require('./stashapp-importer');
 *   const importer = new StashappImporter();
 *   const result = await importer.processRelease(releaseDir);
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');

// Stashapp Configuration
const STASH_URL = process.env.STASHAPP_URL || 'https://stash-aural.chiefsclub.com/graphql';
const STASH_API_KEY = process.env.STASHAPP_API_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJzdGFzaCIsInN1YiI6IkFQSUtleSIsImlhdCI6MTcyMzQ1MzA5OH0.V7_yGP7-07drQoLZsZNJ46WSriQ1NfirT5QjhfZsvNw';
const STASH_OUTPUT_DIR = '/Volumes/Culture 1/Aural_Stash';
const STASH_BASE_URL = 'https://stash-aural.chiefsclub.com';

// Static image for audio-to-video conversion
const STATIC_IMAGE = path.join(__dirname, 'gwa.png');

/**
 * Simple Stashapp GraphQL client
 */
class StashappClient {
  constructor(url = STASH_URL, apiKey = STASH_API_KEY) {
    this.url = url;
    this.apiKey = apiKey;
  }

  /**
   * Execute a GraphQL query
   */
  async query(query, variables = {}) {
    const response = await fetch(this.url, {
      method: 'POST',
      headers: {
        'ApiKey': this.apiKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query, variables })
    });

    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status} ${response.statusText}`);
    }

    const result = await response.json();
    if (result.errors) {
      throw new Error(`GraphQL errors: ${JSON.stringify(result.errors)}`);
    }

    return result.data || {};
  }

  /**
   * Find performer by name
   */
  async findPerformer(name) {
    const query = `
      query FindPerformers($filter: FindFilterType!) {
        findPerformers(filter: $filter) {
          performers { id name disambiguation }
        }
      }
    `;
    const result = await this.query(query, { filter: { q: name, per_page: 10 } });
    const performers = result.findPerformers?.performers || [];

    // Exact match (case-insensitive)
    for (const p of performers) {
      if (p.name.toLowerCase() === name.toLowerCase()) {
        return p;
      }
    }
    return null;
  }

  /**
   * Create a new performer
   */
  async createPerformer(name, imageUrl = null) {
    const query = `
      mutation PerformerCreate($input: PerformerCreateInput!) {
        performerCreate(input: $input) { id name }
      }
    `;
    const input = { name };
    if (imageUrl) {
      input.image = imageUrl;
    }
    const result = await this.query(query, { input });
    return result.performerCreate;
  }

  /**
   * Find or create a performer by name
   */
  async findOrCreatePerformer(name, imageUrl = null) {
    let performer = await this.findPerformer(name);
    if (performer) {
      console.log(`  Found existing performer: ${performer.name} (ID: ${performer.id})`);
      return performer;
    }

    performer = await this.createPerformer(name, imageUrl);
    if (imageUrl) {
      console.log(`  Created new performer: ${performer.name} (ID: ${performer.id}) with avatar`);
    } else {
      console.log(`  Created new performer: ${performer.name} (ID: ${performer.id})`);
    }
    return performer;
  }

  /**
   * Find studio by name
   */
  async findStudio(name) {
    const query = `
      query FindStudios($filter: FindFilterType!) {
        findStudios(filter: $filter) {
          studios { id name }
        }
      }
    `;
    const result = await this.query(query, { filter: { q: name, per_page: 10 } });
    const studios = result.findStudios?.studios || [];

    for (const s of studios) {
      if (s.name.toLowerCase() === name.toLowerCase()) {
        return s;
      }
    }
    return null;
  }

  /**
   * Create a new studio
   */
  async createStudio(name) {
    const query = `
      mutation StudioCreate($input: StudioCreateInput!) {
        studioCreate(input: $input) { id name }
      }
    `;
    const result = await this.query(query, { input: { name } });
    return result.studioCreate;
  }

  /**
   * Find or create a studio by name
   */
  async findOrCreateStudio(name) {
    let studio = await this.findStudio(name);
    if (studio) {
      console.log(`  Found existing studio: ${studio.name} (ID: ${studio.id})`);
      return studio;
    }

    studio = await this.createStudio(name);
    console.log(`  Created new studio: ${studio.name} (ID: ${studio.id})`);
    return studio;
  }

  /**
   * Get all tags with their aliases
   */
  async getAllTags() {
    const query = `
      query FindTags {
        findTags(filter: { per_page: -1 }) {
          tags { id name aliases }
        }
      }
    `;
    const result = await this.query(query);
    return result.findTags?.tags || [];
  }

  /**
   * Trigger a metadata scan
   */
  async triggerScan() {
    const query = `
      mutation MetadataScan($input: ScanMetadataInput!) {
        metadataScan(input: $input)
      }
    `;
    const result = await this.query(query, { input: { paths: [] } });
    return result.metadataScan;
  }

  /**
   * Wait for any running scan jobs to complete
   */
  async waitForScan(timeout = 30) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeout * 1000) {
      const result = await this.query('query { jobQueue { id status } }');
      const jobs = result.jobQueue || [];
      if (jobs.length === 0) {
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    return false;
  }

  /**
   * Find a scene by file basename
   */
  async findSceneByBasename(basename) {
    const query = `
      query FindScenes($filter: FindFilterType!) {
        findScenes(filter: $filter) {
          scenes { id title files { path basename } }
        }
      }
    `;
    const result = await this.query(query, { filter: { q: basename, per_page: 10 } });
    const scenes = result.findScenes?.scenes || [];

    for (const scene of scenes) {
      for (const f of scene.files || []) {
        if (f.basename === basename) {
          return scene;
        }
      }
    }
    return null;
  }

  /**
   * Update a scene with metadata
   */
  async updateScene(sceneId, updates) {
    const query = `
      mutation SceneUpdate($input: SceneUpdateInput!) {
        sceneUpdate(input: $input) { id title }
      }
    `;
    updates.id = sceneId;
    const result = await this.query(query, { input: updates });
    return result.sceneUpdate;
  }

  /**
   * Get Stashapp version (for connection testing)
   */
  async getVersion() {
    const result = await this.query('query { version { version } }');
    return result.version?.version;
  }
}

/**
 * Extract bracketed tags from title
 */
function extractTagsFromTitle(title) {
  const pattern = /\[([^\]]+)\]/g;
  const tags = [];
  let match;
  while ((match = pattern.exec(title)) !== null) {
    tags.push(match[1].trim());
  }
  return tags;
}

/**
 * Extract bracketed tags from post body text (handles escaped brackets)
 */
function extractTagsFromText(text) {
  const pattern = /\\+\[([^\]]+)\\+\]/g;
  const tags = [];
  let match;
  while ((match = pattern.exec(text)) !== null) {
    tags.push(match[1].trim());
  }
  return tags;
}

/**
 * Fetch Reddit avatar for a user
 */
async function getRedditAvatar(username) {
  try {
    const url = `https://www.reddit.com/user/${username}/about.json`;
    const response = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; audio-extractor/1.0)' }
    });

    if (response.ok) {
      const data = await response.json();
      let iconUrl = data.data?.icon_img || '';
      if (iconUrl) {
        // Unescape HTML entities in URL
        iconUrl = iconUrl.replace(/&amp;/g, '&');
        return iconUrl;
      }
    }
  } catch (e) {
    console.log(`    Warning: Could not fetch Reddit avatar for ${username}: ${e.message}`);
  }
  return null;
}

/**
 * Extract all tags from release title and post body
 */
function extractAllTags(release) {
  const tags = [];

  // Tags from title
  const title = release.title || '';
  tags.push(...extractTagsFromTitle(title));

  // Tags from Reddit post body
  const redditData = release.enrichmentData?.reddit || {};
  const selftext = redditData.selftext || '';
  if (selftext) {
    tags.push(...extractTagsFromText(selftext));
  }

  // Remove duplicates while preserving order
  const seen = new Set();
  const uniqueTags = [];
  for (const tag of tags) {
    const tagLower = tag.toLowerCase();
    if (!seen.has(tagLower)) {
      seen.add(tagLower);
      uniqueTags.push(tag);
    }
  }

  return uniqueTags;
}

/**
 * Match extracted tags with existing Stashapp tags (including aliases)
 */
function matchTagsWithStash(extractedTags, stashTags) {
  const matchedTagIds = [];

  // Build lookup dict: lowercase name/alias -> tag id
  const tagLookup = {};
  for (const tag of stashTags) {
    tagLookup[tag.name.toLowerCase()] = tag.id;
    for (const alias of tag.aliases || []) {
      tagLookup[alias.toLowerCase()] = tag.id;
    }
  }

  for (const extracted of extractedTags) {
    const extractedLower = extracted.toLowerCase();
    if (tagLookup[extractedLower]) {
      const tagId = tagLookup[extractedLower];
      if (!matchedTagIds.includes(tagId)) {
        matchedTagIds.push(tagId);
        console.log(`    Matched tag: ${extracted} -> ID ${tagId}`);
      }
    }
  }

  return matchedTagIds;
}

/**
 * Convert audio file to video with static image using ffmpeg
 */
async function convertAudioToVideo(audioPath, outputPath) {
  let staticImage = STATIC_IMAGE;

  // Check if static image exists
  try {
    await fs.access(staticImage);
  } catch {
    console.log(`  Warning: Static image not found at ${staticImage}`);
    console.log('  Creating a simple black image...');
    execSync(`ffmpeg -f lavfi -i color=c=black:s=1280x720:d=1 -frames:v 1 "${staticImage}"`, {
      stdio: 'pipe'
    });
  }

  const cmd = [
    'ffmpeg',
    '-y',
    '-loop', '1',
    '-i', staticImage,
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
 * Generate output filename in Stashapp format
 */
function formatOutputFilename(release) {
  const performer = release.primaryPerformer || 'Unknown';

  // Parse date from Unix timestamp
  let dateStr = 'Unknown';
  if (release.releaseDate) {
    const date = new Date(release.releaseDate * 1000);
    dateStr = date.toISOString().split('T')[0];
  }

  // Get Reddit post ID
  const redditData = release.enrichmentData?.reddit || {};
  const postId = redditData.id || 'unknown';

  // Get clean title (remove emoji and brackets)
  let title = release.title || 'Unknown';
  // Remove bracketed tags for filename
  let cleanTitle = title.replace(/\[[^\]]+\]/g, '').trim();
  // Remove emoji and special chars
  cleanTitle = cleanTitle.replace(/[^\w\s\-\.\,\!\?\'\"\u0080-\uFFFF]/g, '').trim();
  // Truncate if too long
  if (cleanTitle.length > 100) {
    cleanTitle = cleanTitle.substring(0, 100).replace(/\s+\S*$/, '');
  }
  // Sanitize for filesystem
  cleanTitle = cleanTitle.replace(/[<>:"/\\|?*]/g, '');

  return `${performer} - ${dateStr} - ${postId} - ${cleanTitle}.mp4`;
}

/**
 * Main importer class
 */
class StashappImporter {
  constructor(options = {}) {
    this.client = new StashappClient(
      options.url || STASH_URL,
      options.apiKey || STASH_API_KEY
    );
    this.outputDir = options.outputDir || STASH_OUTPUT_DIR;
    this.verbose = options.verbose || false;
  }

  /**
   * Test connection to Stashapp
   */
  async testConnection() {
    console.log('Testing Stashapp connection...');
    const version = await this.client.getVersion();
    console.log(`Connected to Stashapp ${version}`);
    return version;
  }

  /**
   * Process a release directory and import to Stashapp
   * @returns {Object} Result with sceneId and success status
   */
  async processRelease(releaseDir) {
    const releaseJsonPath = path.join(releaseDir, 'release.json');

    let releaseData;
    try {
      const content = await fs.readFile(releaseJsonPath, 'utf8');
      releaseData = JSON.parse(content);
    } catch (e) {
      console.log(`Error: release.json not found in ${releaseDir}`);
      return { success: false, error: 'release.json not found' };
    }

    console.log(`\n${'='.repeat(60)}`);
    console.log(`Processing: ${(releaseData.title || 'Unknown').substring(0, 60)}...`);
    console.log(`${'='.repeat(60)}`);

    // Find audio files
    const audioSources = releaseData.audioSources || [];
    if (audioSources.length === 0) {
      console.log('Error: No audio sources found in release');
      return { success: false, error: 'No audio sources' };
    }

    // Get all Stashapp tags for matching
    console.log('\nFetching Stashapp tags...');
    const stashTags = await this.client.getAllTags();
    console.log(`  Found ${stashTags.length} tags in Stashapp`);

    let lastSceneId = null;

    // Process each audio source
    for (let i = 0; i < audioSources.length; i++) {
      const source = audioSources[i];
      const audioInfo = source.audio || {};
      let audioPath = audioInfo.filePath || '';

      // Make path absolute if relative
      if (!path.isAbsolute(audioPath)) {
        audioPath = path.join(__dirname, audioPath);
      }

      try {
        await fs.access(audioPath);
      } catch {
        console.log(`  Warning: Audio file not found: ${audioPath}`);
        continue;
      }

      console.log(`\n[Audio ${i + 1}/${audioSources.length}] ${path.basename(audioPath)}`);

      // Generate output filename
      const outputFilename = formatOutputFilename(releaseData);
      const outputPath = path.join(this.outputDir, outputFilename);

      console.log(`  Output: ${outputFilename}`);

      // Convert audio to video
      try {
        await fs.access(outputPath);
        console.log('  Video already exists, skipping conversion');
      } catch {
        const success = await convertAudioToVideo(audioPath, outputPath);
        if (!success) {
          console.log('  Error: Failed to convert audio to video');
          continue;
        }
        console.log(`  Conversion successful: ${outputPath}`);
      }

      // Trigger Stashapp scan
      console.log('\n  Triggering Stashapp scan...');
      const jobId = await this.client.triggerScan();
      console.log(`  Scan job started: ${jobId}`);

      // Wait for scan to complete
      console.log('  Waiting for scan to complete...');
      await this.client.waitForScan(60);

      // Find the scene by basename
      const scene = await this.client.findSceneByBasename(outputFilename);
      if (!scene) {
        console.log('  Warning: Scene not found after scan. May need manual refresh.');
        continue;
      }

      console.log(`  Found scene ID: ${scene.id}`);
      lastSceneId = scene.id;

      // Prepare metadata updates
      const updates = {};

      // Title
      updates.title = releaseData.title || '';

      // Date
      if (releaseData.releaseDate) {
        const date = new Date(releaseData.releaseDate * 1000);
        updates.date = date.toISOString().split('T')[0];
      }

      // URLs
      const urls = [];
      const redditData = releaseData.enrichmentData?.reddit || {};
      if (redditData.url) {
        urls.push(redditData.url);
      }
      if (audioInfo.sourceUrl) {
        urls.push(audioInfo.sourceUrl);
      }
      if (urls.length > 0) {
        updates.urls = urls;
      }

      // Details (description)
      const selftext = redditData.selftext || '';
      if (selftext) {
        // Clean up markdown
        let details = selftext
          .replace(/\*\*([^*]+)\*\*/g, '$1')  // Bold
          .replace(/\*([^*]+)\*/g, '$1')      // Italic
          .replace(/\\/g, '');                 // Escape chars
        updates.details = details.substring(0, 5000);
      }

      // Director (script author)
      const llmAnalysis = releaseData.enrichmentData?.llmAnalysis || {};
      let scriptAuthor = llmAnalysis.script?.author;
      if (!scriptAuthor) {
        scriptAuthor = releaseData.scriptAuthor;
      }
      if (scriptAuthor) {
        updates.director = scriptAuthor;
        console.log(`  Director (script author): ${scriptAuthor}`);
      }

      // Performers
      console.log('\n  Processing performers...');
      const performerIds = [];
      const primaryPerformer = releaseData.primaryPerformer;
      if (primaryPerformer) {
        const avatarUrl = await getRedditAvatar(primaryPerformer);
        if (avatarUrl) {
          console.log(`    Found Reddit avatar for ${primaryPerformer}`);
        }
        const performer = await this.client.findOrCreatePerformer(primaryPerformer, avatarUrl);
        performerIds.push(performer.id);
      }

      // Additional performers
      let additionalPerformers = llmAnalysis.performers?.additional || [];
      if (additionalPerformers.length === 0) {
        additionalPerformers = releaseData.additionalPerformers || [];
      }

      for (const additional of additionalPerformers) {
        const avatarUrl = await getRedditAvatar(additional);
        if (avatarUrl) {
          console.log(`    Found Reddit avatar for ${additional}`);
        }
        const performer = await this.client.findOrCreatePerformer(additional, avatarUrl);
        performerIds.push(performer.id);
      }

      if (performerIds.length > 0) {
        updates.performer_ids = performerIds;
      }

      // Studio (same as primary performer for solo releases)
      console.log('\n  Processing studio...');
      if (primaryPerformer) {
        const studio = await this.client.findOrCreateStudio(primaryPerformer);
        updates.studio_id = studio.id;
      }

      // Tags
      console.log('\n  Processing tags...');
      const extractedTags = extractAllTags(releaseData);
      console.log(`    Extracted ${extractedTags.length} tags from title and post body`);

      if (stashTags.length > 0 && extractedTags.length > 0) {
        const matchedTagIds = matchTagsWithStash(extractedTags, stashTags);
        if (matchedTagIds.length > 0) {
          updates.tag_ids = matchedTagIds;
          console.log(`    Matched ${matchedTagIds.length} tags`);
        }
      }

      // Update scene
      console.log('\n  Updating scene metadata...');
      await this.client.updateScene(scene.id, updates);
      console.log('  Scene updated successfully!');
    }

    return {
      success: true,
      sceneId: lastSceneId,
      sceneUrl: lastSceneId ? `${STASH_BASE_URL}/scenes/${lastSceneId}` : null
    };
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Stashapp Importer
=================

This script transforms audio files to video and imports them into Stashapp
with full metadata including performers, studios, and tags.

Usage:
  node stashapp-importer.js <release_directory>

Example:
  node stashapp-importer.js data/releases/SweetnEvil86/1oj6y4p_hitting_on_and_picking_up_your_taken

Options:
  --help    Show this help message
`);
    process.exit(0);
  }

  const releaseDir = args[0];

  try {
    await fs.access(releaseDir);
  } catch {
    console.error(`Error: Directory not found: ${releaseDir}`);
    process.exit(1);
  }

  // Check output directory
  try {
    await fs.access(STASH_OUTPUT_DIR);
  } catch {
    console.error(`Error: Stash output directory not found: ${STASH_OUTPUT_DIR}`);
    console.error('Make sure the volume is mounted.');
    process.exit(1);
  }

  const importer = new StashappImporter();

  try {
    await importer.testConnection();
    const result = await importer.processRelease(releaseDir);

    if (result.success) {
      console.log(`\n${'='.repeat(60)}`);
      console.log('Import completed successfully!');
      if (result.sceneUrl) {
        console.log(`Scene URL: ${result.sceneUrl}`);
      }
      console.log(`${'='.repeat(60)}`);
    } else {
      console.error('\nImport failed:', result.error);
      process.exit(1);
    }
  } catch (e) {
    console.error(`Error: ${e.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  StashappImporter,
  StashappClient,
  STASH_BASE_URL
};
