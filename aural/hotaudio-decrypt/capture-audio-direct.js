// Direct audio capture script - hooks into AudioSource/MediaSource to capture decrypted audio

const playwright = require('playwright');
const fs = require('fs').promises;
const path = require('path');

const OUTPUT_DIR = './captured-audio';

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function extractHotAudioLinks(page) {
  // Extract all HotAudio links from the current page
  const links = await page.evaluate(() => {
    const hotAudioLinks = [];
    const links = document.querySelectorAll('a[href*="hotaudio.net/u/"]');
    
    links.forEach(link => {
      const href = link.href;
      const match = href.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
      if (match) {
        const [, user, audio] = match;
        const title = link.textContent.trim() || `${user}/${audio}`;
        hotAudioLinks.push({
          url: href,
          title: title,
          user: user,
          audio: audio
        });
      }
    });
    
    return hotAudioLinks;
  });
  
  return links;
}

async function saveStoryMap(userDir, audioName, storyMap) {
  const mapFile = path.join(userDir, `${audioName}.story-map.txt`);
  let content = '';
  
  function buildMapContent(node, depth = 0) {
    const indent = '  '.repeat(depth);
    content += `${indent}${node.title}: ${node.url}\n`;
    
    if (node.children && node.children.length > 0) {
      node.children.forEach(child => {
        buildMapContent(child, depth + 1);
      });
    }
  }
  
  buildMapContent(storyMap);
  await fs.writeFile(mapFile, content);
  console.log(`Story map saved to: ${mapFile}`);
}

async function createNewPage(context, tempDir) {
  // Create a new page (tab) for this capture session
  const page = await context.newPage();
  
  // Inject Node.js bridge functions for file operations
  await page.exposeFunction('__nodeWriteSegment', async (tempFileName, uint8Data) => {
    const tempFilePath = path.join(tempDir, tempFileName);
    await fs.writeFile(tempFilePath, Buffer.from(uint8Data));
  });
  
  await page.exposeFunction('__nodeCombineSegments', async (segmentFiles, combinedTempFile) => {
    const combinedTempPath = path.join(tempDir, combinedTempFile);
    const writeStream = require('fs').createWriteStream(combinedTempPath);
    
    return new Promise((resolve, reject) => {
      let processed = 0;
      
      const processNext = async () => {
        if (processed >= segmentFiles.length) {
          writeStream.end();
          resolve(combinedTempPath);
          return;
        }
        
        const segmentFile = segmentFiles[processed];
        const segmentPath = path.join(tempDir, segmentFile);
        
        try {
          const data = await fs.readFile(segmentPath);
          writeStream.write(data);
          // Clean up individual segment file
          await fs.unlink(segmentPath);
          processed++;
          setImmediate(processNext);
        } catch (e) {
          console.warn(`Warning: Could not read segment file ${segmentFile}:`, e.message);
          processed++;
          setImmediate(processNext);
        }
      };
      
      processNext();
    });
  });
  
  // Inject the AudioSource hook before navigation
  await page.addInitScript({ path: './audiosource-hook.js' });
  console.log('AudioSource hook injected');
  
  // Monitor console for hook messages
  page.on('console', msg => {
    if (msg.text().includes('[AudioSource Hook]')) {
      console.log(msg.text());
    }
  });
  
  return page;
}

async function captureAudioAndLinks(context, url, baseUserDir, audioName, capturedUrls, storyMap, tempDir, depth = 0, previousPage = null) {
  if (capturedUrls.has(url)) {
    console.log(`Skipping already captured: ${url}`);
    return;
  }
  
  // Create audio-specific directory
  const audioDir = path.join(baseUserDir, audioName);
  await fs.mkdir(audioDir, { recursive: true });
  
  // Check if audio file already exists
  const audioFile = path.join(audioDir, `${audioName}.mp4`);
  let audioExists = false;
  try {
    await fs.access(audioFile);
    console.log(`${'  '.repeat(depth)}Audio file already exists: ${audioFile}`);
    audioExists = true;
  } catch (e) {
    // File doesn't exist, will need to capture
  }
  
  console.log(`${'  '.repeat(depth)}Processing: ${audioName} (${url})`);
  capturedUrls.add(url);
  
  // Create a new tab to check for links (and capture if needed)
  console.log(`${'  '.repeat(depth)}Creating new tab for ${audioName}...`);
  let page = await createNewPage(context, tempDir);
  
  // Close the previous tab if it exists
  if (previousPage) {
    console.log(`${'  '.repeat(depth)}Closing previous tab...`);
    try {
      await previousPage.close();
    } catch (e) {
      // Page might already be closed
    }
  }
  
  try {
    // Navigate to the audio page
    console.log(`${'  '.repeat(depth)}Navigating to: ${url}`);
    await page.goto(url, { waitUntil: 'networkidle' });
  
  // Wait for player to load
  try {
    await page.waitForSelector('#player-progress-text', { timeout: 10000 });
  } catch (e) {
    console.log(`${'  '.repeat(depth)}No player found on ${url}, skipping...`);
    return;
  }
  
  // Only capture audio if it doesn't already exist
  if (!audioExists) {
    console.log(`${'  '.repeat(depth)}Capturing audio for ${audioName}...`);
    
    // Save the HTML page content
    console.log(`${'  '.repeat(depth)}Saving HTML page content...`);
    try {
      const htmlContent = await page.content();
      const htmlFile = path.join(audioDir, `${audioName}.html`);
      await fs.writeFile(htmlFile, htmlContent);
      console.log(`${'  '.repeat(depth)}HTML page saved to: ${htmlFile}`);
    } catch (error) {
      console.error(`${'  '.repeat(depth)}Error saving HTML:`, error);
    }
    
    // Get audio duration
    const durationText = await page.$eval('#player-progress-text', el => el.textContent);
    console.log(`${'  '.repeat(depth)}Audio duration:`, durationText);
    const totalDuration = durationText.split(' / ')[1];
  
  // Wait for everything to load
  await sleep(3000);
  
  // Click play button
  console.log(`${'  '.repeat(depth)}Starting playback...`);
  const playButton = await page.$('#player-playpause');
  if (playButton) {
    await playButton.click();
  }
  
  // Monitor playback progress
  let lastProgress = '';
  let playbackComplete = false;
  const progressInterval = setInterval(async () => {
    try {
      const progress = await page.$eval('#player-progress-text', el => el.textContent);
      if (progress !== lastProgress) {
        console.log(`${'  '.repeat(depth)}[Progress]`, progress);
        lastProgress = progress;
        
        // Check if playback has ended
        const [current, total] = progress.split(' / ');
        if (current === total || progress.includes('PLAYBACK ERROR')) {
          playbackComplete = true;
          clearInterval(progressInterval);
          console.log(`${'  '.repeat(depth)}Playback complete!`);
        }
      }
      
      // Also check captured data
      const captureStatus = await page.evaluate(() => {
        if (window.__audioCapture) {
          return {
            segments: window.__audioCapture.segments.length,
            totalBytes: window.__audioCapture.totalBytes
          };
        }
        return null;
      });
      
      if (captureStatus) {
        console.log(`${'  '.repeat(depth)}[Capture Status] ${captureStatus.segments} segments, ${(captureStatus.totalBytes / 1024 / 1024).toFixed(2)} MB`);
      }
    } catch (e) {
      // Player might have been removed
    }
  }, 5000);
  
  console.log(`${'  '.repeat(depth)}Waiting for playback to complete (duration: ${totalDuration})...`);
  
  // Wait for playback to complete
  while (!playbackComplete) {
    await sleep(10000);
    
    try {
      await page.$eval('#player-progress-text', el => el.textContent);
    } catch (e) {
      console.log(`${'  '.repeat(depth)}Player element not found, stopping...`);
      break;
    }
  }
  
  clearInterval(progressInterval);
  
  // Wait a bit more to ensure all segments are captured
  await sleep(2000);
  
  // Export captured data
  console.log(`${'  '.repeat(depth)}Exporting captured audio data...`);
  
  try {
    const capturedData = await page.evaluate(() => {
      if (window.exportAudioCapture) {
        return window.exportAudioCapture();
      }
      return null;
    });
    
    if (capturedData && capturedData.segments.length > 0) {
      // Save metadata
      const metadataFile = path.join(audioDir, `${audioName}.metadata.json`);
      await fs.writeFile(metadataFile, JSON.stringify({
        url: url,
        duration: totalDuration,
        metadata: capturedData.metadata,
        totalBytes: capturedData.totalBytes,
        segmentCount: capturedData.segmentCount,
        captureTime: capturedData.captureTime
      }, null, 2));
      
      console.log(`${'  '.repeat(depth)}Metadata saved to: ${metadataFile}`);
      console.log(`${'  '.repeat(depth)}Captured ${capturedData.segmentCount} segments (${(capturedData.totalBytes / 1024 / 1024).toFixed(2)} MB)`);
      
      // Reconstruct audio file from temp files
      console.log(`${'  '.repeat(depth)}Reconstructing audio file from temp files...`);
      
      // Trigger browser-side file combination
      await page.evaluate(() => {
        if (window.reconstructAudio) {
          window.reconstructAudio();
        }
      });
      
      // Get the combined temp file from the page
      const combinedTempFile = await page.evaluate(() => {
        if (window.__audioCapture && window.__audioCapture.sessionId) {
          return `${window.__audioCapture.sessionId}.temp`;
        }
        return null;
      });
      
      if (combinedTempFile) {
        const combinedTempPath = path.join(tempDir, combinedTempFile);
        const audioFile = path.join(audioDir, `${audioName}.mp4`);
        
        // Move the combined temp file to final location
        try {
          await fs.rename(combinedTempPath, audioFile);
          const stats = await fs.stat(audioFile);
          console.log(`${'  '.repeat(depth)}Audio file saved to: ${audioFile}`);
          console.log(`${'  '.repeat(depth)}File size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
        } catch (e) {
          console.error(`${'  '.repeat(depth)}Error moving temp file:`, e);
        }
      } else {
        console.error(`${'  '.repeat(depth)}No combined temp file found`);
      }
      
      console.log(`${'  '.repeat(depth)}Capture complete!`);
    } else {
      console.error(`${'  '.repeat(depth)}No audio data was captured for ${audioName}`);
    }
  } catch (error) {
    console.error(`${'  '.repeat(depth)}Error exporting captured data:`, error);
  }
  } else {
    console.log(`${'  '.repeat(depth)}Skipping capture for existing audio: ${audioName}`);
  }
  
  // Extract links for depth-first traversal (regardless of whether audio exists)
  const links = await extractHotAudioLinks(page);
  console.log(`${'  '.repeat(depth)}Found ${links.length} HotAudio links on this page`);
  
  // Update story map
  if (!storyMap.children) {
    storyMap.children = [];
  }
  
  for (const link of links) {
    if (!capturedUrls.has(link.url)) {
      const childNode = {
        title: link.title,
        url: link.url,
        user: link.user,
        audio: link.audio,
        children: []
      };
      storyMap.children.push(childNode);
      
      // Recursively capture linked audio (depth-first)
      // The current page will be closed by the child call
      page = await captureAudioAndLinks(context, link.url, baseUserDir, link.audio, capturedUrls, childNode, tempDir, depth + 1, page);
    }
  }
  } finally {
    // Return the page so it can be closed by the next call
    // Don't close it here as it will be closed by the next audio or at the end
  }
  
  return page;
}

async function main() {
  // Parse command line arguments
  const args = process.argv.slice(2);
  let follow = false;
  let targetUrl = null;
  let outputDirectory = OUTPUT_DIR;
  
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--follow') {
      follow = true;
    } else if (args[i] === '--output-directory' || args[i] === '-o') {
      if (i + 1 < args.length) {
        outputDirectory = args[i + 1];
        i++; // Skip next argument since it's the directory path
      } else {
        console.error('Error: --output-directory requires a path argument');
        process.exit(1);
      }
    } else if (!targetUrl) {
      targetUrl = args[i];
    }
  }
  
  if (!targetUrl) {
    console.error('Usage: node capture-audio-direct.js [--follow] [--output-directory <path>] <hotaudio-url>');
    console.error('');
    console.error('Options:');
    console.error('  --follow                Follow all linked HotAudio content (Choose Your Own Adventure mode)');
    console.error('  --output-directory, -o  Specify output directory (default: ./captured-audio)');
    console.error('');
    console.error('Examples:');
    console.error('  node capture-audio-direct.js https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up');
    console.error('  node capture-audio-direct.js --follow https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up');
    console.error('  node capture-audio-direct.js --output-directory /path/to/my/audio https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up');
    console.error('  node capture-audio-direct.js --follow -o ~/Downloads/hotaudio https://hotaudio.net/u/The_LUST_Project/T1-Wake-Up');
    process.exit(1);
  }
  
  const TARGET_URL = targetUrl;
  console.log('Starting direct audio capture...');
  console.log('Target URL:', TARGET_URL);
  console.log('Follow mode:', follow ? 'ENABLED' : 'DISABLED');
  console.log('Output directory:', outputDirectory);
  
  // Extract user and audio name from URL
  const urlMatch = TARGET_URL.match(/hotaudio\.net\/u\/([^\/]+)\/([^\/\?]+)/);
  if (!urlMatch) {
    console.error('Invalid HotAudio URL format. Expected: https://hotaudio.net/u/<user>/<audio-name>');
    process.exit(1);
  }
  
  const [, userName, audioName] = urlMatch;
  console.log('User:', userName);
  console.log('Audio:', audioName);
  
  // Create output directory structure
  const userDir = path.join(outputDirectory, userName);
  await fs.mkdir(userDir, { recursive: true });
  
  // Create temp directory for segments
  const tempDir = path.join(outputDirectory, 'temp');
  await fs.mkdir(tempDir, { recursive: true });

  // Launch browser once and reuse it
  console.log('Launching browser...');
  const browser = await playwright.chromium.launch({
    headless: false,
    channel: 'chrome',
    args: ['--disable-blink-features=AutomationControlled']
  });

  // Create a single context for all tabs
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  // Create a placeholder tab to keep the window open
  const placeholderPage = await context.newPage();
  await placeholderPage.goto('about:blank');
  console.log('Created placeholder tab to keep window open');

  try {
    if (follow) {
    // Follow mode: recursively capture all linked audio
    const capturedUrls = new Set();
    const storyMap = {
      title: audioName,
      url: TARGET_URL,
      user: userName,
      audio: audioName,
      children: []
    };

    console.log('\n=== FOLLOW MODE: Starting recursive capture ===');
    let lastPage = null;
    lastPage = await captureAudioAndLinks(context, TARGET_URL, userDir, audioName, capturedUrls, storyMap, tempDir, 0);
    
    // Save the complete story map
    console.log('\n=== Saving complete story map ===');
    await saveStoryMap(userDir, audioName, storyMap);
    
    // Close the last page from follow mode
    if (lastPage) {
      console.log('Closing last capture tab...');
      try {
        await lastPage.close();
      } catch (e) {
        // Page might already be closed
      }
    }
    
    console.log(`\n=== FOLLOW MODE COMPLETE ===`);
    console.log(`Total audio files captured: ${capturedUrls.size}`);
    console.log(`Story map saved for: ${audioName}`);
  } else {
    // Single mode: capture only the specified audio
    // Create audio-specific directory
    const audioDir = path.join(userDir, audioName);
    await fs.mkdir(audioDir, { recursive: true });
    
    // Check if audio file already exists
    const audioFile = path.join(audioDir, `${audioName}.mp4`);
    try {
      await fs.access(audioFile);
      console.log(`Audio file already exists, skipping: ${audioFile}`);
      return;
    } catch (e) {
      // File doesn't exist, proceed with capture
    }
    
    // Create a new tab
    console.log('Creating new tab...');
    const page = await createNewPage(context, tempDir);
    
    try {
      console.log('Navigating to:', TARGET_URL);
      await page.goto(TARGET_URL, { waitUntil: 'networkidle' });
    
    // Wait for player to load
    await page.waitForSelector('#player-progress-text', { timeout: 10000 });
    
    // Save the HTML page content
    console.log('Saving HTML page content...');
    try {
      const htmlContent = await page.content();
      const htmlFile = path.join(audioDir, `${audioName}.html`);
      await fs.writeFile(htmlFile, htmlContent);
      console.log(`HTML page saved to: ${htmlFile}`);
    } catch (error) {
      console.error('Error saving HTML:', error);
    }
    
    // Get audio duration
    const durationText = await page.$eval('#player-progress-text', el => el.textContent);
    console.log('Audio duration:', durationText);
    const totalDuration = durationText.split(' / ')[1];
    
    // Wait for everything to load
    await sleep(3000);
    
    // Click play button
    console.log('Starting playback...');
    const playButton = await page.$('#player-playpause');
    if (playButton) {
      await playButton.click();
    }
    
    // Monitor playback progress
    let lastProgress = '';
    let playbackComplete = false;
    const progressInterval = setInterval(async () => {
      try {
        const progress = await page.$eval('#player-progress-text', el => el.textContent);
        if (progress !== lastProgress) {
          console.log('[Progress]', progress);
          lastProgress = progress;
          
          // Check if playback has ended
          const [current, total] = progress.split(' / ');
          if (current === total || progress.includes('PLAYBACK ERROR')) {
            playbackComplete = true;
            clearInterval(progressInterval);
            console.log('Playback complete!');
          }
        }
        
        // Also check captured data
        const captureStatus = await page.evaluate(() => {
          if (window.__audioCapture) {
            return {
              segments: window.__audioCapture.segments.length,
              totalBytes: window.__audioCapture.totalBytes
            };
          }
          return null;
        });
        
        if (captureStatus) {
          console.log(`[Capture Status] ${captureStatus.segments} segments, ${(captureStatus.totalBytes / 1024 / 1024).toFixed(2)} MB`);
        }
      } catch (e) {
        // Player might have been removed
      }
    }, 5000);
    
    console.log(`Waiting for playback to complete (duration: ${totalDuration})...`);
    
    // Wait for playback to complete
    while (!playbackComplete) {
      await sleep(10000);
      
      try {
        await page.$eval('#player-progress-text', el => el.textContent);
      } catch (e) {
        console.log('Player element not found, stopping...');
        break;
      }
    }
    
    clearInterval(progressInterval);
    
    // Wait a bit more to ensure all segments are captured
    await sleep(2000);
    
    // Export captured data
    console.log('\nExporting captured audio data...');
    
    try {
      const capturedData = await page.evaluate(() => {
        if (window.exportAudioCapture) {
          return window.exportAudioCapture();
        }
        return null;
      });
      
      if (capturedData && capturedData.segments.length > 0) {
        // Save metadata
        const metadataFile = path.join(audioDir, `${audioName}.metadata.json`);
        await fs.writeFile(metadataFile, JSON.stringify({
          url: TARGET_URL,
          duration: totalDuration,
          metadata: capturedData.metadata,
          totalBytes: capturedData.totalBytes,
          segmentCount: capturedData.segmentCount,
          captureTime: capturedData.captureTime
        }, null, 2));
        
        console.log(`Metadata saved to: ${metadataFile}`);
        console.log(`Captured ${capturedData.segmentCount} segments (${(capturedData.totalBytes / 1024 / 1024).toFixed(2)} MB)`);
        
        // Reconstruct audio file from temp files
        console.log('\nReconstructing audio file from temp files...');
        
        // Trigger browser-side file combination
        await page.evaluate(() => {
          if (window.reconstructAudio) {
            window.reconstructAudio();
          }
        });
        
        // Get the combined temp file from the page
        const combinedTempFile = await page.evaluate(() => {
          if (window.__audioCapture && window.__audioCapture.sessionId) {
            return `${window.__audioCapture.sessionId}.temp`;
          }
          return null;
        });
        
        if (combinedTempFile) {
          const combinedTempPath = path.join(tempDir, combinedTempFile);
          const audioFile = path.join(audioDir, `${audioName}.mp4`);
          
          // Move the combined temp file to final location
          try {
            await fs.rename(combinedTempPath, audioFile);
            const stats = await fs.stat(audioFile);
            console.log(`Audio file saved to: ${audioFile}`);
            console.log(`File size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
          } catch (e) {
            console.error('Error moving temp file:', e);
          }
        } else {
          console.error('No combined temp file found');
        }
        
        console.log('\nCapture complete! Audio has been saved.');
      } else {
        console.error('No audio data was captured');
      }
    } catch (error) {
      console.error('Error exporting captured data:', error);
    }
    } finally {
      // Close the tab
      console.log('\nClosing tab...');
      await page.close();
    }
  }
  } finally {
    // Close placeholder tab and browser at the end
    console.log('\nClosing placeholder tab...');
    await placeholderPage.close();
    console.log('Closing browser...');
    await browser.close();
  }
}

main().catch(console.error);