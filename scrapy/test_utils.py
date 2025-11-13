import unittest

from cultureextractorscrapy.utils import parse_resolution_height, parse_resolution_width


class TestParseResolutionWidth(unittest.TestCase):

    def test_parse_resolution_width_with_full_string(self):
        self.assertEqual(parse_resolution_width("Download MP4 HD 1920X1080 version"), 1920)

    def test_parse_resolution_width_standard_format(self):
        self.assertEqual(parse_resolution_width("1920x1080"), 1920)

    def test_parse_resolution_width_with_spaces(self):
        self.assertEqual(parse_resolution_width(" 1920 x 1080 "), 1920)

    def test_parse_resolution_width_with_prefix(self):
        self.assertEqual(parse_resolution_width("Resolution: 1920x1080"), 1920)

    def test_parse_resolution_width_incomplete_format(self):
        self.assertEqual(parse_resolution_width("1920x"), 1920)

    def test_parse_resolution_width_height_only(self):
        self.assertEqual(parse_resolution_width("x1080"), -1)

    def test_parse_resolution_width_empty_string(self):
        self.assertEqual(parse_resolution_width(""), -1)

    def test_parse_resolution_width_single_number(self):
        self.assertEqual(parse_resolution_width("1920"), -1)

    def test_parse_resolution_width_1080p(self):
        self.assertEqual(parse_resolution_width("1080p"), 1920)

    def test_parse_resolution_width_4k(self):
        self.assertEqual(parse_resolution_width("4K"), 3840)

    def test_parse_resolution_width_2160p(self):
        self.assertEqual(parse_resolution_width("2160p"), 3840)

    def test_parse_resolution_width_full_hd(self):
        self.assertEqual(parse_resolution_width("FULL HD"), 1920)

    def test_parse_resolution_width_720p(self):
        self.assertEqual(parse_resolution_width("720p"), 1280)

class TestParseResolutionHeight(unittest.TestCase):

    def test_parse_resolution_height_with_full_string(self):
        self.assertEqual(parse_resolution_height("Download MP4 HD 1920X1080 version"), 1080)

    def test_parse_resolution_height_standard_format(self):
        self.assertEqual(parse_resolution_height("1920x1080"), 1080)

    def test_parse_resolution_height_with_spaces(self):
        self.assertEqual(parse_resolution_height(" 1920 x 1080 "), 1080)

    def test_parse_resolution_height_with_prefix(self):
        self.assertEqual(parse_resolution_height("Resolution: 1920x1080"), 1080)

    def test_parse_resolution_height_incomplete_format(self):
        self.assertEqual(parse_resolution_height("1920x"), -1)

    def test_parse_resolution_height_height_only(self):
        self.assertEqual(parse_resolution_height("x1080"), 1080)

    def test_parse_resolution_height_empty_string(self):
        self.assertEqual(parse_resolution_height(""), -1)

    def test_parse_resolution_height_1080p(self):
        self.assertEqual(parse_resolution_height("1080p"), 1080)

    def test_parse_resolution_height_4k(self):
        self.assertEqual(parse_resolution_height("4K"), 2160)

    def test_parse_resolution_height_2160p(self):
        self.assertEqual(parse_resolution_height("2160p"), 2160)

    def test_parse_resolution_height_full_hd(self):
        self.assertEqual(parse_resolution_height("FULL HD"), 1080)

    def test_parse_resolution_height_720p(self):
        self.assertEqual(parse_resolution_height("720p"), 720)

if __name__ == '__main__':
    unittest.main()
