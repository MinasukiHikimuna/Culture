# TimePoll Function Analysis - HotAudio's Adaptive Streaming

## Overview
The `timepoll()` function manages which audio segments to fetch based on current playback position and buffer state.

## Key Components

### 1. Want Array `this.want`
- `want[0]`: Start time of desired buffer range
- `want[1]`: End time of desired buffer range
- Updates based on current playback position (`this.el.currentTime`)
- Maintains a 5-second buffer ahead of playback

### 2. Have Set `this.have`
- Tracks which segments are already downloaded/buffered
- Used to determine missing segments

### 3. Missing Segments Logic
```javascript
missingSegments(startTime, endTime, haveSet)
```
- Returns `[firstMissing, lastMissing]` segment indices
- Returns `[-1, -1]` if no segments are missing
- Finds gaps in the buffer between startTime and endTime

### 4. Allowed Segments Check
```javascript
this.allowedSeg(segmentIndex)
```
- Checks if user has permission to access this segment
- Likely related to premium content or preview restrictions
- If segment not allowed, finds next allowed segment

### 5. Fetch Strategy
The function implements several strategies:

1. **Normal Playback**: Fetches 5 seconds ahead
2. **Paused State**: Fetches 15 seconds ahead
3. **Playing State**: Fetches 30 seconds ahead
4. **Adaptive Fetching**: Adjusts based on missing segments

### 6. State Management
- `state == 3`: Currently fetching
- `state == 4`: Ready to fetch
- Aborts stale fetches if playback position changes significantly

## Segment Architecture
The "missing segments" reveal HotAudio's streaming strategy:

1. **Segmented Audio**: Audio is split into small segments (likely ~1 second each)
2. **On-Demand Loading**: Only fetches segments as needed
3. **Buffer Management**: Maintains optimal buffer without downloading entire file
4. **Access Control**: Can restrict access to certain segments

## Implications for Decryption

1. **Partial Downloads**: The system only downloads needed segments
2. **Key Timing**: API keys are likely requested just before segment fetch
3. **Sequential Access**: Segments are typically accessed in order
4. **Buffer Windows**: The 5-30 second buffer window determines API call timing

## The Missing Segments
"Missing segments" aren't actually missing from the file - they're segments that:
1. Haven't been downloaded yet
2. Are within the desired playback buffer range
3. Need to be fetched from the CDN

This is why we see periodic API calls during playback - the player is requesting keys for upcoming segments as it determines they're needed.