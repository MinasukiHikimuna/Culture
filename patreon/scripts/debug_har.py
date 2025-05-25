#!/usr/bin/env python3
"""
Debug script to examine HAR file contents in detail.
This will help identify why the test script isn't finding valid posts data.
"""

import json
import sys
from pathlib import Path


def debug_har_file(filepath):
    """Debug and analyze a HAR file in detail."""

    filepath = Path(filepath)

    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

    print(f"✅ Successfully loaded: {filepath}")
    print(f"📁 File size: {filepath.stat().st_size / 1024:.1f} KB")

    if "log" not in raw_data or "entries" not in raw_data["log"]:
        print("❌ Invalid HAR file format")
        return False

    entries = raw_data["log"]["entries"]
    print(f"📊 Total HAR entries: {len(entries)}")

    # Find all Patreon requests
    patreon_entries = []
    for i, entry in enumerate(entries):
        request = entry.get("request", {})
        response = entry.get("response", {})
        url = request.get("url", "")

        if "patreon.com" in url:
            patreon_entries.append((i, entry))

    print(f"🔍 Found {len(patreon_entries)} Patreon requests")

    # Examine each Patreon request
    for i, (entry_idx, entry) in enumerate(patreon_entries):
        request = entry.get("request", {})
        response = entry.get("response", {})
        url = request.get("url", "")
        method = request.get("method", "")
        status = response.get("status", 0)

        print(f"\n--- Patreon Request #{i+1} (Entry #{entry_idx}) ---")
        print(f"Method: {method}")
        print(f"Status: {status}")
        print(f"URL: {url}")

        # Check if it's an API request
        if "/api/" in url:
            print("✅ API request detected")

            # Check response content
            content = response.get("content", {})
            mime_type = content.get("mimeType", "")
            text = content.get("text", "")

            print(f"Content type: {mime_type}")
            print(f"Content length: {len(text)} characters")

            if mime_type in ["application/json", "application/vnd.api+json"] and text:
                try:
                    data = json.loads(text)
                    print("✅ Valid JSON response")

                    # Analyze the JSON structure
                    if isinstance(data, dict):
                        print(f"Root keys: {list(data.keys())}")

                        if "data" in data:
                            data_items = data["data"]
                            if isinstance(data_items, list):
                                print(f"Data items: {len(data_items)}")
                                if data_items:
                                    first_item = data_items[0]
                                    print(
                                        f"First item type: {first_item.get('type', 'Unknown')}"
                                    )
                                    if "attributes" in first_item:
                                        attrs = first_item["attributes"]
                                        print(
                                            f"Attributes: {list(attrs.keys())[:10]}..."
                                        )  # Show first 10
                            else:
                                print(f"Data is not a list: {type(data_items)}")
                        else:
                            print("❌ No 'data' field found")

                        if "included" in data:
                            included = data["included"]
                            print(f"Included items: {len(included)}")

                        if "meta" in data:
                            meta = data["meta"]
                            print(f"Meta keys: {list(meta.keys())}")

                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON: {e}")
                    print(f"First 200 chars: {text[:200]}...")
            else:
                print(f"❌ Not JSON or empty content")
                if text:
                    print(f"First 200 chars: {text[:200]}...")
        else:
            print("⚠️  Not an API request")

    # Look specifically for posts requests
    print(f"\n{'='*60}")
    print("LOOKING FOR POSTS REQUESTS:")

    posts_requests = []
    for i, (entry_idx, entry) in enumerate(patreon_entries):
        url = entry["request"]["url"]
        if "/api/posts" in url:
            posts_requests.append((i, entry_idx, entry))

    print(f"Found {len(posts_requests)} posts requests")

    for i, (patreon_idx, entry_idx, entry) in enumerate(posts_requests):
        print(f"\n--- Posts Request #{i+1} ---")
        request = entry.get("request", {})
        response = entry.get("response", {})

        print(f"URL: {request.get('url', '')}")
        print(f"Status: {response.get('status', 0)}")

        content = response.get("content", {})
        text = content.get("text", "")

        if text:
            try:
                data = json.loads(text)
                print("✅ Valid JSON response")

                if "data" in data:
                    data_items = data["data"]
                    if isinstance(data_items, list) and data_items:
                        print(f"✅ Found {len(data_items)} data items")

                        # Check first item
                        first_item = data_items[0]
                        print(f"First item type: {first_item.get('type', 'Unknown')}")

                        if "attributes" in first_item:
                            attrs = first_item["attributes"]
                            print(f"Attributes: {list(attrs.keys())}")

                            # Check for post-specific fields
                            post_fields = [
                                "title",
                                "content",
                                "published_at",
                                "post_type",
                            ]
                            found_fields = [f for f in post_fields if f in attrs]
                            if found_fields:
                                print(f"✅ Post fields found: {found_fields}")
                            else:
                                print("❌ No post fields found")
                    else:
                        print(f"❌ Data is empty or not a list: {type(data_items)}")
                        if isinstance(data_items, list):
                            print(f"List length: {len(data_items)}")
                else:
                    print("❌ No 'data' field in response")
                    print(f"Available keys: {list(data.keys())}")

            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}")
        else:
            print("❌ No response content")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_har.py <har_file>")
        sys.exit(1)

    har_file = sys.argv[1]
    debug_har_file(har_file)
