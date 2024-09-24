import re

def parse_resolution_width(resolution_string):
    # Try to find the resolution in the form of width x height
    match = re.search(r'(\d{3,4})\s*[xX]', resolution_string)
    if match:
        return int(match.group(1))

    # Handle common labels for width-height formats
    common_resolutions = {
        '1080p': 1920,
        '720p': 1280,
        '2160p': 3840,
        '4K': 3840,  # 4K typically means 3840x2160
        'FULL HD': 1920,
    }
    
    # Check for keywords like 1080p, 720p, etc.
    for key, value in common_resolutions.items():
        if key.upper() in resolution_string.upper():
            return value

    return -1

def parse_resolution_height(resolution_string):
    # First, try to find the resolution in the form of width x height
    match = re.search(r'[xX]\s*(\d{3,4})', resolution_string)
    if match:
        return int(match.group(1))

    # Handle common labels for height-only formats (like 1080p, 720p, 2160p)
    common_heights = {
        '1080p': 1080,
        '720p': 720,
        '2160p': 2160,
        '4K': 2160,  # 4K typically means 3840x2160
        'FULL HD': 1080,
    }
    
    # Check for keywords like 1080p, 720p, etc.
    for key, value in common_heights.items():
        if key.upper() in resolution_string.upper():
            return value

    return -1
