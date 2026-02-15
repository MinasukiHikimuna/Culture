import json
import os
import urllib.parse

import polars as pl
import requests
from dotenv import load_dotenv

from .Categories import Categories


load_dotenv()


class NZBSearch:
    def __init__(self):
        self.drunkenslug_api_key = os.getenv("DRUNKEN_SLUG_API_KEY")
        self.ninjacentral_api_key = os.getenv("NINJA_CENTRAL_API_KEY")

        self.api_urls = {
            "drunkenslug": "https://drunkenslug.com/api",
            "ninja": "https://ninjacentral.co.za/api",
        }

        # Initialize categories for each API
        self.categories = {}
        for api_name, api_url in self.api_urls.items():
            self.categories[api_name] = Categories()
            api_key = (
                self.drunkenslug_api_key
                if api_name == "drunkenslug"
                else self.ninjacentral_api_key
            )
            self.categories[api_name].fetch_categories(api_url, api_key)

    def get_nzb_results(self, api_url: str, api_key: str, query: str) -> dict:
        """Get search results from a single API"""
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"{api_url}?t=search&o=json&apikey={api_key}&q={encoded_query}"
            response = requests.get(url)

            # Check if response is valid
            if not response.ok:
                print(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
                return {"item": []}

            try:
                response_json = response.json()
            except json.JSONDecodeError as e:
                print(f"Invalid JSON response from {api_url}: {e!s}")
                print(
                    f"Response text: {response.text[:200]}..."
                )  # Print first 200 chars of response
                return {"item": []}

            # Handle ninja response format which wraps everything in a channel
            if api_url == "https://ninjacentral.co.za/api":
                if (
                    not isinstance(response_json, dict)
                    or "channel" not in response_json
                ):
                    print(
                        f"Unexpected ninja response format: {str(response_json)[:200]}..."
                    )
                    return {"item": []}
                response_json = response_json["channel"]

            # Handle various response formats
            if "error" in response_json:
                print(f"API returned error: {response_json['error']}")
                return {"item": []}
            if not isinstance(response_json, dict):
                print(f"Unexpected response format: {str(response_json)[:200]}...")
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

        except Exception as e:
            print(f"Error fetching results from {api_url}: {e!s}")
            return {"item": []}

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
        except (ValueError, IndexError):
            pass
        return str(cat_id)

    def search(self, query: str) -> pl.DataFrame:
        """Search across all configured APIs"""
        all_results = []

        for api_name, api_url in self.api_urls.items():
            try:
                api_key = (
                    self.drunkenslug_api_key
                    if api_name == "drunkenslug"
                    else self.ninjacentral_api_key
                )

                try:
                    results = self.get_nzb_results(api_url, api_key, query)

                    if not results["item"]:
                        continue

                    # Convert results to DataFrame
                    nzb_results_df = pl.DataFrame(results["item"])

                    # Extract size and category based on API format
                    if api_name == "drunkenslug":
                        # Drunken Slug has newznab:attr array with name/value pairs
                        nzb_results_df = nzb_results_df.with_columns(
                            [
                                pl.col("newznab:attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["_value"]
                                            for attr in attrs
                                            if attr["_name"] == "size"
                                        ),
                                        "0",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .cast(pl.Int64)
                                .fill_null(0)
                                .alias("size"),
                                pl.col("newznab:attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["_value"]
                                            for attr in attrs
                                            if attr["_name"] == "category"
                                        ),
                                        "",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .alias("category_id"),
                                pl.col("guid")
                                .struct.field("text")
                                .fill_null("")
                                .alias("item_url"),
                            ]
                        )
                    else:
                        # Ninja Central has attr array with @attributes containing name/value
                        nzb_results_df = nzb_results_df.with_columns(
                            [
                                pl.col("attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["@attributes"]["value"]
                                            for attr in attrs
                                            if attr["@attributes"]["name"] == "size"
                                        ),
                                        "0",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .cast(pl.Int64)
                                .fill_null(0)
                                .alias("size"),
                                pl.col("attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["@attributes"]["value"]
                                            for attr in attrs
                                            if attr["@attributes"]["name"] == "category"
                                        ),
                                        "",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .alias("category_id"),
                                pl.col("guid").alias("item_url"),
                            ]
                        )

                    # Select only the columns we need
                    nzb_results_df = nzb_results_df.select(
                        [
                            pl.col("title"),
                            pl.col("size"),
                            pl.col("link"),
                            pl.col("category_id"),
                            pl.col("item_url"),
                            pl.lit(api_name).alias("api_name"),
                        ]
                    )

                    # Add human-readable category names
                    nzb_results_df = nzb_results_df.with_columns(
                        [
                            pl.col("category_id")
                            .map_elements(
                                lambda x: self.get_category_info(api_name, x),
                                return_dtype=pl.Utf8,
                            )
                            .alias("category_name")
                        ]
                    )

                    all_results.append(nzb_results_df)

                except Exception as e:
                    print(f"Error processing results from {api_name}: {e!s}")
                    continue

            except Exception as e:
                print(f"Error fetching results from {api_name}: {e!s}")
                continue

        if not all_results:
            return pl.DataFrame(
                schema={
                    "title": pl.Utf8,
                    "size": pl.Int64,
                    "link": pl.Utf8,
                    "category_id": pl.Utf8,
                    "category_name": pl.Utf8,
                    "item_url": pl.Utf8,
                    "api_name": pl.Utf8,
                }
            )

        combined_df = pl.concat(all_results)
        return combined_df.sort(by="size", descending=True)

    def search_single(self, query: str) -> pl.DataFrame:
        """Search across all configured APIs for a single query"""
        # Create empty schema for consistent return type
        empty_schema = {
            "title": pl.Utf8,
            "size": pl.Int64,
            "link": pl.Utf8,
            "category_id": pl.Utf8,
            "category_name": pl.Utf8,
            "item_url": pl.Utf8,
            "api_name": pl.Utf8,
            "matched_query": pl.Utf8,
            "primary_query": pl.Utf8,
            "is_best_match": pl.Boolean,
        }

        all_results = []

        for api_name, api_url in self.api_urls.items():
            try:
                api_key = (
                    self.drunkenslug_api_key
                    if api_name == "drunkenslug"
                    else self.ninjacentral_api_key
                )

                try:
                    results = self.get_nzb_results(api_url, api_key, query)

                    if not results["item"]:
                        continue

                    # Convert results to DataFrame
                    nzb_results_df = pl.DataFrame(results["item"])

                    # Extract size and category based on API format
                    if api_name == "drunkenslug":
                        # Drunken Slug has newznab:attr array with name/value pairs
                        nzb_results_df = nzb_results_df.with_columns(
                            [
                                pl.col("newznab:attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["_value"]
                                            for attr in attrs
                                            if attr["_name"] == "size"
                                        ),
                                        "0",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .cast(pl.Int64)
                                .fill_null(0)
                                .alias("size"),
                                pl.col("newznab:attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["_value"]
                                            for attr in attrs
                                            if attr["_name"] == "category"
                                        ),
                                        "",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .alias("category_id"),
                                pl.col("guid")
                                .struct.field("text")
                                .fill_null("")
                                .alias("item_url"),
                            ]
                        )
                    else:
                        # Ninja Central has attr array with @attributes containing name/value
                        nzb_results_df = nzb_results_df.with_columns(
                            [
                                pl.col("attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["@attributes"]["value"]
                                            for attr in attrs
                                            if attr["@attributes"]["name"] == "size"
                                        ),
                                        "0",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .cast(pl.Int64)
                                .fill_null(0)
                                .alias("size"),
                                pl.col("attr")
                                .map_elements(
                                    lambda attrs: next(
                                        (
                                            attr["@attributes"]["value"]
                                            for attr in attrs
                                            if attr["@attributes"]["name"] == "category"
                                        ),
                                        "",
                                    ),
                                    return_dtype=pl.Utf8,
                                )
                                .alias("category_id"),
                                pl.col("guid").alias("item_url"),
                            ]
                        )

                    # Add human-readable category names
                    nzb_results_df = nzb_results_df.with_columns(
                        [
                            pl.col("category_id")
                            .map_elements(
                                lambda x: self.get_category_info(api_name, x),
                                return_dtype=pl.Utf8,
                            )
                            .alias("category_name")
                        ]
                    )

                    # Select and reorder columns to match schema
                    nzb_results_df = nzb_results_df.select(
                        [
                            pl.col("title"),
                            pl.col("size"),
                            pl.col("link"),
                            pl.col("category_id"),
                            pl.col("category_name"),
                            pl.col("item_url"),
                            pl.lit(api_name).alias("api_name"),
                            pl.lit(None).alias("matched_query"),
                            pl.lit(None).alias("primary_query"),
                            pl.lit(False).alias("is_best_match"),
                        ]
                    )

                    all_results.append(nzb_results_df)

                except Exception as e:
                    print(f"Error processing results from {api_name}: {e!s}")
                    continue

            except Exception as e:
                print(f"Error fetching results from {api_name}: {e!s}")
                continue

        if not all_results:
            return pl.DataFrame(schema=empty_schema)

        combined_df = pl.concat(all_results)
        return combined_df.sort(by="size", descending=True)

    def search_multiple(
        self, search_queries_list: list[list[str]], validation_info: list[dict] = None
    ) -> pl.DataFrame:
        """
        Search for multiple sets of queries, trying each query in a set until results are found.
        Each item in search_queries_list is a list of fallback queries for one target.
        validation_info: Optional list of dicts with 'studio', 'date', 'performers' for validation
        Returns a DataFrame with all results and best matches identified.
        """
        empty_schema = {
            "title": pl.Utf8,
            "size": pl.Int64,
            "link": pl.Utf8,
            "category_id": pl.Utf8,
            "category_name": pl.Utf8,
            "item_url": pl.Utf8,
            "api_name": pl.Utf8,
            "matched_query": pl.Utf8,
            "primary_query": pl.Utf8,
            "is_best_match": pl.Boolean,
        }

        all_results = []
        best_matches = []

        for i, search_queries in enumerate(search_queries_list):
            target_results = None
            validation_data = (
                validation_info[i]
                if validation_info and i < len(validation_info)
                else None
            )

            # Try each query in order until we get valid results
            for query in search_queries:
                results = self.search_single(query)
                if not results.is_empty():
                    # If we have validation info, filter results
                    if validation_data:
                        valid_results = []
                        for result_dict in results.to_dicts():
                            if self._validate_search_result(
                                result_dict["title"],
                                validation_data.get("studio", ""),
                                validation_data.get("date", ""),
                                validation_data.get("performers", []),
                            ):
                                valid_results.append(result_dict)

                        if valid_results:
                            results = pl.DataFrame(valid_results)
                        else:
                            # No valid results, try next query
                            continue

                    # Add query info and is_best_match columns to match schema
                    results = results.with_columns(
                        [
                            pl.lit(query).alias("matched_query"),
                            pl.lit(search_queries[0]).alias("primary_query"),
                            pl.lit(True).alias("is_best_match"),
                        ]
                    )
                    target_results = results
                    break

            if target_results is not None:
                # Store best match (first/largest result) separately
                best_match = target_results.head(1)
                best_matches.append(best_match)

                all_results.append(target_results)
            else:
                # Add empty result with query information
                empty_df = pl.DataFrame(schema=empty_schema).with_columns(
                    [
                        pl.lit("").alias("matched_query"),
                        pl.lit(search_queries[0]).alias("primary_query"),
                        pl.lit(False).alias("is_best_match"),
                    ]
                )
                all_results.append(empty_df)
                best_matches.append(empty_df)

        if not all_results:
            return pl.DataFrame(schema=empty_schema)

        # Combine all results
        combined_results = pl.concat(all_results)
        best_matches_df = pl.concat(best_matches)

        # Update is_best_match column by matching against best_matches
        combined_results = combined_results.with_columns(
            [
                pl.struct(["title", "size", "link", "primary_query"])
                .is_in(
                    best_matches_df.select(["title", "size", "link", "primary_query"])
                )
                .alias("is_best_match")
            ]
        )

        return combined_results.sort(
            ["primary_query", "is_best_match", "size"], descending=[False, True, True]
        )

    def _validate_search_result(
        self, result_title, expected_studio, expected_date, expected_performers
    ):
        """
        Validate if a search result matches the expected scene criteria
        Returns True if the result is likely a match, False otherwise
        """
        if not result_title or not expected_studio or not expected_date:
            return True  # Skip validation if we don't have enough info

        title_lower = result_title.lower()
        studio_lower = expected_studio.lower()

        # Check if studio name appears in the title
        studio_formatted = expected_studio.replace(" ", "").replace("-", "").lower()
        if (
            studio_formatted not in title_lower
            and studio_lower.replace(" ", "") not in title_lower
        ):
            return False

        # Check if date appears in title in any common format
        from datetime import date, datetime

        try:
            # Handle both string and date objects
            if isinstance(expected_date, str):
                date_obj = datetime.strptime(expected_date, "%Y-%m-%d")
            elif isinstance(expected_date, date):
                date_obj = datetime.combine(expected_date, datetime.min.time())
            else:
                # If it's already a datetime object
                date_obj = expected_date
        except (ValueError, TypeError):
            return True  # Skip date validation if date format is invalid

        date_patterns = [
            date_obj.strftime("%y.%m.%d"),  # 25.02.22
            date_obj.strftime("%Y.%m.%d"),  # 2025.02.22
            date_obj.strftime("%y-%m-%d"),  # 25-02-22
            date_obj.strftime("%Y-%m-%d"),  # 2025-02-22
            date_obj.strftime("%y %m %d"),  # 25 02 22
            date_obj.strftime("%Y %m %d"),  # 2025 02 22
        ]

        date_found = any(date_pattern in title_lower for date_pattern in date_patterns)
        if not date_found:
            return False

        # Check if at least one performer appears in the title
        if expected_performers:
            performer_found = any(
                performer.lower().replace(" ", "")
                in title_lower.replace(" ", "").replace(".", "")
                for performer in expected_performers
            )
            if not performer_found:
                return False

        return True

    def search(self, query_or_queries) -> pl.DataFrame:
        """
        Backwards compatible search method that handles both single queries
        and lists of fallback queries
        """
        if isinstance(query_or_queries, str):
            return self.search_single(query_or_queries)
        if isinstance(query_or_queries, list):
            if all(isinstance(x, str) for x in query_or_queries):
                # Single list of fallback queries
                return self.search_multiple([query_or_queries])
            # List of lists of fallback queries
            return self.search_multiple(query_or_queries)
        raise ValueError(
            "Query must be a string or list of strings or list of lists of strings"
        )

    def _search_implementation(self, query: str) -> pl.DataFrame:
        """Internal method containing the original search implementation"""
        # Move the core implementation from the original search() method here
        # ... copy existing search() implementation here ...


def main():
    searcher = NZBSearch()
    results = searcher.search("your search query")
    print(results)


if __name__ == "__main__":
    main()
