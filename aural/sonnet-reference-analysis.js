#!/usr/bin/env node

const fs = require('fs');

/**
 * Sonnet (Claude) reference analysis for the wingwoman post
 * This serves as a gold standard for comparison with LLM-generated analyses
 */
function createSonnetReferenceAnalysis() {
  const postData = JSON.parse(fs.readFileSync('H:\\Git\\gwasi-extractor\\reddit_data\\alekirser\\1m9aefh_f4m-your-party-girl-wingwoman-takes-you-home-inste.json', 'utf8'));
  const { title, selftext, author } = postData.reddit_data;
  
  console.log('=== SONNET REFERENCE ANALYSIS ===');
  console.log('Analyzing wingwoman post with Claude Sonnet 4');
  console.log('Post ID:', postData.post_id);
  console.log('Author:', author);
  console.log('Title:', title);
  console.log();
  
  // Claude Sonnet's detailed analysis based on the post content
  const analysis = {
    "performers": {
      "count": 1,
      "primary": "alekirser",
      "additional": [],
      "confidence": "high",
      "analysis_notes": "Single performer confirmed. Post is by alekirser, signed as '— Ally' (nickname). No mention of other voice actors."
    },
    "alternatives": {
      "hasAlternatives": false,
      "versions": [],
      "description": "Single F4M version only",
      "confidence": "high",
      "analysis_notes": "No alternative versions mentioned. Single audio file on Soundgasm. No mentions of M4F variants, SFX options, or multiple endings."
    },
    "series": {
      "isPartOfSeries": false,
      "hasPrequels": false,
      "hasSequels": false,
      "seriesName": null,
      "partNumber": null,
      "confidence": "high",
      "analysis_notes": "Standalone script fill. No references to previous parts, sequels, or ongoing storylines."
    },
    "script": {
      "url": "https://www.reddit.com/r/gonewildaudio/comments/gku9yp/f4m_script_offer_your_bitchy_wingwoman_bitch_to/",
      "fillType": "public",
      "author": "CuteEmUp",
      "analysis_notes": "Clear script fill. Post explicitly states '[script](URL) by u/CuteEmUp'. This is a public script that was offered on Reddit. The URL leads to the original script offer post, not a direct script file."
    },
    "collaboration": {
      "hasCollaboration": true,
      "collaborators": ["HTHarpy"],
      "collaborationType": "sound_design",
      "analysis_notes": "Post mentions 'sound design by HTHarpy' - this is audio production collaboration, not voice acting collaboration."
    },
    "metadata": {
      "post_id": postData.post_id,
      "username": postData.username,
      "title": title,
      "date": postData.date,
      "reddit_url": postData.reddit_url,
      "analyzed_at": new Date().toISOString(),
      "analyzer": "claude-sonnet-4",
      "post_type": "script_fill"
    },
    "key_identifiers": {
      "script_indicators": [
        "Title contains '[Script Fill]'",
        "Post starts with '[script](URL) by u/CuteEmUp'",
        "Clear attribution to script author"
      ],
      "audio_links": [
        "https://soundgasm.net/u/alekirser/F4M-Your-Party-Girl-Wingwoman-Takes-You-Home-Instead-Script-Fill"
      ],
      "script_links": [
        "https://www.reddit.com/r/gonewildaudio/comments/gku9yp/f4m_script_offer_your_bitchy_wingwoman_bitch_to/"
      ],
      "collaboration_mentions": [
        "sound design by HTHarpy"
      ],
      "nickname_usage": [
        "— Ally (alekirser's nickname)"
      ]
    },
    "analysis_summary": "This is a straightforward script fill by alekirser of a public script originally written by u/CuteEmUp. The post clearly distinguishes between the script URL (Reddit post) and audio URL (Soundgasm). HTHarpy provided sound design collaboration. The performer uses the nickname 'Ally' but the actual username 'alekirser' should be used for data consistency."
  };
  
  console.log('Sonnet reference analysis:');
  console.log(JSON.stringify(analysis, null, 2));
  
  return analysis;
}

function createComparisonFramework() {
  console.log('\n=== COMPARISON FRAMEWORK ===');
  console.log('Key analysis points for LLM prompt improvement:');
  console.log();
  console.log('1. URL DISTINCTION:');
  console.log('   - Script URL: Reddit post with script content');
  console.log('   - Audio URL: Soundgasm/Whyp.it/HotAudio with actual audio');
  console.log('   - Must extract the correct URL for script field');
  console.log();
  console.log('2. SCRIPT AUTHOR IDENTIFICATION:');
  console.log('   - Look for "by u/[username]" patterns');
  console.log('   - Distinguish between performer and script author');
  console.log('   - Use actual Reddit usernames, not nicknames');
  console.log();
  console.log('3. COLLABORATION DETECTION:');
  console.log('   - "sound design by [username]" = audio production collaboration');
  console.log('   - This is NOT additional voice acting performers');
  console.log('   - Should be noted separately from performer count');
  console.log();
  console.log('4. FILL TYPE CLASSIFICATION:');
  console.log('   - "Script Fill" in title + script URL = "public"');
  console.log('   - Clear script attribution = "public"');
  console.log('   - "private fill" mentioned = "private"');
  console.log('   - No script reference = "original" or "unknown"');
  console.log();
  console.log('5. NICKNAME HANDLING:');
  console.log('   - "— Ally" signature = nickname for alekirser');
  console.log('   - Always use actual Reddit username in author field');
  console.log('   - Note nickname usage in analysis_notes if needed');
}

if (require.main === module) {
  try {
    createSonnetReferenceAnalysis();
    createComparisonFramework();
  } catch (error) {
    console.error('Error:', error.message);
  }
}

module.exports = { createSonnetReferenceAnalysis, createComparisonFramework };