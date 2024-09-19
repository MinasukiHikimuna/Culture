import re

def parse_resolution_width(resolution_string):
    pattern_exact = r"(?P<width>\d+)x(?P<height>\d+)"
    exact_match = re.search(pattern_exact, resolution_string)
    if exact_match:
        return int(exact_match.group("width"))

    trimmed_resolution_string = resolution_string.strip().replace(" ", "")

    pattern_within_other_text_resolution = r"^(?P<width>\d+)x(?P<height>\d+)$"
    match_within_other_text_resolution = re.match(pattern_within_other_text_resolution, trimmed_resolution_string)
    if match_within_other_text_resolution:
        return int(match_within_other_text_resolution.group("width"))

    return -1

def parse_resolution_height(resolution_string):
    pattern_exact = r"(?P<width>\d+)x(?P<height>\d+)"
    exact_match = re.search(pattern_exact, resolution_string)
    if exact_match:
        return int(exact_match.group("height"))

    trimmed_resolution_string = resolution_string.strip().replace(" ", "")

    pattern_within_other_text_resolution = r"(?P<width>\d+)x(?P<height>\d+)"
    match_within_other_text_resolution = re.search(pattern_within_other_text_resolution, trimmed_resolution_string)
    if match_within_other_text_resolution:
        return int(match_within_other_text_resolution.group("height"))

    if any(s in resolution_string.upper() for s in ["4K", "2160", "2160P", "UHD"]):
        return 2160

    if any(s in resolution_string.upper() for s in ["1080", "1080P", "FULL HD"]):
        return 1080

    pattern = r"(?P<height>\d+)p"
    match = re.search(pattern, resolution_string)
    if match:
        return int(match.group("height"))

    return -1
