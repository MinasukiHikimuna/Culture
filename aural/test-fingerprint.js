#!/usr/bin/env node

/**
 * Test script to validate Stashapp fingerprint API on scene 215
 *
 * This tests the fileSetFingerprints mutation to verify we can set
 * custom audio_sha256 fingerprints on scene files.
 *
 * Usage:
 *   node test-fingerprint.js
 */

const path = require('path');

// Load .env from project root
require('dotenv').config({ path: path.join(__dirname, '.env') });

const { StashappClient } = require('./stashapp-importer');

async function testFingerprint() {
  const client = new StashappClient();

  console.log('Testing Stashapp fingerprint API...\n');

  // 1. Get scene 215's file ID and current fingerprints
  console.log('Step 1: Fetching scene 215 details...');
  const sceneQuery = `
    query GetScene($id: ID!) {
      findScene(id: $id) {
        id
        title
        files {
          id
          path
          basename
          fingerprints {
            type
            value
          }
        }
      }
    }
  `;

  const scene = await client.query(sceneQuery, { id: '215' });

  if (!scene.findScene) {
    console.error('Error: Scene 215 not found');
    process.exit(1);
  }

  console.log(`  Scene ID: ${scene.findScene.id}`);
  console.log(`  Title: ${scene.findScene.title}`);

  const file = scene.findScene.files?.[0];
  if (!file) {
    console.error('Error: Scene 215 has no files');
    process.exit(1);
  }

  console.log(`  File ID: ${file.id}`);
  console.log(`  File basename: ${file.basename}`);
  console.log(`  Current fingerprints: ${JSON.stringify(file.fingerprints, null, 2)}`);

  // Check if audio_sha256 fingerprint already exists
  const existingFp = file.fingerprints?.find(fp => fp.type === 'audio_sha256');
  if (existingFp) {
    console.log(`\nNote: audio_sha256 fingerprint already exists: ${existingFp.value}`);
    console.log('Test completed - fingerprint API is working!');
    return;
  }

  // 2. Set the audio_sha256 fingerprint
  console.log('\nStep 2: Setting audio_sha256 fingerprint...');
  const sha256 = 'a6be988139b04302547d9df7cb9ca77f08dc8d9dc3fab0110385a32e8e519503';
  console.log(`  SHA256: ${sha256}`);

  const setFpQuery = `
    mutation SetFingerprints($input: FileSetFingerprintsInput!) {
      fileSetFingerprints(input: $input)
    }
  `;

  try {
    await client.query(setFpQuery, {
      input: {
        id: file.id,
        fingerprints: [{ type: 'audio_sha256', value: sha256 }]
      }
    });
    console.log('  Fingerprint mutation executed successfully');
  } catch (error) {
    console.error('  Error setting fingerprint:', error.message);
    process.exit(1);
  }

  // 3. Verify the fingerprint was set
  console.log('\nStep 3: Verifying fingerprint was set...');
  const verifyScene = await client.query(sceneQuery, { id: '215' });
  const verifyFile = verifyScene.findScene?.files?.[0];

  console.log(`  Updated fingerprints: ${JSON.stringify(verifyFile?.fingerprints, null, 2)}`);

  const newFp = verifyFile?.fingerprints?.find(fp => fp.type === 'audio_sha256');
  if (newFp && newFp.value === sha256) {
    console.log('\n✓ SUCCESS: Fingerprint API is working correctly!');
    console.log(`  audio_sha256 fingerprint set to: ${newFp.value}`);
  } else {
    console.error('\n✗ FAILED: Fingerprint was not set correctly');
    process.exit(1);
  }
}

testFingerprint().catch(error => {
  console.error('Error:', error.message);
  process.exit(1);
});
