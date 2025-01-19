from typing import Dict, Optional

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
    
    studio_name = studio["name"]
    parent_studio = studio.get("parent_studio")

    if parent_studio:
        return f"{parent_studio['name']}꞉ {studio_name}"
    
    return studio_name
