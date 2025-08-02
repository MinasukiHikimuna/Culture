// AudioSource hook - captures decrypted audio segments as they're processed
// This hooks into the MediaSource/SourceBuffer that receives decrypted audio data

(() => {
  console.log('[AudioSource Hook] Installing...');
  
  // Storage for captured audio segments
  window.__audioCapture = {
    segments: [], // Keep minimal metadata only
    metadata: {},
    sourceBuffers: new WeakMap(),
    totalBytes: 0,
    segmentFiles: [], // Track segment file paths
    sessionId: crypto.randomUUID() // Unique session ID for temp files
  };
  
  // Hook into MediaSource
  if (window.MediaSource) {
    const originalAddSourceBuffer = MediaSource.prototype.addSourceBuffer;
    
    MediaSource.prototype.addSourceBuffer = function(mimeType) {
      console.log('[AudioSource Hook] MediaSource.addSourceBuffer called with:', mimeType);
      
      const sourceBuffer = originalAddSourceBuffer.call(this, mimeType);
      
      // Store mime type
      window.__audioCapture.metadata.mimeType = mimeType;
      
      // Hook into SourceBuffer.appendBuffer
      const originalAppendBuffer = sourceBuffer.appendBuffer;
      let segmentIndex = 0;
      
      sourceBuffer.appendBuffer = function(data) {
        // Only log every 100th segment to reduce noise
        if (segmentIndex % 100 === 0) {
          console.log('[AudioSource Hook] SourceBuffer.appendBuffer called with', data.byteLength, 'bytes');
        }
        
        // Create temp file name for this segment
        const segmentId = segmentIndex.toString().padStart(8, '0');
        const tempFileName = `${window.__audioCapture.sessionId}-${segmentId}.temp`;
        
        // Store minimal segment metadata (no audio data in memory)
        const segment = {
          index: segmentIndex++,
          timestamp: Date.now(),
          tempFileName: tempFileName,
          byteLength: data.byteLength
        };
        
        window.__audioCapture.segments.push(segment);
        window.__audioCapture.segmentFiles.push(tempFileName);
        window.__audioCapture.totalBytes += data.byteLength;
        
        // Write segment data to temp file via Node.js bridge
        if (window.__nodeWriteSegment) {
          const uint8Data = new Uint8Array(data);
          window.__nodeWriteSegment(tempFileName, uint8Data);
        }
        
        // Only log every 100th segment to reduce noise
        if ((segment.index) % 100 === 0) {
          console.log(`[AudioSource Hook] Captured segment ${segment.index} (${data.byteLength} bytes, total: ${window.__audioCapture.totalBytes} bytes)`);
        }
        
        // Call original
        return originalAppendBuffer.call(this, data);
      };
      
      // Hook into remove() to track buffer management
      const originalRemove = sourceBuffer.remove;
      sourceBuffer.remove = function(start, end) {
        console.log(`[AudioSource Hook] SourceBuffer.remove called (${start} - ${end})`);
        return originalRemove.call(this, start, end);
      };
      
      window.__audioCapture.sourceBuffers.set(sourceBuffer, {
        mimeType: mimeType,
        created: Date.now()
      });
      
      return sourceBuffer;
    };
  }
  
  // Also hook into AudioSource if we can find it
  let audioSourceHooked = false;
  const findAudioSource = setInterval(() => {
    // Look for objects that might be AudioSource instances
    const candidates = [
      window.AudioSource,
      window.audioSource,
      window.player,
      document.querySelector('audio')?.player,
      document.querySelector('audio')?._player
    ];
    
    for (const candidate of candidates) {
      if (candidate && !audioSourceHooked) {
        // Check if it has expected methods
        if (candidate.decode || candidate.fetchAB || candidate.fetchKey) {
          console.log('[AudioSource Hook] Found AudioSource instance');
          
          // Hook decode method if it exists
          if (typeof candidate.decode === 'function') {
            const originalDecode = candidate.decode;
            candidate.decode = function(segmentIndex, encryptedData) {
              console.log(`[AudioSource Hook] decode(${segmentIndex}, ${encryptedData.byteLength} bytes)`);
              
              const result = originalDecode.call(this, segmentIndex, encryptedData);
              
              // If decode returns a promise
              if (result && typeof result.then === 'function') {
                result.then(decrypted => {
                  console.log(`[AudioSource Hook] Segment ${segmentIndex} decrypted: ${decrypted.byteLength} bytes`);
                });
              } else if (result) {
                console.log(`[AudioSource Hook] Segment ${segmentIndex} decrypted: ${result.byteLength} bytes`);
              }
              
              return result;
            };
          }
          
          audioSourceHooked = true;
          clearInterval(findAudioSource);
          break;
        }
      }
    }
  }, 500);
  
  // Stop searching after 30 seconds
  setTimeout(() => clearInterval(findAudioSource), 30000);
  
  // Export function to get captured audio
  window.exportAudioCapture = () => {
    const segments = window.__audioCapture.segments;
    console.log(`[AudioSource Hook] Exporting ${segments.length} segments (${window.__audioCapture.totalBytes} bytes total)`);
    
    return {
      metadata: window.__audioCapture.metadata,
      totalBytes: window.__audioCapture.totalBytes,
      segmentCount: segments.length,
      segments: segments,
      captureTime: new Date().toISOString()
    };
  };
  
  // Function to reconstruct audio from temp files
  window.reconstructAudio = () => {
    const segments = window.__audioCapture.segments;
    if (segments.length === 0) {
      console.log('[AudioSource Hook] No segments captured yet');
      return null;
    }
    
    // Sort segments by index to ensure correct order
    segments.sort((a, b) => a.index - b.index);
    
    console.log(`[AudioSource Hook] Starting reconstruction of ${segments.length} segments from temp files`);
    
    // Create combined temp file name
    const combinedTempFile = `${window.__audioCapture.sessionId}.temp`;
    
    // Request Node.js to combine all temp files
    if (window.__nodeCombineSegments) {
      const segmentFiles = segments.map(s => s.tempFileName);
      window.__nodeCombineSegments(segmentFiles, combinedTempFile);
      
      // Create download link pointing to the combined temp file
      const a = document.createElement('a');
      a.href = `file:///${combinedTempFile}`;
      a.download = `captured-audio-${Date.now()}.mp4`;
      a.click();
      
      console.log('[AudioSource Hook] Download started from combined temp file');
      
      return combinedTempFile;
    } else {
      console.error('[AudioSource Hook] Node.js bridge not available for file operations');
      return null;
    }
  };
  
  console.log('[AudioSource Hook] Ready. Functions available:');
  console.log('- window.exportAudioCapture() - Export captured segments as JSON');
  console.log('- window.reconstructAudio() - Reconstruct and download audio file');
})();