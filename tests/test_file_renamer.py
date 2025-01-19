import json
from pathlib import Path
import pytest
from libraries.file_renamer import get_studio_value

@pytest.fixture
def sample_data():
    sample_file = Path(__file__).parent / "data" / "file_renamer.sample01.json"
    with open(sample_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_get_studio_value_with_parent(sample_data):
    # Get studio from sample data
    studio = sample_data[0]["stashapp_studio"]
    
    # Test
    result = get_studio_value(studio)
    
    # Verify
    assert result == "VIPissy Cash꞉ VIPissy"

def test_get_studio_value_without_parent():
    # Studio without parent
    studio = {
        "name": "Solo Studio",
        "id": 123,
        "url": "https://example.com"
    }
    
    result = get_studio_value(studio)
    assert result == "Solo Studio"

def test_get_studio_value_none():
    result = get_studio_value(None)
    assert result == "Unknown Studio"

def test_get_studio_value_empty_dict():
    with pytest.raises(KeyError):
        get_studio_value({})
