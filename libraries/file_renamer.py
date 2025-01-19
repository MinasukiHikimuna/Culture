from typing import Dict, List, Optional

def get_studio_value(studio: Optional[Dict]) -> str:
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

def has_studio_code_tag(use_studio_code_tag: Dict, studio: Dict) -> bool:
    if use_studio_code_tag is None:
        raise ValueError("use_studio_code_tag is required")
    
    if studio is None or studio.get("tags") is None or len(studio.get("tags")) == 0:
        return False

    tag_ids = [tag["id"] for tag in studio.get("tags")]
    return use_studio_code_tag["id"] in tag_ids

def get_performers_value(performers: List[Dict]) -> str:
    """
    Format performers list with gender-based sorting.
    
    Args:
        performers: List of dictionaries containing performer information
                  Example: [{"stashapp_performers_name": "Name", "stashapp_performers_gender": "FEMALE"}]
    
    Returns:
        Comma-separated string of performer names, sorted by gender priority and name
        Example: "Female Name, Male Name"
        Raises ValueError if performers is None
    """
    if performers is None:
        raise ValueError("performers is required")
    
    if len(performers) == 0:
        return "Unknown performers"

    # Define gender priority
    gender_priority = {
        'TRANSGENDER_FEMALE': 1,
        'FEMALE': 2,
        'MALE': 3
    }

    # Sort performers by gender priority and name
    sorted_performers = sorted(
        performers,
        key=lambda x: (
            gender_priority.get(x["stashapp_performers_gender"], 4),
            x["stashapp_performers_name"]
        )
    )

    return ", ".join(p["stashapp_performers_name"] for p in sorted_performers)
