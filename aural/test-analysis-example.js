#!/usr/bin/env node

const fs = require('fs');

/**
 * Demonstrates the expected analysis output for the wingwoman post
 */
function analyzeWingwomanPost() {
  const postData = JSON.parse(fs.readFileSync('H:\\Git\\gwasi-extractor\\reddit_data\\alekirser\\1m9aefh_f4m-your-party-girl-wingwoman-takes-you-home-inste.json', 'utf8'));
  const { title, selftext, author } = postData.reddit_data;
  
  console.log('=== ANALYZING WINGWOMAN POST ===');
  console.log('Poster username:', author);
  console.log('Post content analysis:');
  console.log('- Title contains "[Script Fill]"');
  console.log('- Content mentions "script by u/CuteEmUp"');  
  console.log('- Has URL: https://www.reddit.com/r/gonewildaudio/comments/gku9yp/f4M_script_offer_your_bitchy_wingwoman_bitch_to/');
  console.log('- Sound design by HTHarpy');
  console.log('- Signed as "— Ally"');
  console.log();
  
  // Expected analysis based on manual review
  const analysis = {
    "performers": {
      "count": 1,
      "primary": "alekirser", 
      "additional": [],
      "confidence": "high"
    },
    "alternatives": {
      "hasAlternatives": false,
      "versions": [],
      "description": "Single F4M version",
      "confidence": "high"
    },
    "series": {
      "isPartOfSeries": false,
      "hasPrequels": false,
      "hasSequels": false,
      "seriesName": null,
      "partNumber": null,
      "confidence": "high"
    },
    "script": {
      "url": "https://www.reddit.com/r/gonewildaudio/comments/gku9yp/f4M_script_offer_your_bitchy_wingwoman_bitch_to/",
      "fillType": "public",
      "author": "CuteEmUp"
    },
    "analysis_notes": "Script fill by alekirser of public script originally by u/CuteEmUp. Sound design collaboration with HTHarpy. Poster signs as 'Ally' (nickname).",
    "metadata": {
      "post_id": postData.post_id,
      "username": postData.username,
      "title": title,
      "date": postData.date,
      "reddit_url": postData.reddit_url,
      "analyzed_at": new Date().toISOString()
    }
  };
  
  console.log('Expected analysis result:');
  console.log(JSON.stringify(analysis, null, 2));
  
  return analysis;
}

if (require.main === module) {
  try {
    analyzeWingwomanPost();
  } catch (error) {
    console.error('Error:', error.message);
  }
}

module.exports = analyzeWingwomanPost;