import os
from pathlib import Path
from typing import Optional


MAX_LENGTH = 255

def create_filename_with_directory(use_studio_code_tag: dict, row: dict, base_directory: str = None) -> dict[str, str]:
    """
    Create a filename and directory structure from a Polars DataFrame row dictionary.

    Args:
        use_studio_code_tag: Tag information for studio codes
        row: Dictionary containing scene information with stashapp_ prefixed keys
        base_directory: Base directory path (if None, derives from file's drive + \\Culture\\Videos)

    Returns:
        Dictionary with 'filename', 'directory', and 'full_path' keys
    """
    filename = create_filename(use_studio_code_tag, row)
    if not filename:
        return {"filename": None, "directory": None, "full_path": None}

    # Determine base directory if not provided
    if base_directory is None:
        current_file_path = row.get("stashapp_primary_file_path", "")
        if current_file_path:
            # Get the drive letter from the current file path
            drive = os.path.splitdrive(current_file_path)[0]
            base_directory = str(Path(drive) / os.sep / "Culture" / "Videos")
        else:
            # No file path available - cannot determine directory
            return {"filename": filename, "directory": None, "full_path": None}

    # Get studio information for directory structure
    studio = row.get("stashapp_studio")
    if not studio:
        # Fallback to current directory if no studio
        current_dir = str(Path(row.get("stashapp_primary_file_path", "")).parent)
        return {
            "filename": filename,
            "directory": current_dir,
            "full_path": str(Path(current_dir) / filename)
        }

    studio_name = studio.get("name", "Unknown Studio")
    parent_studio = studio.get("parent_studio")

    if parent_studio:
        # Network structure: Sites\[Network]\[Network]: [Site]
        network_name = parent_studio.get("name", "Unknown Network")
        site_name = studio_name

        # Clean network and site names for directory use
        clean_network = _clean_for_directory(network_name)
        clean_site = _clean_for_directory(site_name)

        # Create directory structure
        directory = str(Path(base_directory) / "Sites" / clean_network / f"{clean_network}꞉ {clean_site}")
    else:
        # No parent studio, use studio name directly
        clean_studio = _clean_for_directory(studio_name)
        directory = str(Path(base_directory) / "Sites" / clean_studio)

    return {
        "filename": filename,
        "directory": directory,
        "full_path": str(Path(directory) / filename)
    }

def create_filename(use_studio_code_tag: dict, row: dict) -> str:
    """
    Create a filename from a Polars DataFrame row dictionary.

    Args:
        row: Dictionary containing scene information with stashapp_ prefixed keys

    Returns:
        Formatted filename string
    """
    # Get the file suffix
    suffix = get_suffix(row.get("stashapp_primary_file_basename"))
    if not suffix:
        return None

    ce_uuid = row.get("stashapp_ce_id")
    if ce_uuid:
        ce_uuid_fmt = f" [{ce_uuid}]"
        ce_uuid_length = len(ce_uuid_fmt)
    else:
        ce_uuid_fmt = ""
        ce_uuid_length = 0

    suffix_length = len(suffix)
    max_length_wo_ce_uuid_suffix = MAX_LENGTH - ce_uuid_length - suffix_length

    # Get studio and format it
    studio = row.get("stashapp_studio")
    studio_name = get_studio_value(studio)

    # Get date
    date = row.get("stashapp_date")
    date_str = date if isinstance(date, str) else date.strftime("%Y-%m-%d") if date else "Unknown Date"

    # Get performers
    performers_str = get_performers_value(row.get("stashapp_performers"))

    # Get title
    title = row.get("stashapp_title", "Unknown Title")

    # Build base filename
    base_filename = f"{studio_name} – {date_str} – "

    # Add studio code if needed
    has_tag = has_studio_code_tag(use_studio_code_tag, studio)
    if has_tag and row.get("stashapp_code"):
        base_filename += f"{_clean_for_filename(row['stashapp_code'])} – "

    base_filename += _clean_for_filename(f"{title} – {performers_str}")

    # Check if the generated filename exceeds the maximum length
    if len(base_filename) + len(suffix) > max_length_wo_ce_uuid_suffix:
        # Truncate the base filename to fit within limits
        base_filename = base_filename[:max_length_wo_ce_uuid_suffix]

    return base_filename + ce_uuid_fmt + suffix

def _title_case_except_acronyms(text):
    words = text.split()
    title_cased_words = []
    for word in words:
        # Check if the word contains an apostrophe
        if "'" in word:
            # Split the word at the apostrophe and process each part
            parts = word.split("'")
            new_parts = [parts[0].title()]  # Always capitalize the part before the apostrophe
            if len(parts) > 1:
                # Never capitalize after the apostrophe
                new_parts.append(parts[1])
            # Rejoin the parts with an apostrophe
            title_cased_words.append("'".join(new_parts))
        # Check if word is all uppercase (acronym) - preserve it
        elif word.isupper() and len(word) > 1 or any(c.isupper() for c in word[1:]):
            title_cased_words.append(word)
        # Otherwise apply title case
        else:
            title_cased_words.append(word.title())

    return " ".join(title_cased_words)

def _clean_for_filename(input):
    input = _title_case_except_acronyms(input)
    return (
        input.replace(":", "꞉").replace("?", "？").replace("/", "∕").replace("\\", "＼")
        .replace("*", "＊").replace('"', "＂").replace("<", "＜").replace(">", "＞")
        .replace("|", "｜").replace("  ", " ")
    )

def _clean_for_directory(input):
    """Clean text for use in directory names, but keep most characters allowed by filesystems"""
    input = _title_case_except_acronyms(input)
    # Remove or replace characters that are not allowed in Windows directory names
    # Keep colon as ꞉ for display purposes, but it will be handled specially in paths
    return (
        input.replace(":", "꞉").replace("?", "？").replace("/", "∕").replace("\\", "＼")
        .replace("*", "＊").replace('"', "＂").replace("<", "＜").replace(">", "＞")
        .replace("|", "｜").replace("  ", " ")
    )

def get_suffix(primary_file_basename: str) -> str:
    if primary_file_basename is None:
        return None

    file_suffix = Path(primary_file_basename).suffix
    return file_suffix

def get_studio_value(studio: dict | None) -> str:
    """
    Format studio name with parent if available.

    Args:
        studio: Dictionary containing studio information with optional parent_studio
               Example: {"name": "VIPissy", "parent_studio": {"name": "VIPissy Cash"}}

    Returns:
        Formatted studio name. Examples:
        - "VIPissy Cash꞉ VIPissy" (with parent)
        - "VIPissy" (without parent)
        - "Unknown Studio" (if studio is None)
    """
    if studio is None:
        return "Unknown Studio"

    if studio.get("parent_studio") is None:
        return studio["name"]

    studio_name = studio["name"]
    parent_studio = studio.get("parent_studio")
    return f"{parent_studio['name']}꞉ {studio_name}"

def has_studio_code_tag(use_studio_code_tag: dict, studio: dict) -> bool:
    if use_studio_code_tag is None:
        raise ValueError("use_studio_code_tag is required")

    if studio is None:
        return False

    # Check studio's own tags
    studio_tags = studio.get("tags", [])
    if studio_tags and any(str(tag["id"]) == str(use_studio_code_tag["id"]) for tag in studio_tags):
        return True

    # Check parent studio's tags if they exist
    parent_studio = studio.get("parent_studio")
    if parent_studio and parent_studio.get("tags"):
        parent_tags = parent_studio.get("tags", [])
        if any(str(tag["id"]) == str(use_studio_code_tag["id"]) for tag in parent_tags):
            return True

    return False

def get_performers_value(performers: list[dict]) -> str:
    """
    Format performers list with gender-based sorting and favorite prioritization.

    Args:
        performers: List of dictionaries containing performer information
                  Example: [{"stashapp_performers_name": "Name", 
                           "stashapp_performers_gender": "FEMALE",
                           "stashapp_performers_favorite": True}]

    Returns:
        Comma-separated string of performer names, sorted by:
        1. Gender priority (TRANSGENDER_FEMALE, FEMALE, MALE)
        2. Favorite status within gender (favorites first)
        3. Name alphabetically
        Example: "Favorite Female, Other Female, Male"
        Raises ValueError if performers is None
    """
    if performers is None:
        raise ValueError("performers is required")

    if len(performers) == 0:
        return "Unknown performers"

    # Define gender priority
    gender_priority = {
        "TRANSGENDER_FEMALE": 1,
        "FEMALE": 2,
        "NON_BINARY": 3,
        "TRANSGENDER_MALE": 4,
        "MALE": 5
    }

    # Sort performers by gender priority, favorite status (True comes before False), and name
    # Use 999 for None gender values to put them last
    sorted_performers = sorted(
        performers,
        key=lambda x: (
            gender_priority.get(x["stashapp_performers_gender"], 999),
            not x.get("stashapp_performers_favorite", False),
            x["stashapp_performers_name"]
        )
    )

    return ", ".join(p["stashapp_performers_name"] for p in sorted_performers)

def process_scene_row(row: dict) -> dict:
    """
    Example function showing how to process an entire row from a Polars DataFrame.

    Args:
        row: Dictionary containing all fields from a Polars DataFrame row
             The row is automatically converted to a dictionary when using map_elements

    Returns:
        Dictionary with processed values

    Example usage from Polars:
        df.map_elements(process_scene_row)
    """
    return {
        "studio": get_studio_value(row.get("stashapp_studio")),
        "performers": get_performers_value(row.get("stashapp_performers")),
        "suffix": get_suffix(row.get("stashapp_primary_file_basename")),
        # Add any other fields you need to process
    }
