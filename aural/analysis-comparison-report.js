#!/usr/bin/env node

/**
 * Comparison report between Sonnet reference analysis and LLM output
 * Shows key differences and areas for improvement
 */
function createComparisonReport() {
  console.log('=== ANALYSIS COMPARISON REPORT ===');
  console.log('Wingwoman Post: 1m9aefh');
  console.log('Date: 2025-08-03');
  console.log();

  const sonnetAnalysis = {
    "script": {
      "url": "https://www.reddit.com/r/gonewildaudio/comments/gku9yp/f4m_script_offer_your_bitchy_wingwoman_bitch_to/",
      "fillType": "public",
      "author": "CuteEmUp"
    }
  };

  const llmAnalysis = {
    "script": {
      "url": "https://soundgasm.net/u/alekirser/F4M-Your-Party-Girl-Wingwoman-Takes-You-Home-Instead-Script-Fill",
      "fillType": "public", 
      "author": "alekirser"
    }
  };

  console.log('🔍 KEY DIFFERENCES FOUND:');
  console.log();

  console.log('1. SCRIPT URL EXTRACTION:');
  console.log('   ✅ Sonnet (Correct):');
  console.log('      URL: https://www.reddit.com/r/gonewildaudio/comments/gku9yp/f4m_script_offer_your_bitchy_wingwoman_bitch_to/');
  console.log('      Type: Reddit script offer post');
  console.log();
  console.log('   ❌ LLM (Incorrect):');
  console.log('      URL: https://soundgasm.net/u/alekirser/F4M-Your-Party-Girl-Wingwoman-Takes-You-Home-Instead-Script-Fill');
  console.log('      Type: Audio file (not script)');
  console.log();

  console.log('2. SCRIPT AUTHOR IDENTIFICATION:');
  console.log('   ✅ Sonnet (Correct):');
  console.log('      Author: CuteEmUp');
  console.log('      Source: "by u/CuteEmUp" in post text');
  console.log();
  console.log('   ❌ LLM (Incorrect):');
  console.log('      Author: alekirser');
  console.log('      Issue: Confused performer with script author');
  console.log();

  console.log('3. FILL TYPE CLASSIFICATION:');
  console.log('   ✅ Both Correct:');
  console.log('      Both identified "public" fillType correctly');
  console.log();

  console.log('4. PERFORMER COUNT:');
  console.log('   ✅ Both Correct:');
  console.log('      Both identified single performer correctly');
  console.log();

  console.log('🔧 ROOT CAUSE ANALYSIS:');
  console.log();
  console.log('Problem 1: URL Confusion');
  console.log('  - LLM extracted audio URL instead of script URL');
  console.log('  - Post has both types: [script](script-URL) and [AUDIO HERE](audio-URL)');
  console.log('  - LLM needs to distinguish between these link types');
  console.log();

  console.log('Problem 2: Author Attribution');
  console.log('  - LLM missed "by u/CuteEmUp" attribution');
  console.log('  - Defaulted to post author instead of script author');
  console.log('  - Needs better pattern recognition for "by u/[username]"');
  console.log();

  console.log('Problem 3: Collaboration Handling');
  console.log('  - Sonnet noted HTHarpy as sound designer (separate from performers)');
  console.log('  - LLM mentioned HTHarpy but didn\'t properly categorize');
  console.log('  - Need to distinguish audio production vs voice acting collaboration');
  console.log();

  console.log('📋 IMPROVEMENT RECOMMENDATIONS:');
  console.log();
  console.log('1. Enhance URL Pattern Recognition:');
  console.log('   - Look for [script](URL) vs [AUDIO HERE](URL) patterns');
  console.log('   - Prioritize Reddit URLs for script field');
  console.log('   - Audio platform URLs (Soundgasm/Whyp.it) are NOT script URLs');
  console.log();

  console.log('2. Improve Author Extraction:');
  console.log('   - Search for "by u/[username]" patterns more aggressively');
  console.log('   - "script by u/X" = script author is X, not post author');
  console.log('   - Distinguish between performer (post author) and script author');
  console.log();

  console.log('3. Better Collaboration Detection:');
  console.log('   - "sound design by X" = production collaboration');
  console.log('   - "with [username]" = potential voice acting collaboration');
  console.log('   - Add collaboration field to track non-performer contributors');
  console.log();

  console.log('📊 ACCURACY SCORES:');
  console.log();
  console.log('Field              | Sonnet | LLM    | Match');
  console.log('-------------------|--------|--------|-------');
  console.log('Performer Count    | ✅ 1   | ✅ 1   | ✅ Yes');
  console.log('Primary Performer  | ✅     | ✅     | ✅ Yes');
  console.log('Alternatives       | ✅     | ✅     | ✅ Yes');
  console.log('Series Info        | ✅     | ✅     | ✅ Yes');
  console.log('Script URL         | ✅     | ❌     | ❌ No');
  console.log('Script Author      | ✅     | ❌     | ❌ No');
  console.log('Fill Type          | ✅     | ✅     | ✅ Yes');
  console.log();
  console.log('Overall Accuracy: 71% (5/7 fields correct)');
  console.log('Critical Fields (script analysis): 33% (1/3 correct)');
}

function createPromptImprovements() {
  console.log('\n=== PROMPT IMPROVEMENT SUGGESTIONS ===');
  console.log();

  console.log('Add these specific instructions to the LLM prompt:');
  console.log();

  console.log('```');
  console.log('URL EXTRACTION RULES:');
  console.log('- Script URLs are typically Reddit links to script offer posts');
  console.log('- Audio URLs are typically Soundgasm, Whyp.it, or HotAudio links');
  console.log('- Look for patterns like [script](URL) in the post text');
  console.log('- For script field, extract the Reddit script offer URL, NOT the audio URL');
  console.log('- If post says "AUDIO HERE" or similar, that\'s an audio link, not script');
  console.log();

  console.log('AUTHOR ATTRIBUTION PATTERNS:');
  console.log('- "script by u/[username]" = script author is [username]');
  console.log('- "by u/[username]" after script link = script author is [username]');
  console.log('- "[script](URL) by u/[username]" = script author is [username]');
  console.log('- Do NOT use the post author as script author unless they wrote it');
  console.log('- Look for explicit attribution before defaulting to post author');
  console.log();

  console.log('COLLABORATION PATTERNS:');
  console.log('- "sound design by [username]" = audio production, not voice acting');
  console.log('- "editing by [username]" = post-production, not voice acting');
  console.log('- "with [username]" = potential additional voice actor');
  console.log('- Only count voice actors in performer count, not production team');
  console.log('```');
  console.log();

  console.log('Example improved prompt section:');
  console.log('```');
  console.log('CRITICAL: When analyzing script information:');
  console.log('1. Script URL must be a link to the actual script or script offer post');
  console.log('2. Audio platform URLs (soundgasm.net, whyp.it, hotaudio.net) are NOT script URLs');
  console.log('3. Look for "[script](URL) by u/[username]" patterns');
  console.log('4. Script author is the person who WROTE the script, not who performed it');
  console.log('5. If you see "by u/X" after a script link, X is the script author');
  console.log('```');
}

if (require.main === module) {
  createComparisonReport();
  createPromptImprovements();
}

module.exports = { createComparisonReport, createPromptImprovements };