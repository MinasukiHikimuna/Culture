import logging
import os
import re
import shutil
import sys


class WindowsSafeFormatter(logging.Formatter):
    def format(self, record):
        # Convert Unicode colon (꞉) to standard colon (:) in the message
        if hasattr(record, "msg"):
            if isinstance(record.msg, str):
                record.msg = record.msg.replace("꞉", ":")

            # Handle string formatting arguments
            if hasattr(record, "args"):
                if isinstance(record.args, dict):
                    # Handle dictionary style formatting
                    args = {}
                    for key, value in record.args.items():
                        if isinstance(value, str):
                            args[key] = value.replace("꞉", ":")
                        else:
                            args[key] = value
                    record.args = args
                elif record.args:
                    # Handle sequence style formatting
                    args = list(record.args)
                    for i, arg in enumerate(args):
                        if isinstance(arg, str):
                            args[i] = arg.replace("꞉", ":")
                    record.args = tuple(args)

        # Format the message
        formatted = super().format(record)

        # Ensure the output is compatible with Windows console
        if sys.platform == "win32":
            try:
                # Test if the string can be encoded in cp1252
                formatted.encode("cp1252")
            except UnicodeEncodeError:
                # If it can't, replace problematic characters with their closest ASCII equivalent
                formatted = formatted.encode("ascii", "replace").decode("ascii")

        return formatted


def parse_resolution_width(resolution_string):
    # Try to find the resolution in the form of width x height
    match = re.search(r"(\d{3,4})\s*[xX]", resolution_string)
    if match:
        return int(match.group(1))

    # Handle common labels for width-height formats
    common_resolutions = {
        "1080p": 1920,
        "1080i": 1920,
        "720p": 1280,
        "720i": 1280,
        "2160p": 3840,
        "4K": 3840,  # 4K typically means 3840x2160
        "FULL HD": 1920,
    }

    # Check for keywords like 1080p, 720p, 1080i, 720i, etc.
    for key, value in common_resolutions.items():
        if key.upper() in resolution_string.upper():
            return value

    return -1


def parse_resolution_height(resolution_string):
    # First, try to find the resolution in the form of width x height
    match = re.search(r"[xX]\s*(\d{3,4})", resolution_string)
    if match:
        return int(match.group(1))

    # Handle common labels for height-only formats (including interlaced formats)
    common_heights = {
        "1080p": 1080,
        "1080i": 1080,
        "720p": 720,
        "720i": 720,
        "2160p": 2160,
        "4K": 2160,  # 4K typically means 3840x2160
        "FULL HD": 1080,
    }

    # Check for keywords like 1080p, 720p, 1080i, 720i, etc.
    for key, value in common_heights.items():
        if key.upper() in resolution_string.upper():
            return value

    # Check for other interlaced formats
    match = re.search(r"(\d{3,4})I", resolution_string, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return -1


def get_log_filename(spider_name):
    import datetime
    import os

    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()
    log_dir = settings.get("LOG_DIR", "logs")

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{spider_name}_{timestamp}.log")

    # Set up logging to both file and console
    logger = logging.getLogger()
    logger.setLevel(settings.get("LOG_LEVEL", "INFO"))

    # Create the custom formatter
    formatter = WindowsSafeFormatter(
        fmt=settings.get(
            "LOG_FORMAT", "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ),
        datefmt=settings.get("LOG_DATEFORMAT", "%Y-%m-%d %H:%M:%S"),
    )

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return log_file


def check_available_disk_space(target_path, min_free_gb=50):
    """
    Check if there's at least min_free_gb of free space available on the target drive.

    Args:
        target_path (str): Path to check disk space for
        min_free_gb (int): Minimum required free space in gigabytes (default: 50GB)

    Returns:
        tuple: (bool, float) - (has_enough_space, available_gb)
    """
    try:
        # Ensure the directory exists to get accurate disk space
        os.makedirs(target_path, exist_ok=True)

        # Get disk usage statistics
        total, used, free = shutil.disk_usage(target_path)

        # Convert bytes to gigabytes
        free_gb = free / (1024 ** 3)

        return free_gb >= min_free_gb, free_gb

    except Exception as e:
        logging.error(f"Error checking disk space for {target_path}: {e}")
        # Return False to be safe if we can't check disk space
        return False, 0.0
