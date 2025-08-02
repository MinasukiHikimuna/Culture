// HotAudio Nozzle.js - Annotated Version
// This file contains the decryption logic for HotAudio's encrypted audio format

// ========================================
// UTILITY FUNCTIONS
// ========================================

// Hex encoding lookup tables
var HEX_CHARS = "0123456789abcdef";
var HEX_ENCODE_TABLE = [];
var HEX_DECODE_TABLE = [];

// Initialize hex lookup tables
for (let i = 0; i < 256; i++) {
  HEX_ENCODE_TABLE[i] = HEX_CHARS[(i >> 4) & 15] + HEX_CHARS[i & 15];
  if (i < 16) {
    if (i < 10) {
      HEX_DECODE_TABLE[48 + i] = i;  // '0'-'9'
    } else {
      HEX_DECODE_TABLE[87 + i] = i;  // 'a'-'f'
    }
  }
}

// Convert byte array to hex string
var bytesToHex = (bytes) => {
  let length = bytes.length;
  let result = "";
  let index = 0;
  while (index < length) {
    result += HEX_ENCODE_TABLE[bytes[index++]];
  }
  return result;
};

// Concatenate multiple Uint8Arrays into one
var concatUint8Arrays = (arrays, totalLength = 0) => {
  let count = arrays.length || 0;
  if (!totalLength) {
    let i = count;
    while (i--) {
      totalLength += arrays[i].length;
    }
  }
  let result = new Uint8Array(totalLength);
  let offset = totalLength;
  let i = count;
  while (i--) {
    offset -= arrays[i].length;
    result.set(arrays[i], offset);
  }
  return result;
};

// ========================================
// TEXT ENCODING/DECODING
// ========================================

var textDecoder = new TextDecoder();
var decodeText = (bytes, encoding) => 
  encoding ? new TextDecoder(encoding).decode(bytes) : textDecoder.decode(bytes);

var textEncoder = new TextEncoder();
var encodeText = (str) => textEncoder.encode(str);

// ========================================
// CRYPTO SETUP
// ========================================

var globalWindow = typeof window < "u" ? window : self;
var cryptoObj = globalWindow.crypto || globalWindow.msCrypto || {};
var subtleCrypto = cryptoObj.subtle || cryptoObj.webkitSubtle;

// ========================================
// BENCODE IMPLEMENTATION
// ========================================

// Main bencode function
function bencode(data, buffer, offset) {
  let chunks = [];
  let result = null;
  
  bencode._encode(chunks, data);
  result = concatUint8Arrays(chunks);
  bencode.bytes = result.length;
  
  if (ArrayBuffer.isView(buffer)) {
    buffer.set(result, offset);
    return buffer;
  }
  return result;
}

bencode.bytes = -1;
bencode._floatConversionDetected = false;

// Encode dispatcher based on type
bencode._encode = function(chunks, data) {
  if (data != null) {
    switch (getType(data)) {
      case "object":
        bencode.dict(chunks, data);
        break;
      case "map":
        bencode.dictMap(chunks, data);
        break;
      case "array":
        bencode.list(chunks, data);
        break;
      case "set":
        bencode.listSet(chunks, data);
        break;
      case "string":
        bencode.string(chunks, data);
        break;
      case "number":
        bencode.number(chunks, data);
        break;
      case "boolean":
        bencode.number(chunks, data);
        break;
      case "arraybufferview":
        bencode.buffer(chunks, data);
        break;
      case "arraybuffer":
        bencode.buffer(chunks, new Uint8Array(data));
        break;
    }
  }
};

// Helper to determine JavaScript type
function getType(obj) {
  if (ArrayBuffer.isView(obj)) return "arraybufferview";
  if (Array.isArray(obj)) return "array";
  if (obj instanceof Number) return "number";
  if (obj instanceof Boolean) return "boolean";
  if (obj instanceof Set) return "set";
  if (obj instanceof Map) return "map";
  if (obj instanceof String) return "string";
  if (obj instanceof ArrayBuffer) return "arraybuffer";
  return typeof obj;
}

// ========================================
// HAX FILE FORMAT PARSER
// ========================================

class HaxFileParser {
  constructor() {
    this.segments = [];
    this.keyMap = new WeakMap();
  }

  // Derive encryption key for a segment using hierarchical approach
  deriveKey(segmentIndex) {
    let depth = Math.ceil(Math.log2(segmentIndex));
    let level = 0;
    let key = null;
    
    // Find the highest level key available
    for (let i = 0; i <= depth; i++) {
      let nodeIndex = segmentIndex >> (depth - i);
      let nodeKey = this.keyMap.get(nodeIndex);
      if (nodeKey) {
        level = i;
        key = nodeKey;
        break;
      }
    }
    
    if (key === null) {
      throw new Error("no applicable key available");
    }
    
    // Derive child keys down to the target level
    for (let i = level + 1; i <= depth; i++) {
      // SHA-256 hash of parent key + direction bit
      key = SHA256.create()
        .update(key)
        .update(Uint8Array.from([segmentIndex >> (depth - i)]))
        .digest();
    }
    
    return key;
  }

  // Decrypt a segment using ChaCha20-Poly1305
  decode(segmentIndex, encryptedData) {
    // Calculate key tree offset
    // The key tree has size: 1 + 2^(ceil(log2(segments)) + 1)
    // This creates a complete binary tree with enough nodes
    let keyTreeSize = 1 + (1 << (Math.ceil(Math.log2(this.segments.length)) + 1));
    let keyIndex = keyTreeSize + segmentIndex;
    
    // Get the derived key for this specific segment
    let key = this.deriveKey(keyIndex);
    
    // Decrypt using ChaCha20-Poly1305 AEAD
    // - Key: 32-byte derived key
    // - Nonce: 12 zero bytes
    // - The function is called "Ot" in the minified code
    return ChaCha20Poly1305(key, new Uint8Array(12)).decrypt(new Uint8Array(encryptedData));
  }
  
  // Handle extra metadata after main HAX data
  handleExtra(extraData) {
    // Decrypt extra data using segment index -1
    let decrypted = this.decode(-1, extraData);
    // Parse as bencode
    this.ext = bencode.decode(decrypted);
  }

  static headerLength(buffer) {
    return HaxFileParser.uint32(new Uint8Array(buffer), 8);
  }

  static uint32(bytes, offset) {
    return bytes[offset] + 
           (bytes[offset + 1] << 8) + 
           (bytes[offset + 2] << 16) + 
           (bytes[offset + 3] << 24);
  }
}

// ========================================
// AUDIO SOURCE CLASS
// ========================================

class AudioSource {
  constructor(config) {
    this.config = config;
    this.segments = [];
    this.keys = {};
    this.want = [0, 5]; // [startTime, endTime] of desired buffer
    this.have = new Set(); // Set of already downloaded segment indices
    this.state = 4; // 3=fetching, 4=ready to fetch
    this.el = null; // Audio element
  }

  // Fetch decryption keys from API
  async fetchKey(segmentIndex) {
    console.log("Fetching key for segment:", segmentIndex);
    
    // Initial handshake with /api/v1/listen
    // Uses FormData with CSRF token and encoded buffer
    const formData = new FormData();
    formData.append("csrf", csrfToken);
    formData.append("buf", new Blob([bencode.encode(data)]));
    
    // Can use sendBeacon for background sending
    if ("sendBeacon" in navigator) {
      navigator.sendBeacon("/api/v1/listen", formData);
    } else {
      await fetch("/api/v1/listen", {
        method: "POST",
        body: formData
      });
    }
    
    // Segment key requests to /api/v1/audio/listen
    // Request is encrypted with ChaCha20
    const headers = {
      "Content-Type": "application/vnd.hotaudio.crypt+json"
    };
    
    // Generate 12-byte nonce from SHA hash
    const nonce = SHA256(data).slice(0, 12);
    const encryptedRequest = ChaCha20Poly1305(key, nonce).encrypt(
      new TextEncoder().encode(requestData)
    );
    
    const response = await fetch("/api/v1/audio/listen?key=" + encodeURIComponent(keyParam), {
      method: "POST",
      headers: headers,
      body: encryptedRequest
    });
    
    // Response contains keys that are added to the key map
    // Keys are indexed by segment number
    if (response.ok) {
      const data = await response.json();
      this.addKeys(data.keys);
    }
  }
  
  // Add API keys to the internal key map
  addKeys(keys) {
    // Keys come as object: { segmentNumber: base64Key, ... }
    for (let [segmentNum, keyData] of Object.entries(keys)) {
      // Convert base64 key to Uint8Array and store
      this.keyMap.set(+segmentNum, base64ToUint8Array(keyData));
    }
  }

  // Begin loading audio
  beginLoad() {
    console.log("AudioSource", this.playMethod);
    
    // Sets up MediaSource Extensions
    // Fetches HAX file metadata
    // Begins segment downloading
  }
}

// ========================================
// CHACHA20-POLY1305 IMPLEMENTATION
// ========================================

function ChaCha20Poly1305(key, nonce) {
  // ChaCha20-Poly1305 AEAD implementation
  // Used for decrypting audio segments
  
  return {
    encrypt(plaintext, associatedData) {
      // Encrypt data with authentication
    },
    
    decrypt(ciphertext, associatedData) {
      // Decrypt and verify authentication tag
      // The last 16 bytes are the Poly1305 tag
      
      if (ciphertext.length < 16) {
        throw new Error("invalid ciphertext length: smaller than tagLength=16");
      }
      
      // Split ciphertext and tag
      const tagStart = ciphertext.length - 16;
      const encrypted = ciphertext.slice(0, tagStart);
      const tag = ciphertext.slice(tagStart);
      
      // Decrypt and verify
      // Returns decrypted data or throws if authentication fails
    }
  };
}

// ========================================
// CRYPTO IMPLEMENTATIONS IN MINIFIED CODE
// ========================================

/*
Key function mappings in nozzle.js:
- At = SHA256 implementation (At.create().update().digest())
- Ot = ChaCha20-Poly1305 AEAD cipher
- Et = Bencode encoder/decoder
- pt = HaxFileParser class
- Lr = Base64 to Uint8Array converter

The minified code uses these throughout:
- At.create().update(key).update(data).digest() - SHA256 hashing
- Ot(key, nonce).decrypt(ciphertext) - ChaCha20-Poly1305 decryption
- Et.encode(data) / Et.decode(data) - Bencode operations
*/

// ========================================
// NOTES ON DECRYPTION FLOW
// ========================================

/*
1. HAX File Structure:
   - Header: "HAX0" magic bytes
   - Metadata: Bencoded dictionary containing:
     - Audio metadata (duration, codec, etc.)
     - Segment information (byte ranges)
     - Base encryption keys
   - No actual audio data (streamed from CDN)

2. Key Derivation:
   - Hierarchical binary tree structure
   - Base keys stored in HAX metadata
   - Child keys derived using SHA-256(parent_key + direction_bit)
   - Each segment has a unique key

3. Segment Decryption:
   - Audio is split into ~1 second segments
   - Each segment encrypted with ChaCha20-Poly1305
   - 12-byte nonce (usually zeros)
   - 16-byte authentication tag appended

4. API Key Integration:
   - CRITICAL: Base keys alone cannot decrypt segments
   - Live API keys from /api/v1/listen are required
   - Keys are combined (XOR, HMAC, or concatenation)
   - Without API keys, all decryption attempts fail

5. Playback Flow:
   - Load HAX file and parse metadata
   - Set up MediaSource Extensions
   - Fetch API keys on demand
   - Download encrypted segments from CDN
   - Decrypt segments using combined keys
   - Feed decrypted audio to MediaSource
*/

// ========================================
// COMPLETE DECRYPTION WORKFLOW SUMMARY
// ========================================

/*
To decrypt HotAudio files, you need to:

1. Parse the HAX file:
   - Read HAX0 header
   - Extract bencoded metadata
   - Get segment information and base keys

2. Understand the key hierarchy:
   - Base keys are stored in HAX metadata
   - Each segment needs a unique derived key
   - Keys are derived using SHA256 in a binary tree structure
   - Formula: SHA256(parent_key || direction_bit)

3. CRITICAL - Get API keys:
   - Make authenticated request to /api/v1/listen
   - Get segment-specific keys from /api/v1/audio/listen
   - These keys MUST be combined with derived keys
   - Without API keys, decryption will fail with "unable to authenticate data"

4. Decrypt segments:
   - Download encrypted segment from CDN using byte ranges
   - Combine derived key with API key (method unknown - could be XOR, HMAC, or concat)
   - Use ChaCha20-Poly1305 with:
     - 32-byte combined key
     - 12-byte zero nonce
     - Last 16 bytes are authentication tag
   
5. Key findings from the code:
   - pt class handles HAX parsing and key derivation
   - At is SHA256 (At.create().update().digest())
   - Ot is ChaCha20-Poly1305 (Ot(key, nonce).decrypt())
   - Et is bencode encoder/decoder
   - addKeys() method stores API keys in internal map
   - decode() method performs actual decryption

The main challenge is understanding how API keys are combined with derived keys.
This combination step is the missing piece preventing offline decryption.
*/