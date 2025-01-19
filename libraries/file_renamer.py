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
        'TRANSGENDER_FEMALE': 1,
        'FEMALE': 2,
        'NON_BINARY': 3,
        'TRANSGENDER_MALE': 4,
        'MALE': 5
    }

    # Sort performers by gender priority, favorite status (True comes before False), and name
    sorted_performers = sorted(
        performers,
        key=lambda x: (
            gender_priority.get(x["stashapp_performers_gender"], 4),
            not x.get("stashapp_performers_favorite", False),
            x["stashapp_performers_name"]
        )
    )

    return ", ".join(p["stashapp_performers_name"] for p in sorted_performers)
