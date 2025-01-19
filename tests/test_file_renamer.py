import json
from pathlib import Path
import pytest
from libraries.file_renamer import FileRenamer

@pytest.fixture
def sample_data():
    sample_file = Path(__file__).parent / "data" / "file_renamer.sample01.json"
    with open(sample_file, 'r', encoding='utf-8') as f:
        return json.load(f)

@pytest.fixture
def file_renamer():
    return FileRenamer()

def test_get_studio_value_with_parent(file_renamer, sample_data):
    # Get studio from sample data
    studio = sample_data[0]["stashapp_studio"]
    
    # Test
    result = file_renamer.get_studio_value(studio)
    
    # Verify
    assert result == "VIPissy Cash꞉ VIPissy"

def test_get_studio_value_without_parent(file_renamer):
    # Studio without parent
    studio = {
        "name": "Solo Studio",
        "id": 123,
        "url": "https://example.com"
    }
    
    result = file_renamer.get_studio_value(studio)
    assert result == "Solo Studio"

def test_get_studio_value_none(file_renamer):
    result = file_renamer.get_studio_value(None)
    assert result == "Unknown Studio"

def test_get_studio_value_empty_dict(file_renamer):
    with pytest.raises(KeyError):
        file_renamer.get_studio_value({})
