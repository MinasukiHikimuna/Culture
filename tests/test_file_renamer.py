import json
from pathlib import Path
import pytest
from libraries.file_renamer import get_studio_value


def test_get_studio_value_with_parent():
    # Arrange
    studio = {
        "id": 132,
        "name": "VIPissy",
        "url": "https://www.vipissy.com/",
        "tags": [],
        "parent_studio": {
            "id": 367,
            "name": "VIPissy Cash",
            "url": "https://nats.vipissycash.com/",
            "tags": [],
        },
    }

    # Act
    result = get_studio_value(studio)

    # Assert
    assert result == "VIPissy Cash꞉ VIPissy"


def test_get_studio_value_without_parent():
    # Arrange
    studio = {
        "id": 82,
        "name": "Xev Unleashed",
        "url": "https://xevunleashed.com/",
        "tags": [],
        "parent_studio": None,
    }

    # Act
    result = get_studio_value(studio)

    # Assert
    assert result == "Xev Unleashed"


def test_get_studio_value_none():
    result = get_studio_value(None)
    assert result == "Unknown Studio"


def test_get_studio_value_empty_dict():
    with pytest.raises(KeyError):
        get_studio_value({})
