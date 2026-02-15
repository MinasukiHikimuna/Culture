import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional

import requests


@dataclass
class Subcat:
    id: int
    name: str

@dataclass
class Category:
    id: int
    name: str
    subcats: list[Subcat]

class Categories:
    def __init__(self):
        self.categories: list[Category] = []

    def fetch_categories(self, api_url: str, api_key: str) -> None:
        """Fetch categories from the API endpoint"""
        url = f"{api_url}?t=caps&apikey={api_key}"
        response = requests.get(url)
        response.raise_for_status()

        # Parse XML response
        root = ET.fromstring(response.text)
        categories_elem = root.find("categories")

        if categories_elem is None:
            raise ValueError("No categories found in API response")

        self.categories = []
        for cat in categories_elem.findall("category"):
            category = Category(
                id=int(cat.get("id", 0)),
                name=cat.get("name", ""),
                subcats=[]
            )

            for subcat in cat.findall("subcat"):
                category.subcats.append(
                    Subcat(
                        id=int(subcat.get("id", 0)),
                        name=subcat.get("name", "")
                    )
                )

            self.categories.append(category)

    def get_category_name(self, cat_id: int) -> Optional[str]:
        """Get category name by ID"""
        for cat in self.categories:
            if cat.id == cat_id:
                return cat.name
        return None

    def get_subcat_name(self, cat_id: int, subcat_id: int) -> Optional[str]:
        """Get subcategory name by category ID and subcategory ID"""
        for cat in self.categories:
            if cat.id == cat_id:
                for subcat in cat.subcats:
                    if subcat.id == subcat_id:
                        return subcat.name
        return None

    def print_all_categories(self):
        """Debug method to print all loaded categories"""
        for cat in self.categories:
            print(f"Category {cat.id}: {cat.name}")
            for subcat in cat.subcats:
                print(f"  Subcat {subcat.id}: {subcat.name}")