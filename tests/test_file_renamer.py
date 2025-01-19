import pytest
from libraries.file_renamer import get_studio_value, has_studio_code_tag


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


def test_has_studio_code_tag_true():
    # Arrange
    studio = {
        "id": 41,
        "name": "Babes",
        "url": "https://www.babes.com/",
        "tags": [{"id": 7940, "name": "Filenames: Use Studio Code"}],
        "parent_studio": {
            "id": 425,
            "name": "Babes (Network)",
            "url": "https://www.babesnetwork.com/",
            "tags": [{"id": 7940, "name": "Filenames: Use Studio Code"}],
        },
    }

    # Act
    result = has_studio_code_tag({"id": 7940}, studio)

    # Assert
    assert result == True


def test_has_studio_code_tag_false():
    # Arrange
    studio = {
        "id": 82,
        "name": "Xev Unleashed",
        "url": "https://xevunleashed.com/",
        "tags": [],
        "parent_studio": None,
    }

    # Act
    result = has_studio_code_tag({"id": 7940}, studio)

    # Assert
    assert result == False


def test_has_studio_code_tag_different_tag():
    # Arrange
    studio = {
        "id": 6,
        "name": "X-Art",
        "url": "https://www.x-art.com/",
        "tags": [{"id": 7627, "name": "Completionist"}],
        "parent_studio": {"id": 900, "name": "Malibu Media", "url": "", "tags": []},
    }

    # Act
    result = has_studio_code_tag({"id": 7940}, studio)

    # Assert
    assert result == False


def test_has_studio_code_tag_none_studio():
    # Act
    result = has_studio_code_tag({"id": 7940}, None)

    # Assert
    assert result == False


def test_has_studio_code_tag_none_tag_param():
    # Arrange
    studio = {
        "id": 41,
        "name": "Babes",
        "tags": [{"id": 7940, "name": "Filenames: Use Studio Code"}],
    }

    # Act & Assert
    with pytest.raises(ValueError):
        has_studio_code_tag(None, studio)


if __name__ == "__main__":
    pytest.main()
