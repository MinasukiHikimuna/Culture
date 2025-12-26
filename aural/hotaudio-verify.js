#!/usr/bin/env node

/**
 * HotAudio Decryption Verification Script
 *
 * Runs the extractor with --verify flag and compares output against
 * known good values to validate the decryption implementation.
 *
 * Usage:
 *   node hotaudio-verify.js                    # Run all test cases
 *   node hotaudio-verify.js --case=1           # Run specific case
 *   node hotaudio-verify.js --check-output     # Verify existing M4A files only
 */

import { spawn } from 'child_process';
import { createHash } from 'crypto';
import fs from 'fs/promises';
import path from 'path';

// Known good values from verified extractions
const TEST_CASES = {
  // Case 1: Short audio (37 seconds) - receives root key (node 1)
  "case_1": {
    name: "Short Audio (37s)",
    url: "https://hotaudio.net/u/SweetnEvil86/Lurky-and-Emma-Airplane-Collab-Blooper",
    expected: {
      hax: {
        size_bytes: 310092,
        sha256: "a2b02d7509e5d397cc9333fdb904e45c6ff579b41ecec01d07ceb5c223249ed9",
        header_hex: "48415830e4060b0006020000"
      },
      metadata: {
        base_key_hex: "9d75bba6e2f08bebd4886ddc177da300",
        codec: "aac",
        duration_ms: 37175,
        segment_count: 37
      },
      output: {
        size_bytes: 721388,
        sha256: "0e3e7d6c3117278b2efb5356d35a23e5c2f6cd0a64b62b53633ca3a5252d94eb"
      },
      // Key derivation info for documentation
      key_info: {
        tree_depth: 6,
        segment_key_base: 129,
        root_key_node: 1,
        note: "Short files receive root key (node 1), allowing full tree derivation"
      }
    }
  },

  // Case 2: Long audio (7:12) - receives progressive subtree keys
  "case_2": {
    name: "Long Audio (7:12)",
    url: "https://hotaudio.net/u/Lurkydip/BBW-Belly-Blowjob-Wank",
    expected: {
      hax: {
        size_bytes: 8116321,
        sha256: "2f0818966979f38f9b48f43e0d564d3b4888ea00d3b61fc4f77ac48acb97d127"
      },
      metadata: {
        codec: "aac",
        duration_ms: 432810,  // ~7:12.81
        segment_count: 432
      },
      output: {
        size_bytes: 8116321,
        sha256: "9477eb72c99299f0fe7c95593146c0464da57956e860b17a92bdaaa375f991c1"
      },
      // Key derivation info
      key_info: {
        tree_depth: 9,
        segment_key_base: 1025,
        note: "Long files receive subtree keys progressively during playback"
      }
    }
  }
};

function green(text) { return `\x1b[32m${text}\x1b[0m`; }
function red(text) { return `\x1b[31m${text}\x1b[0m`; }
function yellow(text) { return `\x1b[33m${text}\x1b[0m`; }
function dim(text) { return `\x1b[2m${text}\x1b[0m`; }

async function sha256File(filePath) {
  const data = await fs.readFile(filePath);
  return createHash('sha256').update(data).digest('hex');
}

async function runExtractor(url) {
  return new Promise((resolve, reject) => {
    const proc = spawn('node', ['hotaudio-extractor-v2.js', url, '--verify'], {
      cwd: process.cwd(),
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Extractor exited with code ${code}\n${stderr}`));
        return;
      }

      // Extract verification JSON from output
      const marker = '--- VERIFICATION DATA ---';
      const markerIndex = stdout.indexOf(marker);
      if (markerIndex === -1) {
        reject(new Error('No verification data found in output'));
        return;
      }

      const jsonStr = stdout.substring(markerIndex + marker.length).trim();
      try {
        const verifyData = JSON.parse(jsonStr);
        resolve(verifyData);
      } catch (e) {
        reject(new Error(`Failed to parse verification JSON: ${e.message}`));
      }
    });

    proc.on('error', reject);
  });
}

function compareValues(path, actual, expected) {
  const results = [];

  if (expected === undefined || expected === null) {
    return results;
  }

  if (typeof expected === 'object' && !Array.isArray(expected)) {
    for (const [key, expVal] of Object.entries(expected)) {
      if (key === 'note' || key === 'key_info') continue; // Skip documentation fields

      const actVal = actual?.[key];
      const subPath = `${path}.${key}`;

      if (typeof expVal === 'object') {
        results.push(...compareValues(subPath, actVal, expVal));
      } else {
        const match = actVal === expVal;
        results.push({
          path: subPath,
          expected: expVal,
          actual: actVal,
          match
        });
      }
    }
  }

  return results;
}

async function verifyCase(caseId, testCase, skipExtraction = false) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`TEST CASE: ${testCase.name}`);
  console.log(`URL: ${testCase.url}`);
  console.log('='.repeat(60));

  let verifyData;

  if (skipExtraction) {
    // Just verify existing output file
    const slug = testCase.url.split('/').pop();
    const outputPath = `./data/hotaudio/${slug}.m4a`;

    try {
      const stat = await fs.stat(outputPath);
      const sha256 = await sha256File(outputPath);

      verifyData = {
        output: {
          path: outputPath,
          size_bytes: stat.size,
          sha256
        }
      };
      console.log(`\nChecking existing file: ${outputPath}`);

      // In check-output mode, only compare output fields
      const comparisons = compareValues('', verifyData, { output: testCase.expected.output });
      let passed = 0;
      let failed = 0;

      console.log('\n--- VERIFICATION RESULTS ---\n');

      for (const comp of comparisons) {
        if (comp.match) {
          console.log(green(`✓ ${comp.path}`));
          console.log(dim(`  ${comp.actual}`));
          passed++;
        } else {
          console.log(red(`✗ ${comp.path}`));
          console.log(`  Expected: ${comp.expected}`);
          console.log(`  Actual:   ${comp.actual}`);
          failed++;
        }
      }

      console.log(`\n${'─'.repeat(40)}`);
      if (failed === 0) {
        console.log(green(`All ${passed} checks passed`));
      } else {
        console.log(red(`${failed} failed`), `/ ${passed} passed`);
      }

      return { passed, failed, skipped: 0 };
    } catch (e) {
      console.log(red(`\nFile not found: ${outputPath}`));
      return { passed: 0, failed: 1, skipped: 0 };
    }
  } else {
    console.log('\nRunning extractor with --verify...');
    console.log(dim('(This will open a browser window)'));

    try {
      verifyData = await runExtractor(testCase.url);
      console.log(green('\nExtraction completed successfully'));
    } catch (e) {
      console.log(red(`\nExtraction failed: ${e.message}`));
      return { passed: 0, failed: 1, skipped: 0 };
    }
  }

  // Compare values
  console.log('\n--- VERIFICATION RESULTS ---\n');

  const comparisons = compareValues('', verifyData, testCase.expected);
  let passed = 0;
  let failed = 0;

  for (const comp of comparisons) {
    if (comp.match) {
      console.log(green(`✓ ${comp.path}`));
      console.log(dim(`  ${comp.actual}`));
      passed++;
    } else {
      console.log(red(`✗ ${comp.path}`));
      console.log(`  Expected: ${comp.expected}`);
      console.log(`  Actual:   ${comp.actual}`);
      failed++;
    }
  }

  // Summary
  console.log(`\n${'─'.repeat(40)}`);
  if (failed === 0) {
    console.log(green(`All ${passed} checks passed`));
  } else {
    console.log(red(`${failed} failed`), `/ ${passed} passed`);
  }

  return { passed, failed, skipped: 0 };
}

async function verifyOutputIntegrity(outputPath, expectedSha256) {
  try {
    const actual = await sha256File(outputPath);
    const match = actual === expectedSha256;

    console.log(`\nFile: ${outputPath}`);
    console.log(`Expected SHA256: ${expectedSha256}`);
    console.log(`Actual SHA256:   ${actual}`);
    console.log(match ? green('✓ Match') : red('✗ Mismatch'));

    return match;
  } catch (e) {
    console.log(red(`Error reading file: ${e.message}`));
    return false;
  }
}

async function main() {
  const args = process.argv.slice(2);
  const checkOutputOnly = args.includes('--check-output');
  const caseArg = args.find(a => a.startsWith('--case='));
  const specificCase = caseArg ? caseArg.split('=')[1] : null;

  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║         HotAudio Decryption Verification Suite             ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  if (checkOutputOnly) {
    console.log('\nMode: Checking existing output files only');
  } else {
    console.log('\nMode: Full extraction and verification');
    console.log(yellow('Note: This will open browser windows and may take several minutes'));
  }

  let totalPassed = 0;
  let totalFailed = 0;

  const casesToRun = specificCase
    ? { [`case_${specificCase}`]: TEST_CASES[`case_${specificCase}`] }
    : TEST_CASES;

  for (const [caseId, testCase] of Object.entries(casesToRun)) {
    if (!testCase) {
      console.log(red(`\nUnknown test case: ${specificCase}`));
      continue;
    }

    const result = await verifyCase(caseId, testCase, checkOutputOnly);
    totalPassed += result.passed;
    totalFailed += result.failed;
  }

  // Final summary
  console.log('\n' + '═'.repeat(60));
  console.log('FINAL SUMMARY');
  console.log('═'.repeat(60));
  console.log(`Total checks: ${totalPassed + totalFailed}`);
  console.log(`Passed: ${green(totalPassed.toString())}`);
  console.log(`Failed: ${totalFailed > 0 ? red(totalFailed.toString()) : '0'}`);

  if (totalFailed === 0) {
    console.log(green('\n✓ All verification checks passed!'));
    process.exit(0);
  } else {
    console.log(red(`\n✗ ${totalFailed} check(s) failed`));
    process.exit(1);
  }
}

main().catch(e => {
  console.error(red(`Error: ${e.message}`));
  process.exit(1);
});
