import binascii
import hashlib
import json
import logging
import math
import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import bencodepy
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def uint32(data, offset):
    """Reads a 32-bit unsigned integer (little-endian) from the data."""
    return struct.unpack_from("<I", data, offset)[0]

@dataclass
class HotAudioHeader:
    file_length: int
    header_length: int 
    extra_length: int
    meta: dict
    segments: List[dict]  # List of dicts with 'off' and 'pts' keys
    base_key: bytes

class HotAudioDecryptor:
    def __init__(self, header_data: bytes, keys: Dict[str, str]):
        """Initialize decryptor with header data and decryption keys"""
        if not header_data.startswith(b"HAX0"):
            raise ValueError("Invalid HAX header magic")

        self.header = self._parse_header(header_data)
        self.keys = {int(k): binascii.unhexlify(v) for k, v in keys.items()}

    def _parse_header(self, data: bytes) -> HotAudioHeader:
        """Parse the HAX header format"""
        # Parse fixed header fields
        file_length = uint32(data, 4)
        header_length = uint32(data, 8)
        extra_length = uint32(data, 12)

        logger.debug(f"Header lengths: file={file_length}, header={header_length}, extra={extra_length}")

        try:
            # Decode the bencoded metadata section
            bencoded_data = data[16:header_length]
            logger.debug(f"Bencoded data (first 32 bytes): {bencoded_data[:32].hex()}")

            meta = bencodepy.decode(bencoded_data)
            logger.debug(f"Decoded metadata: {meta}")

            # Parse segments
            segments = []
            seg_data = meta[b"segments"]
            for i in range(0, len(seg_data), 8):
                offset = uint32(seg_data, i)
                pts = uint32(seg_data, i + 4)
                segments.append({"off": offset, "pts": pts})

            # Add final segment
            segments.append({
                "off": file_length,
                "pts": meta[b"durationMs"]
            })

            return HotAudioHeader(
                file_length=file_length,
                header_length=header_length,
                extra_length=extra_length,
                meta={k.decode() if isinstance(k, bytes) else k: v for k, v in meta.items()},
                segments=segments,
                base_key=meta[b"baseKey"]
            )
        except Exception as e:
            logger.error(f"Error parsing header: {e}")
            raise

    def _derive_key(self, index: int) -> bytes:
        """Derive the decryption key for a given index"""
        r = math.ceil(math.log2(index)) if index > 0 else 0
        derived_key = None
        found_i = 0

        # Find the first applicable key
        for i in range(r + 1):
            key_index = index >> (r - i)
            if key_index in self.keys:
                derived_key = self.keys[key_index]
                found_i = i
                break

        if derived_key is None:
            if 1 in self.keys:  # Try base key
                derived_key = self.keys[1]
                found_i = 0
            else:
                raise ValueError("No applicable key available")

        # Derive final key using remaining bits
        for i in range(found_i + 1, r + 1):
            shift_byte = bytes([index >> (r - i) & 0xFF])
            derived_key = hashlib.sha256(derived_key + shift_byte).digest()

        return derived_key

    def decrypt_segment(self, segment_num: int, data: bytes) -> bytes:
        """Decrypt a single segment"""
        if segment_num < 0:
            raise ValueError("Invalid segment number")

        # Calculate key index
        h = 1 + (1 << (math.ceil(math.log2(len(self.header.segments))) + 1))
        key = self._derive_key(h + segment_num)

        # Pad data if needed
        padding_length = (16 - len(data) % 16) % 16
        padded_data = data + bytes([padding_length] * padding_length)

        # Decrypt using AES-CBC with zero IV
        iv = bytes(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(padded_data) + decryptor.finalize()

        # Remove padding
        if padding_length > 0:
            decrypted = decrypted[:-padding_length]

        return decrypted
