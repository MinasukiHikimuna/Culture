# HotAudio Encryption Case Studies

This document provides detailed technical analysis of HotAudio's encryption system based on
two extracted audio files: a short 37-second audio and a longer 7-minute audio.

## Overview of Encryption System

HotAudio uses a sophisticated multi-layer encryption system:

1. **Key Exchange**: X25519 ECDH (Elliptic Curve Diffie-Hellman)
2. **Symmetric Encryption**: ChaCha20-Poly1305 (authenticated encryption)
3. **Key Derivation**: Tree-based SHA256 derivation for segment keys

### File Format: HAX (HotAudio eXtended)

```
┌─────────────────────────────────────┐
│ Magic: "HAX0" (4 bytes)             │
├─────────────────────────────────────┤
│ Header: 12 bytes (unknown purpose)  │
├─────────────────────────────────────┤
│ Bencode Metadata Dictionary         │
│   - baseKey: 16 bytes               │
│   - codec: "aac"                    │
│   - durationMs: integer             │
│   - segmentCount: integer           │
│   - loudness: dict                  │
│   - origHash: 16 bytes              │
├─────────────────────────────────────┤
│ Segment Table                       │
│   - 8 bytes per segment             │
│   - 4 bytes: data offset (LE)       │
│   - 4 bytes: PTS timestamp (LE)     │
├─────────────────────────────────────┤
│ Encrypted Audio Segments            │
│   - ChaCha20-Poly1305 encrypted     │
│   - 12-byte zero nonce              │
│   - 16-byte auth tag at end         │
└─────────────────────────────────────┘
```

### Key Tree Structure

HotAudio uses a binary tree for key derivation, allowing efficient key distribution:

```
                    Node 1 (root)
                   /            \
             Node 2              Node 3
            /      \            /      \
        Node 4    Node 5    Node 6    Node 7
        ...       ...       ...       ...

Segment keys at leaves: Node (segmentKeyBase + segmentIndex)
```

**Key Derivation Formula:**
```
segmentKey = sha256(ancestorKey || ancestorNodeIndex)
```

Where ancestor is the highest node in the tree that covers this segment.

---

## Case Study 1: Short Audio (37 seconds)

### Source Information

| Field | Value |
|-------|-------|
| Title | Lurky and Emma Airplane Collab Blooper |
| Performer | SweetnEvil86 |
| URL | https://hotaudio.net/u/SweetnEvil86/Lurky-and-Emma-Airplane-Collab-Blooper |
| CDN URL | https://cdn.hotaudio.net/a/kntvq9q2y25yqn48dqe1ezd300.hax |
| Duration | 37.175 seconds |
| Output Size | 721,388 bytes (704 KB) |

### HAX File Structure

| Field | Value |
|-------|-------|
| File Size | 310,092 bytes (CDN) / 722,660 bytes (captured with response data) |
| Magic | `HAX0` |
| Header Bytes | `e4060b0006020000a2000000` |
| Bencode Range | bytes 16-213 |

### Metadata (from Bencode)

| Field | Value |
|-------|-------|
| Base Key | `9d75bba6e2f08bebd4886ddc177da300` (16 bytes hex) |
| Codec | `aac` |
| Duration | 37,175 ms |
| Segment Count | 37 |
| Flags | 1 |
| Original Hash | `0e3e7d6c1127278b2efb5356d35a23e5` |

### Loudness Data

| Field | Value |
|-------|-------|
| Integrated (I) | 23,693 |
| LRAH (High) | 33,957 |
| LRAL (Low) | 17,682 |
| MH (Max High) | 42,397 |
| ML (Max Low) | 156 |

### Sample Segment Table (first 5 segments)

| Segment | Offset | PTS | Size |
|---------|--------|-----|------|
| 0 | 680 | 0 | 18,155 bytes |
| 1 | 18,835 | 1,021 | 8,427 bytes |
| 2 | 27,262 | 2,046 | 16,076 bytes |
| 3 | 43,338 | 3,067 | 17,269 bytes |
| 4 | 60,607 | 4,092 | 14,165 bytes |

### Encryption Keys

#### API Response Data

| Field | Value |
|-------|-------|
| PID | 2475 |
| Session Key (32 bytes) | `9dc11904a74ffb913571ad79d1ccc7bcf801f08188575c9110a5770439ebcf37` |

#### Tree Key (from `/api/v1/audio/listen`)

| Node | Key (hex) |
|------|-----------|
| **1** (root) | `b506d00c5e7fbe600262b656834c12b6a78e0e2a2e7a90ea15b01485234bbc19` |

> **Note:** For short files, only the root key (Node 1) is provided. All segment keys
> are derived from this single root key.

#### Captured Ephemeral X25519 Private Key

```
7e57e88c36c87d0ac2fac990044d25f2e82654098535160a893bef191fad410b
```

This is the client's ephemeral private key used in the X25519 key exchange.

### Key Derivation Details

| Parameter | Value |
|-----------|-------|
| Tree Depth | 6 (for 37 segments) |
| Segment Key Base | 129 (= 1 + 2^7) |
| Segment 0 Key Node | 129 |
| Segment 36 Key Node | 165 |

**Derivation Example (Segment 0):**
```
segmentKeyNode = 129
ancestorChain = [129, 64, 32, 16, 8, 4, 2, 1]
// Server provides Node 1, so derive down:
key_64 = sha256(key_1 || 1)    // left child
key_32 = sha256(key_64 || 64)  // left child
key_16 = sha256(key_32 || 32)  // left child
...
key_129 = sha256(key_64 || 64) // segment key
```

---

## Case Study 2: Long Audio (7 minutes)

### Source Information

| Field | Value |
|-------|-------|
| Title | BBW Belly Blowjob Wank |
| Performer | Lurkydip |
| URL | https://hotaudio.net/u/Lurkydip/BBW-Belly-Blowjob-Wank |
| Duration | ~432 seconds (7:12) |
| Segment Count | 432 |
| Output Size | 8,116,321 bytes (7.7 MB) |

### Key Distribution Pattern

For longer files, the server optimizes by NOT sending the root key. Instead, it sends
subtree keys that cover specific ranges of segments:

**Tree Parameters:**
| Parameter | Value |
|-----------|-------|
| Tree Depth | 9 (for 432 segments) |
| Segment Key Base | 1025 (= 1 + 2^10) |
| Segments per subtree | 128 (depth-7 node) |

### Keys Captured During Playback

The server progressively provides keys as playback advances:

| Node | Covers Segments | When Provided |
|------|-----------------|---------------|
| 8 | 0-127 | Initial request |
| 9 | 128-255 | ~2 min into playback |
| 5 | 256-383 | ~4 min into playback |
| 11 | 384-431 (partial) | ~6 min into playback |

> **Critical Insight:** The server does NOT provide Node 1 (root) for long files.
> You must collect keys progressively during playback.

### Extraction Strategy

For long files, the extraction must:

1. **Start playback** - Click play and let audio run
2. **Collect keys progressively** - Keys arrive via `/api/v1/audio/listen` as needed
3. **Wait for full duration** - Must play through entire audio to get all keys
4. **Use CDP capture** - Use Chrome DevTools Protocol to capture keys before `exposeFunction` is ready

---

## Technical Implementation Notes

### Key Capture via CDP

The first API response often arrives before Playwright's `exposeFunction` is ready.
To capture it, use CDP:

```javascript
const cdpSession = await context.newCDPSession(page);
await cdpSession.send('Runtime.enable');

cdpSession.on('Runtime.consoleAPICalled', (event) => {
  if (event.type === 'log') {
    const args = event.args;
    if (args.length >= 2 && args[0]?.value === '__KEYS__') {
      const keysJson = args[1]?.value;
      const keys = JSON.parse(keysJson);
      // Store keys...
    }
  }
});
```

### Init Script for Key Capture

Hook `JSON.parse` to emit keys via console:

```javascript
await page.addInitScript(() => {
  const originalJSONParse = JSON.parse.bind(JSON);
  JSON.parse = function(text) {
    const result = originalJSONParse(text);
    if (result?.keys && typeof result.keys === 'object') {
      console.log('__KEYS__', JSON.stringify(result.keys));
    }
    return result;
  };
});
```

### ChaCha20-Poly1305 Decryption

Each segment is decrypted independently:

```javascript
const crypto = require('crypto');

function decryptSegment(encryptedData, key) {
  // ChaCha20-Poly1305 with 12-byte zero nonce
  const nonce = Buffer.alloc(12);
  const authTag = encryptedData.slice(-16);
  const ciphertext = encryptedData.slice(0, -16);

  const decipher = crypto.createDecipheriv('chacha20-poly1305', key, nonce, {
    authTagLength: 16
  });
  decipher.setAuthTag(authTag);

  return Buffer.concat([
    decipher.update(ciphertext),
    decipher.final()
  ]);
}
```

---

## Comparison: Short vs Long Files

| Aspect | Short (37s) | Long (7min) |
|--------|-------------|-------------|
| Segments | 37 | 432 |
| Tree Depth | 6 | 9 |
| Root Key Provided | Yes | No |
| Keys in Initial Response | 1 (root) | 1-2 (subtree) |
| Key Collection | Instant | Progressive |
| Extraction Time | ~5 seconds | ~8 minutes |

---

## Troubleshooting

### Problem: Missing Keys for Some Segments

**Cause:** Audio didn't play through completely; keys arrive progressively.

**Solution:** Let audio play through entire duration with buffer time:
```javascript
const maxWaitMs = (duration + 60) * 1000;
```

### Problem: First Keys Not Captured

**Cause:** `exposeFunction` not ready when first API response arrives.

**Solution:** Use CDP to capture console messages directly.

### Problem: Seeking Doesn't Fetch Keys

**Cause:** HotAudio uses MediaSource API; seeking repositions within buffered data.

**Solution:** Let audio play naturally rather than seeking.

---

## References

- [X25519 ECDH](https://en.wikipedia.org/wiki/Curve25519)
- [ChaCha20-Poly1305](https://en.wikipedia.org/wiki/ChaCha20-Poly1305)
- [Bencode Format](https://wiki.theory.org/BitTorrentSpecification#Bencoding)
- [Playwright CDP](https://playwright.dev/docs/api/class-cdpsession)
