import polars as pl
import requests
from dotenv import load_dotenv
import os
import urllib.parse
from .Categories import Categories

load_dotenv()

class NZBSearch:
    def __init__(self):
        self.drunkenslug_api_key = os.getenv("DRUNKEN_SLUG_API_KEY")
        self.ninjacentral_api_key = os.getenv("NINJA_CENTRAL_API_KEY")
        
        self.api_urls = {
            "drunkenslug": "https://drunkenslug.com/api",
            "ninja": "https://ninjacentral.co.za/api"
        }
        
        # Initialize categories for each API
        self.categories = {}
        for api_name, api_url in self.api_urls.items():
            self.categories[api_name] = Categories()
            api_key = self.drunkenslug_api_key if api_name == "drunkenslug" else self.ninjacentral_api_key
            self.categories[api_name].fetch_categories(api_url, api_key)

    def get_nzb_results(self, api_url: str, api_key: str, query: str) -> dict:
        """Get search results from a single API"""
        encoded_query = urllib.parse.quote(query)
        url = f"{api_url}?t=search&o=json&apikey={api_key}&q={encoded_query}"
        response = requests.get(url)
        response_json = response.json()
        
        # Handle ninja response format which wraps everything in a channel
        if api_url == "https://ninjacentral.co.za/api":
            response_json = response_json["channel"]
        
        # Handle various response formats
        if "error" in response_json:
            print(f"API returned error: {response_json['error']}")
            return {"item": []}
        if not isinstance(response_json, dict):
            print(f"Unexpected response format")
            return {"item": []}
        if "item" not in response_json:
            return {"item": []}
        # Handle case where item might be None instead of empty list
        if response_json["item"] is None:
            return {"item": []}
        # Ensure item is always a list
        if isinstance(response_json["item"], dict):
            response_json["item"] = [response_json["item"]]
        return response_json

    def get_category_info(self, api_name: str, cat_id: str) -> str:
        """Get human-readable category name"""
        try:
            # Category IDs come as simple numbers like "6020" or "6040"
            cat_id_int = int(cat_id)
            main_cat_id = (cat_id_int // 1000) * 1000  # e.g., 6020 -> 6000
            sub_cat_id = cat_id_int  # e.g., 6020
            
            cat = self.categories[api_name]
            category_name = cat.get_category_name(main_cat_id)
            subcat_name = cat.get_subcat_name(main_cat_id, sub_cat_id)
            
            if category_name and subcat_name:
                return f"{category_name}/{subcat_name}"
        except (ValueError, IndexError) as e:
            pass
        return str(cat_id)

    def search(self, query: str) -> pl.DataFrame:
        """Search across all configured APIs"""
        all_results = []
        
        for api_name, api_url in self.api_urls.items():
            try:
                api_key = self.drunkenslug_api_key if api_name == "drunkenslug" else self.ninjacentral_api_key
                
                try:
                    results = self.get_nzb_results(api_url, api_key, query)
                    
                    if not results["item"]:
                        continue
                        
                    # Convert results to DataFrame
                    nzb_results_df = pl.DataFrame(results["item"])
                    
                    # Extract size and category based on API format
                    if api_name == "drunkenslug":
                        # Drunken Slug has newznab:attr array with name/value pairs
                        nzb_results_df = nzb_results_df.with_columns([
                            pl.col("newznab:attr").map_elements(
                                lambda attrs: next((attr["_value"] for attr in attrs if attr["_name"] == "size"), "0"),
                                return_dtype=pl.Utf8
                            ).cast(pl.Int64).fill_null(0).alias("size"),
                            pl.col("newznab:attr").map_elements(
                                lambda attrs: next((attr["_value"] for attr in attrs if attr["_name"] == "category"), ""),
                                return_dtype=pl.Utf8
                            ).alias("category_id"),
                            pl.col("guid").struct.field("text").fill_null("").alias("item_url")
                        ])
                    else:
                        # Ninja Central has attr array with @attributes containing name/value
                        nzb_results_df = nzb_results_df.with_columns([
                            pl.col("attr").map_elements(
                                lambda attrs: next((attr["@attributes"]["value"] for attr in attrs if attr["@attributes"]["name"] == "size"), "0"),
                                return_dtype=pl.Utf8
                            ).cast(pl.Int64).fill_null(0).alias("size"),
                            pl.col("attr").map_elements(
                                lambda attrs: next((attr["@attributes"]["value"] for attr in attrs if attr["@attributes"]["name"] == "category"), ""),
                                return_dtype=pl.Utf8
                            ).alias("category_id"),
                            pl.col("guid").alias("item_url")
                        ])
                    
                    # Select only the columns we need
                    nzb_results_df = nzb_results_df.select([
                        pl.col("title"),
                        pl.col("size"),
                        pl.col("link"),
                        pl.col("category_id"),
                        pl.col("item_url"),
                        pl.lit(api_name).alias("api_name")
                    ])
                    
                    # Add human-readable category names
                    nzb_results_df = nzb_results_df.with_columns([
                        pl.col("category_id").map_elements(
                            lambda x: self.get_category_info(api_name, x),
                            return_dtype=pl.Utf8
                        ).alias("category_name")
                    ])
                    
                    all_results.append(nzb_results_df)
                    
                except Exception as e:
                    print(f"Error processing results from {api_name}: {str(e)}")
                    continue
                
            except Exception as e:
                print(f"Error fetching results from {api_name}: {str(e)}")
                continue
        
        if not all_results:
            return pl.DataFrame(schema={
                "title": pl.Utf8,
                "size": pl.Int64,
                "link": pl.Utf8,
                "category_id": pl.Utf8,
                "category_name": pl.Utf8,
                "item_url": pl.Utf8,
                "api_name": pl.Utf8
            })
            
        combined_df = pl.concat(all_results)
        return combined_df.sort(by="size", descending=True)

def main():
    searcher = NZBSearch()
    results = searcher.search("your search query")
    print(results)

if __name__ == "__main__":
    main() 