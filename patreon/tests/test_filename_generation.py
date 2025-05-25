#!/usr/bin/env python3
"""
Pytest tests for the filename generation function.

Tests the generate_media_filename function to ensure it properly handles
various edge cases and produces the expected filename format:
<account> - <date> - <id> - <title> - <optional index for posts with multiple files>
"""

import pytest
import sys
from pathlib import Path

# Add the scripts directory to path so we can import scraper
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from scraper import generate_media_filename


class TestFilenameGeneration:
    """Test class for filename generation functionality."""

    def test_single_image_no_index(self):
        """Test single image filename generation (no index number)."""
        result = generate_media_filename(
            creator_name="simple_creator",
            post_date="2023-11-15",
            post_id="11111",
            post_title="Single Image Post",
            image_number=1,
            total_images=1,
            file_extension="webp",
        )
        expected = "simple_creator - 2023-11-15 - 11111 - Single_Image_Post.webp"
        assert result == expected

    def test_multiple_images_with_index(self):
        """Test multiple image filename generation with index."""
        result = generate_media_filename(
            creator_name="test_creator",
            post_date="2023-12-01",
            post_id="12345",
            post_title="My Amazing Post Title!",
            image_number=1,
            total_images=3,
            file_extension="jpg",
        )
        expected = "test_creator - 2023-12-01 - 12345 - My_Amazing_Post_Title - 01.jpg"
        assert result == expected

    def test_special_characters_removal(self):
        """Test that special characters are properly removed from titles."""
        result = generate_media_filename(
            creator_name="creator-name",
            post_date="2023-12-01",
            post_id="67890",
            post_title="Post with @#$%^&*() special chars",
            image_number=2,
            total_images=2,
            file_extension="png",
        )
        expected = (
            "creator-name - 2023-12-01 - 67890 - Post_with_special_chars - 02.png"
        )
        assert result == expected

    def test_empty_title_fallback(self):
        """Test fallback to 'untitled' when title is empty."""
        result = generate_media_filename(
            creator_name="creator",
            post_date="2023-10-01",
            post_id="99999",
            post_title="",
            image_number=1,
            total_images=1,
            file_extension="gif",
        )
        expected = "creator - 2023-10-01 - 99999 - untitled.gif"
        assert result == expected

    def test_long_title_truncation(self):
        """Test that very long titles are properly truncated."""
        long_title = "This is a very long post title that should be truncated because it exceeds the maximum length limit"
        result = generate_media_filename(
            creator_name="creator",
            post_date="2023-09-15",
            post_id="55555",
            post_title=long_title,
            image_number=3,
            total_images=5,
            file_extension="jpeg",
        )
        expected = "creator - 2023-09-15 - 55555 - This_is_a_very_long_post_title_that_should_be_trun - 03.jpeg"
        assert result == expected

    def test_spaces_to_underscores(self):
        """Test that spaces in titles are converted to underscores."""
        result = generate_media_filename(
            creator_name="creator_with_underscores",
            post_date="2023-08-20",
            post_id="77777",
            post_title="Post Title With Multiple   Spaces",
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        expected = "creator_with_underscores - 2023-08-20 - 77777 - Post_Title_With_Multiple_Spaces.jpg"
        assert result == expected

    @pytest.mark.parametrize("extension", ["jpg", "png", "gif", "webp", "jpeg"])
    def test_various_file_extensions(self, extension):
        """Test that various file extensions are handled correctly."""
        result = generate_media_filename(
            creator_name="test",
            post_date="2023-01-01",
            post_id="123",
            post_title="Extension Test",
            image_number=1,
            total_images=1,
            file_extension=extension,
        )
        expected = f"test - 2023-01-01 - 123 - Extension_Test.{extension}"
        assert result == expected

    def test_numbers_in_title(self):
        """Test that numbers in titles are preserved."""
        result = generate_media_filename(
            creator_name="creator123",
            post_date="2023-01-01",
            post_id="456",
            post_title="Post 123 with numbers 456",
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        expected = "creator123 - 2023-01-01 - 456 - Post_123_with_numbers_456.jpg"
        assert result == expected

    def test_very_short_inputs(self):
        """Test with very short input values."""
        result = generate_media_filename(
            creator_name="c",
            post_date="2023-01-01",
            post_id="1",
            post_title="a",
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        expected = "c - 2023-01-01 - 1 - a.jpg"
        assert result == expected

    @pytest.mark.parametrize(
        "image_number,total_images,expected_suffix",
        [
            (1, 1, ".jpg"),  # Single image, no index
            (1, 2, " - 01.jpg"),  # First of multiple
            (2, 2, " - 02.jpg"),  # Second of multiple
            (10, 15, " - 10.jpg"),  # Double digit index
        ],
    )
    def test_index_numbering(self, image_number, total_images, expected_suffix):
        """Test that index numbering works correctly for different scenarios."""
        result = generate_media_filename(
            creator_name="test",
            post_date="2023-01-01",
            post_id="123",
            post_title="Test Post",
            image_number=image_number,
            total_images=total_images,
            file_extension="jpg",
        )
        expected = f"test - 2023-01-01 - 123 - Test_Post{expected_suffix}"
        assert result == expected

    def test_none_title_handling(self):
        """Test handling of None title (should not happen in practice but good to test)."""
        result = generate_media_filename(
            creator_name="creator",
            post_date="2023-01-01",
            post_id="123",
            post_title=None,
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        expected = "creator - 2023-01-01 - 123 - untitled.jpg"
        assert result == expected


class TestFilenameGenerationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_creator_name_cleaning(self):
        """Test that creator names with special characters are cleaned."""
        result = generate_media_filename(
            creator_name="creator@#$%name",
            post_date="2023-01-01",
            post_id="123",
            post_title="Test",
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        expected = "creator____name - 2023-01-01 - 123 - Test.jpg"
        assert result == expected

    def test_maximum_title_length(self):
        """Test that title is truncated at exactly 50 characters."""
        # Create a title that's exactly 50 characters
        title_50_chars = "a" * 50
        result = generate_media_filename(
            creator_name="test",
            post_date="2023-01-01",
            post_id="123",
            post_title=title_50_chars,
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        expected = f"test - 2023-01-01 - 123 - {title_50_chars}.jpg"
        assert result == expected

        # Test title longer than 50 characters
        title_60_chars = "a" * 60
        result_long = generate_media_filename(
            creator_name="test",
            post_date="2023-01-01",
            post_id="123",
            post_title=title_60_chars,
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        expected_long = f"test - 2023-01-01 - 123 - {title_60_chars[:50]}.jpg"
        assert result_long == expected_long

    def test_whitespace_handling(self):
        """Test various whitespace scenarios."""
        test_cases = [
            ("  leading spaces", "leading_spaces"),
            ("trailing spaces  ", "trailing_spaces"),
            ("  both  ", "both"),
            ("multiple    spaces   between", "multiple_spaces_between"),
            ("\t\n\r mixed whitespace \t\n", "mixed_whitespace"),
        ]

        for input_title, expected_clean in test_cases:
            result = generate_media_filename(
                creator_name="test",
                post_date="2023-01-01",
                post_id="123",
                post_title=input_title,
                image_number=1,
                total_images=1,
                file_extension="jpg",
            )
            expected = f"test - 2023-01-01 - 123 - {expected_clean}.jpg"
            assert result == expected, f"Failed for input: '{input_title}'"


# Integration test to verify the function works with realistic data
class TestFilenameGenerationIntegration:
    """Integration tests with realistic Patreon data scenarios."""

    def test_realistic_patreon_post(self):
        """Test with realistic Patreon post data."""
        result = generate_media_filename(
            creator_name="artist_name",
            post_date="2023-12-15",
            post_id="98765432",
            post_title="December Art Pack - Fantasy Characters & Landscapes",
            image_number=3,
            total_images=8,
            file_extension="png",
        )
        expected = "artist_name - 2023-12-15 - 98765432 - December_Art_Pack_Fantasy_Characters_Landscapes - 03.png"
        assert result == expected

    def test_unicode_characters(self):
        """Test handling of unicode characters in titles."""
        result = generate_media_filename(
            creator_name="artist",
            post_date="2023-01-01",
            post_id="123",
            post_title="Art with émojis 🎨 and ñiño characters",
            image_number=1,
            total_images=1,
            file_extension="jpg",
        )
        # Unicode characters are preserved in the current implementation
        expected = "artist - 2023-01-01 - 123 - Art_with_émojis_and_ñiño_characters.jpg"
        assert result == expected
