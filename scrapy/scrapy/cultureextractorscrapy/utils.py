import re
import logging

def parse_resolution_width(resolution_string):
    # Try to find the resolution in the form of width x height
    match = re.search(r'(\d{3,4})\s*[xX]', resolution_string)
    if match:
        return int(match.group(1))

    # Handle common labels for width-height formats
    common_resolutions = {
        '1080p': 1920,
        '1080i': 1920,
        '720p': 1280,
        '720i': 1280,
        '2160p': 3840,
        '4K': 3840,  # 4K typically means 3840x2160
        'FULL HD': 1920,
    }
    
    # Check for keywords like 1080p, 720p, 1080i, 720i, etc.
    for key, value in common_resolutions.items():
        if key.upper() in resolution_string.upper():
            return value

    return -1

def parse_resolution_height(resolution_string):
    # First, try to find the resolution in the form of width x height
    match = re.search(r'[xX]\s*(\d{3,4})', resolution_string)
    if match:
        return int(match.group(1))

    # Handle common labels for height-only formats (including interlaced formats)
    common_heights = {
        '1080p': 1080,
        '1080i': 1080,
        '720p': 720,
        '720i': 720,
        '2160p': 2160,
        '4K': 2160,  # 4K typically means 3840x2160
        'FULL HD': 1080,
    }
    
    # Check for keywords like 1080p, 720p, 1080i, 720i, etc.
    for key, value in common_heights.items():
        if key.upper() in resolution_string.upper():
            return value

    # Check for other interlaced formats
    match = re.search(r'(\d{3,4})I', resolution_string, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return -1

def get_log_filename(spider_name):
    import datetime
    import os
    from scrapy.utils.project import get_project_settings
    
    settings = get_project_settings()
    log_dir = settings.get('LOG_DIR', 'logs')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f"{spider_name}_{timestamp}.log")
    
    # Set up logging to both file and console
    logger = logging.getLogger()
    logger.setLevel(settings.get('LOG_LEVEL', 'INFO'))
    
    # File handler
    fh = logging.FileHandler(log_file)
    fh.setFormatter(logging.Formatter(
        settings.get('LOG_FORMAT', '%(asctime)s [%(name)s] %(levelname)s: %(message)s'),
        settings.get('LOG_DATEFORMAT', '%Y-%m-%d %H:%M:%S')
    ))
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        settings.get('LOG_FORMAT', '%(asctime)s [%(name)s] %(levelname)s: %(message)s'),
        settings.get('LOG_DATEFORMAT', '%Y-%m-%d %H:%M:%S')
    ))
    logger.addHandler(ch)
    
    return log_file
