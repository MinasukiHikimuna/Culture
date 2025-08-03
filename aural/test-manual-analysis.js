#!/usr/bin/env node

const fs = require('fs');

/**
 * Manual analysis of the example post to demonstrate expected output
 */
function manualAnalysis() {
  const postData = JSON.parse(fs.readFileSync('reddit_data/alekirser/1amzk7q.json', 'utf8'));
  const { title, selftext, author } = postData.reddit_data;
  
  console.log('=== MANUAL ANALYSIS ===');
  console.log('Poster username:', author);
  console.log('Title:', title);
  console.log('Post content excerpt:', selftext.substring(0, 100) + '...');
  console.log();
  
  // Manual analysis based on the text
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
      "url": null,
      "fillType": "original",
      "author": "alekirser"
    },
    "analysis_notes": "Original content by performer. Post says 'i'm trying to write more of my own stuff so here's something i came up with'. Signed as '— Ally' indicating nickname usage.",
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
    manualAnalysis();
  } catch (error) {
    console.error('Error:', error.message);
  }
}

module.exports = manualAnalysis;