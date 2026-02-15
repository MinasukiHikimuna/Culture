import pytest
from decrypt_hotaudio import HotAudioDecryptor
import json

@pytest.fixture
def sample_keys():
    with open("hm6aq9rrzwtt2drebe64hmjf00.json") as f:
        return json.load(f)["keys"]

@pytest.fixture
def sample_header():
    with open("hm6aq9rrzwtt2drebe64hmjf00.hax", "rb") as f:
        return f.read()  # Read enough for header

def test_header_parsing(sample_header):
    # Print the header magic and lengths
    print(f"Header magic: {sample_header[:4]}")
    print(f"File length: {int.from_bytes(sample_header[4:8], 'little')}")
    print(f"Header length: {int.from_bytes(sample_header[8:12], 'little')}")
    print(f"Extra length: {int.from_bytes(sample_header[12:16], 'little')}")
    print(f"Bencoded data (hex): {sample_header[16:50].hex()}")
    
    decryptor = HotAudioDecryptor(sample_header, {})
    header = decryptor.header
    
    # Test basic header fields
    assert header.header_length == 15268
    assert header.file_length == 27430737
    assert header.extra_length == 4871
    
    # Test metadata
    assert "segmentCount" in header.meta
    assert header.meta["segmentCount"] == 1880
    assert "durationMs" in header.meta
    assert header.meta["durationMs"] == 1919754
    assert header.base_key == b"\x8d\x0c\xab\xa7\x18\xff5\xa17\x0e[\x8cH\xd2O\x00"

def test_key_derivation(sample_header, sample_keys):
    decryptor = HotAudioDecryptor(sample_header, sample_keys)
    
    # Test deriving key for segment 0
    key = decryptor._derive_key(4096)
    assert len(key) == 32  # SHA-256 output length
    assert key == b"\xe7A\xd9\xb2u\x8a\xb8\x90z\xc4\xb8\x8dk\xd2\xd6\xf1\x1dn\xef\xe5\xfe\xd3\xcf\xe0\x1e\x1d\x97\x99~\x1fB\xc1"

# def test_segment_decryption(sample_header, sample_keys):
#     decryptor = HotAudioDecryptor(sample_header, sample_keys)
#     
#     # Read first segment data
#     with open('hm6aq9rrzwtt2drebe64hmjf00.hax', 'rb') as f:
#         f.seek(decryptor.header.header_length + decryptor.header.extra_length)
#         segment_data = f.read(decryptor.header.segments[1][0] - decryptor.header.segments[0][0])
#     
#     # Decrypt first segment
#     decrypted = decryptor.decrypt_segment(0, segment_data)
#     
#     # Basic validation of decrypted data
#     assert len(decrypted) > 0
#     # Check for AAC ADTS header magic bytes
#     assert decrypted.startswith(b'\xff\xf1') or decrypted.startswith(b'\xff\xf9')
# 