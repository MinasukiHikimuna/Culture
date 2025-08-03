#!/usr/bin/env node

/**
 * Example Workflow - Demonstrates the new architecture
 * 
 * Shows how the components work together:
 * 1. Reddit post discovery
 * 2. LLM analysis
 * 3. Audio extraction (platform-agnostic)
 * 4. Release aggregation
 */

const { ReleaseOrchestrator } = require('./release-orchestrator');

async function demonstrateWorkflow() {
  console.log('🎭 GWASI Extractor - New Architecture Demo\n');
  
  // Initialize orchestrator
  const orchestrator = new ReleaseOrchestrator({
    dataDir: 'data',
    cacheEnabled: true,
    validateExtractions: true
  });
  
  // Example 1: Process a Reddit post with multiple audio sources
  console.log('📝 Example 1: Multi-platform Release\n');
  
  const redditPost = {
    id: 't3_1mf1onp',
    title: '[F4M] Shy Ghost Girl Possesses You To Feel Pleasure Again',
    author: 'LurkyDip',
    created_utc: '2024-11-28T12:00:00Z',
    selftext: `Hey everyone! Here's my latest audio...
    
    🎧 Listen on:
    - Soundgasm: https://soundgasm.net/u/LurkyDip/Shy-Ghost-Girl-Possesses-You-To-Feel-Pleasure-Again
    - Whyp.it: https://whyp.it/tracks/299350/shy-ghost-girl-possesses-you-to-feel-pleasure-again
    - HotAudio: https://hotaudio.net/u/Lurkydip/Shy-Ghost-Girl-Possesses-You-To-Feel-Pleasure-Again
    
    Script by: u/TheWritingJedi
    
    Tags: [F4M] [Ghost] [Possession] [Supernatural]`
  };
  
  // Simulated LLM analysis (would come from analyze-reddit-post.js)
  const llmAnalysis = {
    primary_performer: 'LurkyDip',
    script_author: 'TheWritingJedi',
    tags: ['F4M', 'Ghost', 'Possession', 'Supernatural'],
    audio_versions: [
      {
        version_name: 'Main',
        urls: [
          { url: 'https://soundgasm.net/u/LurkyDip/Shy-Ghost-Girl-Possesses-You-To-Feel-Pleasure-Again', platform: 'Soundgasm' },
          { url: 'https://whyp.it/tracks/299350/shy-ghost-girl-possesses-you-to-feel-pleasure-again', platform: 'Whyp.it' },
          { url: 'https://hotaudio.net/u/Lurkydip/Shy-Ghost-Girl-Possesses-You-To-Feel-Pleasure-Again', platform: 'HotAudio' }
        ]
      }
    ],
    script_url: 'https://scriptbin.works/u/TheWritingJedi/f4m-shy-ghost-girl-possesses-you-to-feel-pleasure'
  };
  
  // Process the post
  console.log('🔄 Processing Reddit post...\n');
  const release = await orchestrator.processPost(redditPost, llmAnalysis);
  
  // Show results
  console.log('\n✅ Release Created:');
  console.log(`   ID: ${release.id}`);
  console.log(`   Title: ${release.title}`);
  console.log(`   Performer: ${release.primaryPerformer}`);
  console.log(`   Audio Sources: ${release.audioSources.length}`);
  console.log(`   Platforms: ${[...new Set(release.audioSources.map(s => s.metadata.platform.name))].join(', ')}`);
  
  // Example 2: Direct audio extraction (no post context)
  console.log('\n\n📝 Example 2: Direct Audio Extraction\n');
  
  const directUrl = 'https://soundgasm.net/u/SnakeySmut/Threesome-At-The-Milk-Maid-Cafe';
  console.log(`🔗 Extracting: ${directUrl}`);
  
  const audioSource = await orchestrator.extractAudio(directUrl);
  
  console.log('\n✅ Audio Extracted:');
  console.log(`   Title: ${audioSource.metadata.title}`);
  console.log(`   Author: ${audioSource.metadata.author}`);
  console.log(`   Platform: ${audioSource.metadata.platform.name}`);
  console.log(`   Format: ${audioSource.audio.format}`);
  console.log(`   File: ${audioSource.audio.filePath}`);
  console.log(`   Checksum: ${audioSource.audio.checksum.sha256?.substring(0, 16)}...`);
  
  // Example 3: Check caching
  console.log('\n\n📝 Example 3: Cache Demonstration\n');
  
  console.log('🔄 Extracting same URL again...');
  const startTime = Date.now();
  const cachedSource = await orchestrator.extractAudio(directUrl);
  const elapsed = Date.now() - startTime;
  
  console.log(`⚡ Extraction completed in ${elapsed}ms (cached)`);
  console.log(`   Same checksum: ${cachedSource.audio.checksum.sha256?.substring(0, 16)}...`);
  
  // Show data structure
  console.log('\n\n📊 Data Structure Overview:\n');
  console.log('data/');
  console.log('├── audio/                    # Platform-specific audio files');
  console.log('│   ├── soundgasm/');
  console.log('│   ├── whypit/');
  console.log('│   └── hotaudio/');
  console.log('├── enrichment/               # Post metadata');
  console.log('│   ├── reddit/');
  console.log('│   └── patreon/');
  console.log('├── releases/                 # Aggregated releases');
  console.log('│   ├── index.json           # Global release index');
  console.log('│   └── LurkyDip/            # Per-performer releases');
  console.log('└── .cache/                  # Extraction cache');
}

// Error handling wrapper
async function main() {
  try {
    await demonstrateWorkflow();
    console.log('\n\n✅ Demo completed successfully!');
  } catch (error) {
    console.error('\n❌ Demo failed:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Note about implementation
console.log('⚠️  Note: This is a demonstration of the architecture.');
console.log('    Some extractors may need to be updated to the new schema.\n');

if (require.main === module) {
  main();
}