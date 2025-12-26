#!/usr/bin/env node

/**
 * HotAudio Extractor v2
 *
 * Complete extractor that:
 * 1. Captures segment keys via JSON.parse hook (avoids tamper detection)
 * 2. Downloads HAX file directly from CDN
 * 3. Decrypts all segments using tree-based key derivation
 * 4. Outputs playable M4A file
 */

import { chromium } from 'playwright';
import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { sha256 } from '@noble/hashes/sha2.js';
import { createHash } from 'crypto';
import fs from 'fs/promises';
import path from 'path';

function sha256hex(data) {
  return createHash('sha256').update(data).digest('hex');
}

class KeyTree {
  constructor(keys) {
    this.keys = new Map();
    for (const [nodeStr, hexKey] of Object.entries(keys)) {
      this.keys.set(parseInt(nodeStr), Buffer.from(hexKey, 'hex'));
    }
  }

  deriveKey(nodeIndex) {
    // Find the highest bit position (tree depth)
    const n = Math.floor(Math.log2(nodeIndex));
    let depth = -1;
    let ancestorKey = null;

    // Search from root (depth 0) to leaf (depth n) for an ancestor we have
    // At depth d, the ancestor node is nodeIndex >> (n - d)
    for (let d = 0; d <= n; d++) {
      const ancestorNode = nodeIndex >> (n - d);
      if (this.keys.has(ancestorNode)) {
        depth = d;
        ancestorKey = this.keys.get(ancestorNode);
        break;
      }
    }

    if (ancestorKey === null) {
      throw new Error(`No applicable key available for node ${nodeIndex}`);
    }

    // Derive from ancestor down to target
    let currentKey = ancestorKey;
    for (let d = depth + 1; d <= n; d++) {
      const childNode = nodeIndex >> (n - d);
      currentKey = sha256(Buffer.concat([currentKey, Uint8Array.from([childNode])]));
    }

    return currentKey;
  }

  getSegmentKey(segmentIndex, segmentCount) {
    const treeDepth = Math.ceil(Math.log2(segmentCount));
    const segmentKeyBase = 1 + (1 << (treeDepth + 1));
    const nodeIndex = segmentKeyBase + segmentIndex;
    return this.deriveKey(nodeIndex);
  }
}

function parseBencode(buffer, offset = 0) {
  const char = String.fromCharCode(buffer[offset]);

  if (char === 'd') {
    const dict = {};
    offset++;
    while (String.fromCharCode(buffer[offset]) !== 'e') {
      const [key, newOffset1] = parseBencode(buffer, offset);
      const [value, newOffset2] = parseBencode(buffer, newOffset1);
      dict[key.toString()] = value;
      offset = newOffset2;
    }
    return [dict, offset + 1];
  } else if (char === 'i') {
    offset++;
    let numStr = '';
    while (String.fromCharCode(buffer[offset]) !== 'e') {
      numStr += String.fromCharCode(buffer[offset]);
      offset++;
    }
    return [parseInt(numStr), offset + 1];
  } else if (char >= '0' && char <= '9') {
    let lenStr = char;
    offset++;
    while (String.fromCharCode(buffer[offset]) !== ':') {
      lenStr += String.fromCharCode(buffer[offset]);
      offset++;
    }
    offset++;
    const len = parseInt(lenStr);
    const str = buffer.slice(offset, offset + len);
    return [str, offset + len];
  } else if (char === 'l') {
    const list = [];
    offset++;
    while (String.fromCharCode(buffer[offset]) !== 'e') {
      const [item, newOffset] = parseBencode(buffer, offset);
      list.push(item);
      offset = newOffset;
    }
    return [list, offset + 1];
  }

  throw new Error(`Unknown bencode type at offset ${offset}: ${char}`);
}

class HotAudioExtractor {
  constructor() {
    this.browser = null;
    this.capturedData = {
      haxUrl: null,
      segmentKeys: {},  // Accumulate keys from multiple responses
      metadata: null,
      segmentCount: null
    };
  }

  async extract(url, options = {}) {
    const { outputDir = './data/hotaudio', outputName, verify = false } = options;

    // Verification data collector
    const verifyData = verify ? {
      url,
      hax: {},
      metadata: {},
      tree_keys: {},
      segments: [],
      output: {}
    } : null;

    console.log('HotAudio Extractor v2');
    console.log('=====================\n');
    console.log(`URL: ${url}\n`);

    // Extract audio slug from URL for output filename
    const urlParts = url.split('/');
    const slug = urlParts[urlParts.length - 1] || 'audio';
    const finalOutputName = outputName || slug;

    // Launch browser - use headless:false to capture initial key
    this.browser = await chromium.launch({
      headless: false,
      channel: 'chrome',
      args: ['--disable-blink-features=AutomationControlled']
    });

    const context = await this.browser.newContext({
      viewport: { width: 1920, height: 1080 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    });

    const page = await context.newPage();

    // Use CDP to capture console messages - this works even before exposeFunction is ready
    const cdpSession = await context.newCDPSession(page);
    await cdpSession.send('Runtime.enable');

    cdpSession.on('Runtime.consoleAPICalled', (event) => {
      if (event.type === 'log') {
        const args = event.args;
        if (args.length >= 2) {
          const prefix = args[0]?.value;
          if (prefix === '__KEYS__') {
            try {
              const keysJson = args[1]?.value;
              const keys = JSON.parse(keysJson);
              const newKeys = Object.keys(keys).filter(k => !this.capturedData.segmentKeys[k]);
              Object.assign(this.capturedData.segmentKeys, keys);
              if (newKeys.length > 0) {
                const keyNums = newKeys.map(Number).sort((a, b) => a - b);
                console.log(`CDP captured ${newKeys.length} new tree node keys: ${keyNums.slice(0, 5).join(',')}${keyNums.length > 5 ? '...' : ''} (total: ${Object.keys(this.capturedData.segmentKeys).length})`);
              }
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
    });

    // Expose functions to receive captured data (as backup)
    await page.exposeFunction('__captureHaxUrl', (url) => {
      this.capturedData.haxUrl = url;
      console.log(`Captured HAX URL: ${url.substring(0, 60)}...`);
    });

    await page.exposeFunction('__captureSegmentKeys', (keys) => {
      // Accumulate keys from multiple responses
      const newKeys = Object.keys(keys).filter(k => !this.capturedData.segmentKeys[k]);
      Object.assign(this.capturedData.segmentKeys, keys);
      if (newKeys.length > 0) {
        console.log(`Captured ${newKeys.length} new tree node keys (total: ${Object.keys(this.capturedData.segmentKeys).length})`);
      }
    });

    await page.exposeFunction('__captureMetadata', (metadata) => {
      this.capturedData.metadata = metadata;
      console.log(`Captured metadata: ${metadata.title || 'untitled'}`);
    });

    // Inject hooks
    await page.addInitScript(() => {
      console.log('[HotAudioExtractor] Installing hooks...');

      // Buffer for captures before exposed functions are ready
      window.__pendingKeyCaptures = [];
      window.__pendingMetadataCaptures = [];

      // Hook JSON.parse to capture segment keys from /api/v1/audio/listen response
      const originalJSONParse = JSON.parse.bind(JSON);
      JSON.parse = function(text) {
        const result = originalJSONParse(text);

        if (result && typeof result === 'object') {
          // Capture segment keys from listen response
          if (result.keys && typeof result.keys === 'object' && !result.tracks) {
            const keyNodes = Object.keys(result.keys).map(Number).sort((a,b) => a-b);
            console.log('[Hook] Captured segment keys:', keyNodes.length, 'nodes:', keyNodes.join(','));

            // Emit via console.log with special prefix for CDP capture
            // This works even before exposeFunction is ready
            console.log('__KEYS__', JSON.stringify(result.keys));

            // Also try the exposed function as backup
            if (window.__captureSegmentKeys) {
              window.__captureSegmentKeys(result.keys);
            } else {
              window.__pendingKeyCaptures.push(result.keys);
              console.log('[Hook] Buffered keys (function not ready), nodes:', keyNodes.join(','));
            }
          }

          // Capture track metadata from decrypted state
          if (result.tracks && Array.isArray(result.tracks)) {
            console.log('[Hook] Captured track metadata');
            if (window.__captureMetadata) {
              const track = result.tracks[0];
              window.__captureMetadata({
                title: track?.title,
                artist: track?.artist,
                duration: track?.duration,
                pid: result.pid
              });
            } else {
              const track = result.tracks[0];
              window.__pendingMetadataCaptures.push({
                title: track?.title,
                artist: track?.artist,
                duration: track?.duration,
                pid: result.pid
              });
            }
          }
        }

        return result;
      };

      console.log('[HotAudioExtractor] Hooks installed');
    });

    // Intercept network to capture HAX URL and listen API responses
    await page.route('**/*', async (route, request) => {
      const reqUrl = request.url();

      // Capture HAX file URL from CDN
      if (reqUrl.includes('.hax') || reqUrl.includes('/a/') && reqUrl.includes('cdn.hotaudio')) {
        this.capturedData.haxUrl = reqUrl;
        console.log(`Captured HAX URL from request: ${reqUrl.substring(0, 60)}...`);
      }

      // For listen API, we need to intercept the response to get keys
      if (reqUrl.includes('/api/v1/audio/listen')) {
        try {
          const response = await route.fetch();
          const body = await response.text();

          // The response is encrypted, but let's log it for debugging
          // The decrypted keys come through JSON.parse hook instead
          console.log(`Listen API response: ${body.length} bytes`);
        } catch (e) {
          // Continue normally if fetch fails
        }
      }

      await route.continue();
    });

    try {
      // Navigate to page
      console.log('Navigating to page...');
      await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });

      // Flush any buffered captures from before exposed functions were ready
      const pendingKeys = await page.evaluate(() => {
        const pending = window.__pendingKeyCaptures || [];
        window.__pendingKeyCaptures = [];
        return pending;
      });
      for (const keys of pendingKeys) {
        const newKeys = Object.keys(keys).filter(k => !this.capturedData.segmentKeys[k]);
        Object.assign(this.capturedData.segmentKeys, keys);
        if (newKeys.length > 0) {
          console.log(`Flushed ${newKeys.length} buffered tree node keys (total: ${Object.keys(this.capturedData.segmentKeys).length})`);
        }
      }

      // Wait for player
      try {
        await page.waitForSelector('#player-playpause', { timeout: 10000 });
        console.log('Player found');
      } catch {
        console.log('Player not found, continuing...');
      }

      // Click play to trigger key capture
      console.log('Clicking play to trigger key exchange...');
      const playButton = await page.$('#player-playpause');
      if (playButton) {
        await playButton.click();
        await page.waitForTimeout(2000);
      }

      // Get total duration from player to know how many keys we need
      const duration = await page.evaluate(() => {
        const progressText = document.querySelector('#player-progress-text');
        if (progressText) {
          const parts = progressText.textContent.split('/');
          if (parts.length === 2) {
            const [min, sec] = parts[1].trim().split(':').map(Number);
            return min * 60 + sec;
          }
        }
        return null;
      });

      if (duration) {
        console.log(`Total duration: ${Math.floor(duration / 60)}:${(duration % 60).toString().padStart(2, '0')}`);

        // For long files, seek through to collect all keys
        // Each segment is ~1 second, keys are fetched in batches
        const estimatedSegments = Math.ceil(duration);

        if (estimatedSegments > 200) {
          console.log(`Long audio detected (${estimatedSegments} segments). Collecting all keys...`);

          const progressBar = page.locator('#player-progress-bar');
          const box = await progressBar.boundingBox();

          // Helper to find uncovered segments
          const findUncoveredSegments = (segmentCount) => {
            const treeDepth = Math.ceil(Math.log2(segmentCount));
            const segmentKeyBase = 1 + (1 << (treeDepth + 1));
            const keys = Object.keys(this.capturedData.segmentKeys).map(Number);

            const uncovered = [];
            for (let seg = 0; seg < segmentCount; seg++) {
              const node = segmentKeyBase + seg;
              const n = Math.floor(Math.log2(node));
              let covered = false;

              for (let d = 0; d <= n; d++) {
                const ancestor = node >> (n - d);
                if (keys.includes(ancestor)) {
                  covered = true;
                  break;
                }
              }

              if (!covered) {
                uncovered.push(seg);
              }
            }
            return uncovered;
          };

          // Helper to get seek positions for uncovered ranges
          const getSeekPositionsForGaps = (uncovered, segmentCount) => {
            if (uncovered.length === 0) return [];

            // Group into ranges and seek to start of each range
            const positions = new Set();
            let rangeStart = uncovered[0];

            for (let i = 1; i <= uncovered.length; i++) {
              if (i === uncovered.length || uncovered[i] !== uncovered[i - 1] + 1) {
                // End of range, add seek position for range start
                positions.add(rangeStart / segmentCount);
                if (i < uncovered.length) {
                  rangeStart = uncovered[i];
                }
              }
            }

            return Array.from(positions).sort((a, b) => a - b);
          };

          // Let the audio play through naturally to collect all keys
          console.log('  Letting audio play through to collect all keys...');
          console.log(`  Audio duration: ${Math.floor(duration / 60)}:${Math.floor(duration % 60).toString().padStart(2, '0')}`);

          // Make sure audio is playing
          const playButton = await page.$('#player-playpause');
          if (playButton) {
            await playButton.click();
            await page.waitForTimeout(1000);
          }

          const startTime = Date.now();
          const maxWaitMs = (duration + 60) * 1000; // duration + 1 minute buffer

          while (Date.now() - startTime < maxWaitMs) {
            await page.waitForTimeout(10000); // Check every 10 seconds

            const currentKeys = Object.keys(this.capturedData.segmentKeys).length;
            const uncovered = findUncoveredSegments(estimatedSegments);
            const elapsed = Math.floor((Date.now() - startTime) / 1000);

            // Get current playback position from the player UI
            const timeInfo = await page.evaluate(() => {
              const progressText = document.querySelector('#player-progress-text');
              return progressText ? progressText.textContent : 'unknown';
            });

            console.log(`  ${elapsed}s: ${timeInfo} - ${currentKeys} keys, ${estimatedSegments - uncovered.length}/${estimatedSegments} covered`);

            if (uncovered.length === 0) {
              console.log('  All segments covered!');
              break;
            }
          }

          const finalUncovered = findUncoveredSegments(estimatedSegments);
          console.log(`Collected ${Object.keys(this.capturedData.segmentKeys).length} tree node keys`);
          console.log(`Coverage: ${estimatedSegments - finalUncovered.length}/${estimatedSegments} segments`);
        }
      }

      // Check if we have all required data
      if (Object.keys(this.capturedData.segmentKeys).length === 0) {
        throw new Error('Failed to capture segment keys');
      }

      if (!this.capturedData.haxUrl) {
        // Try to extract from page config
        const haxUrl = await page.evaluate(() => {
          if (window.__ha_state?.tracks?.[0]?.src) {
            return window.__ha_state.tracks[0].src;
          }
          return null;
        });

        if (haxUrl) {
          this.capturedData.haxUrl = haxUrl;
          console.log(`Extracted HAX URL from page: ${haxUrl.substring(0, 60)}...`);
        } else {
          throw new Error('Failed to capture HAX URL');
        }
      }

      // Close browser - we have what we need
      await this.browser.close();
      this.browser = null;

      // Download HAX file directly from CDN
      console.log('\nDownloading HAX file from CDN...');
      const haxResponse = await fetch(this.capturedData.haxUrl);
      if (!haxResponse.ok) {
        throw new Error(`Failed to download HAX: ${haxResponse.status}`);
      }

      const haxBuffer = Buffer.from(await haxResponse.arrayBuffer());
      console.log(`Downloaded ${(haxBuffer.length / 1024).toFixed(1)} KB`);

      // Collect HAX verification data
      if (verifyData) {
        verifyData.hax = {
          url: this.capturedData.haxUrl,
          size_bytes: haxBuffer.length,
          sha256: sha256hex(haxBuffer),
          header_hex: haxBuffer.slice(0, 16).toString('hex')
        };
      }

      // Parse HAX file
      console.log('\nParsing HAX file...');
      const magic = haxBuffer.slice(0, 4).toString('utf8');
      if (magic !== 'HAX0') {
        throw new Error(`Invalid HAX magic: ${magic}`);
      }

      // Find metadata start
      let metaStart = 16;
      while (metaStart < 64 && haxBuffer[metaStart] !== 0x64) {
        metaStart++;
      }

      const [metadata] = parseBencode(haxBuffer, metaStart);
      console.log(`  Codec: ${metadata.codec.toString()}`);
      console.log(`  Duration: ${(metadata.durationMs / 1000).toFixed(1)}s`);
      console.log(`  Segments: ${metadata.segmentCount}`);

      // Collect metadata verification data
      if (verifyData) {
        verifyData.metadata = {
          base_key_hex: Buffer.from(metadata.baseKey).toString('hex'),
          codec: metadata.codec.toString(),
          duration_ms: metadata.durationMs,
          segment_count: metadata.segmentCount,
          orig_hash_hex: metadata.origHash ? Buffer.from(metadata.origHash).toString('hex') : null
        };
        verifyData.tree_keys = { ...this.capturedData.segmentKeys };
      }

      // Parse segment table
      const segmentData = metadata.segments;
      const segments = [];
      for (let i = 0; i < metadata.segmentCount; i++) {
        const offset = segmentData.readUInt32LE(i * 8);
        const pts = segmentData.readUInt32LE(i * 8 + 4);
        segments.push({ offset, pts, index: i });
      }

      // Calculate sizes
      for (let i = 0; i < segments.length - 1; i++) {
        segments[i].size = segments[i + 1].offset - segments[i].offset;
      }
      segments[segments.length - 1].size = haxBuffer.length - segments[segments.length - 1].offset;

      // Build key tree and decrypt
      console.log('\nDecrypting segments...');
      console.log(`Key nodes available: ${Object.keys(this.capturedData.segmentKeys).sort((a,b) => Number(a) - Number(b)).slice(0, 20).join(', ')}...`);
      const keyTree = new KeyTree(this.capturedData.segmentKeys);
      const decryptedSegments = [];

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (seg.size === 0) continue;

        try {
          const segKey = keyTree.getSegmentKey(i, metadata.segmentCount);
          const ciphertext = haxBuffer.subarray(seg.offset, seg.offset + seg.size);

          const nonce = new Uint8Array(12);
          const cipher = chacha20poly1305(segKey, nonce);
          const decrypted = cipher.decrypt(ciphertext);

          decryptedSegments.push(decrypted);

          // Collect segment verification data
          if (verifyData) {
            verifyData.segments.push({
              index: i,
              offset: seg.offset,
              size: seg.size,
              encrypted_sha256: sha256hex(ciphertext),
              decrypted_sha256: sha256hex(Buffer.from(decrypted))
            });
          }

          if (i === 0 || i === segments.length - 1) {
            console.log(`  Segment ${i}: ${decrypted.length} bytes`);
          } else if (i === 1) {
            console.log(`  ... decrypting ${segments.length - 2} more segments ...`);
          }
        } catch (e) {
          const failedNode = 4097 + i; // Approximate - assuming base
          console.log(`  Segment ${i} failed (node ${failedNode}): ${e.message}`);
          console.log(`  Looking for ancestors: ${[1,2,4,8,16,32,64,128,256,512,1024,2048,4096].filter(n => n < failedNode).join(', ')}`);
          console.log(`  We have: ${Object.keys(this.capturedData.segmentKeys).slice(0, 20).join(', ')}...`);
          break;
        }
      }

      console.log(`\nDecrypted ${decryptedSegments.length}/${segments.length} segments`);

      // Concatenate and save
      await fs.mkdir(outputDir, { recursive: true });
      const outputPath = path.join(outputDir, `${finalOutputName}.m4a`);

      const fullAudio = Buffer.concat(decryptedSegments);
      await fs.writeFile(outputPath, fullAudio);

      // Collect output verification data
      if (verifyData) {
        verifyData.output = {
          path: outputPath,
          size_bytes: fullAudio.length,
          sha256: sha256hex(fullAudio)
        };
      }

      const result = {
        success: true,
        outputPath,
        duration: metadata.durationMs / 1000,
        size: fullAudio.length,
        segments: decryptedSegments.length,
        metadata: this.capturedData.metadata,
        verifyData
      };

      console.log(`\nSaved: ${outputPath}`);
      console.log(`Size: ${(fullAudio.length / 1024).toFixed(1)} KB`);
      console.log(`Duration: ${(metadata.durationMs / 1000).toFixed(1)}s`);

      // Output verification JSON if requested
      if (verifyData) {
        console.log('\n--- VERIFICATION DATA ---');
        console.log(JSON.stringify(verifyData, null, 2));
      }

      return result;

    } catch (error) {
      console.error(`\nError: ${error.message}`);
      throw error;
    } finally {
      if (this.browser) {
        await this.browser.close();
      }
    }
  }
}

// CLI
async function main() {
  const args = process.argv.slice(2);
  const verify = args.includes('--verify');
  const positionalArgs = args.filter(arg => !arg.startsWith('--'));

  const url = positionalArgs[0];
  const outputName = positionalArgs[1];

  if (!url) {
    console.log('Usage: node hotaudio-extractor-v2.js <hotaudio-url> [output-name] [--verify]');
    console.log('');
    console.log('Options:');
    console.log('  --verify    Output detailed verification JSON with checksums');
    console.log('');
    console.log('Example:');
    console.log('  node hotaudio-extractor-v2.js https://hotaudio.net/u/User/Audio-Title');
    console.log('  node hotaudio-extractor-v2.js https://hotaudio.net/u/User/Audio-Title --verify');
    process.exit(1);
  }

  const extractor = new HotAudioExtractor();
  await extractor.extract(url, { outputName, verify });
}

main().catch(console.error);

export { HotAudioExtractor, KeyTree, parseBencode };
