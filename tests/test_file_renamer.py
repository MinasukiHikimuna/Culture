import pytest
from libraries.file_renamer import (
    get_performers_value,
    get_studio_value,
    has_studio_code_tag,
)


class TestGetStudioValue:
    def test_with_parent(self):
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

    def test_without_parent(self):
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

    def test_none(self):
        result = get_studio_value(None)
        assert result == "Unknown Studio"

    def test_empty_dict(self):
        with pytest.raises(KeyError):
            get_studio_value({})


class TestHasStudioCodeTag:
    def test_true(self):
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

    def test_false(self):
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

    def test_different_tag(self):
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

    def test_none_studio(self):
        # Act
        result = has_studio_code_tag({"id": 7940}, None)

        # Assert
        assert result == False

    def test_none_tag_param(self):
        # Arrange
        studio = {
            "id": 41,
            "name": "Babes",
            "tags": [{"id": 7940, "name": "Filenames: Use Studio Code"}],
        }

        # Act & Assert
        with pytest.raises(ValueError):
            has_studio_code_tag(None, studio)


class TestGetPerformersValue:
    def test_none(self):
        with pytest.raises(ValueError):
            get_performers_value(None)

    def test_with_performers(self):
        # Arrange
        performers = [
            {
                "stashapp_performers_id": 139,
                "stashapp_performers_name": "Alexis Crystal",
                "stashapp_performers_disambiguation": "",
                "stashapp_performers_alias_list": [],
                "stashapp_performers_gender": "FEMALE",
                "stashapp_performers_stash_ids": [],
                "stashapp_performers_custom_fields": [],
            },
            {
                "stashapp_performers_id": 230,
                "stashapp_performers_name": "Nancy Ace",
                "stashapp_performers_disambiguation": "",
                "stashapp_performers_alias_list": [],
                "stashapp_performers_gender": "FEMALE",
                "stashapp_performers_stash_ids": [],
                "stashapp_performers_custom_fields": [],
            },
        ]

        # Act
        result = get_performers_value(performers)

        # Assert
        assert result == "Alexis Crystal, Nancy Ace"


if __name__ == "__main__":
    pytest.main()
