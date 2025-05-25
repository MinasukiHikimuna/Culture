#!/usr/bin/env python3
"""
Quick validation script to validate captured Patreon data.
Run this before using the main scraper to ensure your captured data is valid.
"""

import json
import sys
from pathlib import Path


def validate_captured_file(filepath):
    """Validate and analyze a captured JSON or HAR file."""

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

    # Determine file type and extract data
    if filepath.suffix.lower() == ".har":
        print("🔍 HAR file detected")

        if "log" not in raw_data or "entries" not in raw_data["log"]:
            print("❌ Invalid HAR file format")
            return False

        # Extract Patreon API requests
        patreon_entries = []
        for entry in raw_data["log"]["entries"]:
            request = entry.get("request", {})
            response = entry.get("response", {})
            url = request.get("url", "")

            if (
                "patreon.com/api" in url
                and response.get("status") == 200
                and "content" in response
                and response["content"].get("mimeType")
                in ["application/json", "application/vnd.api+json"]
            ):
                patreon_entries.append(entry)

        print(f"📡 Found {len(patreon_entries)} Patreon API requests")

        if not patreon_entries:
            print("❌ No Patreon API requests found in HAR file")
            return False

        # Find posts request
        posts_entries = []
        for entry in patreon_entries:
            url = entry["request"]["url"]
            if "posts" in url:
                try:
                    content_text = entry["response"]["content"].get("text", "")
                    if content_text:
                        data = json.loads(content_text)
                        if "data" in data and data["data"]:
                            posts_entries.append((entry, data))
                except json.JSONDecodeError:
                    continue

        if not posts_entries:
            print("❌ No valid posts data found in HAR file")
            return False

        # Use the posts entry with the most data items
        entry, data = max(posts_entries, key=lambda x: len(x[1]["data"]))
        request_headers = {
            h["name"]: h["value"] for h in entry["request"].get("headers", [])
        }

        print(f"✅ Using posts request: {entry['request']['url']}")
        print(f"🔑 Headers captured: {len(request_headers)} headers")

        # Check important headers
        important_headers = ["Authorization", "Cookie", "User-Agent"]
        for header in important_headers:
            if header in request_headers:
                print(f"   ✅ {header}: Present")
            else:
                print(f"   ⚠️ {header}: Missing")

    else:
        print("🔍 JSON file detected")
        data = raw_data

        # Test basic structure
        if not isinstance(data, dict):
            print("❌ Expected JSON object at root level")
            return False

        # Check for data array
        if "data" not in data:
            print("❌ Missing 'data' field - this might not be a Patreon API response")
            return False

    data_items = data["data"]
    if not isinstance(data_items, list):
        data_items = [data_items]

    print(f"📊 Found {len(data_items)} data items")

    # Analyze first item
    if data_items:
        first_item = data_items[0]
        print(f"🔍 First item type: {first_item.get('type', 'Unknown')}")

        if "attributes" in first_item:
            attrs = first_item["attributes"]
            print(f"📝 Attributes found: {list(attrs.keys())}")

            # Look for common Patreon post fields
            expected_fields = ["title", "content", "published_at", "post_type"]
            found_fields = [field for field in expected_fields if field in attrs]
            if found_fields:
                print(f"✅ Post fields detected: {found_fields}")
            else:
                print("⚠️  No common post fields found - might not be post data")

        if "relationships" in first_item:
            rels = first_item["relationships"]
            print(f"🔗 Relationships found: {list(rels.keys())}")

    # Check pagination
    pagination_found = False
    if "meta" in data:
        if "pagination" in data["meta"]:
            pagination_found = True
            pagination = data["meta"]["pagination"]
            print(f"📄 Pagination info: {pagination}")
        if "count" in data["meta"]:
            print(f"📊 Total count: {data['meta']['count']}")

    if "links" in data:
        pagination_found = True
        print(f"🔗 Links found: {list(data['links'].keys())}")

    if not pagination_found:
        print("⚠️  No pagination info found - this might be the last page")

    # Check for included data (media, etc.)
    if "included" in data:
        included = data["included"]
        print(f"📎 Included items: {len(included)}")

        # Group by type
        types = {}
        for item in included:
            item_type = item.get("type", "unknown")
            types[item_type] = types.get(item_type, 0) + 1

        for item_type, count in types.items():
            print(f"   - {item_type}: {count}")

    # Look for media URLs
    media_count = 0

    # Check in data items
    for item in data_items:
        if "attributes" in item:
            attrs = item["attributes"]
            for field in ["image", "thumbnail", "video", "audio"]:
                if field in attrs and attrs[field]:
                    if isinstance(attrs[field], dict) and "url" in attrs[field]:
                        media_count += 1
                    elif isinstance(attrs[field], str) and attrs[field].startswith(
                        "http"
                    ):
                        media_count += 1

    # Check in included items
    if "included" in data:
        for item in data["included"]:
            if item.get("type") in ["media", "attachment"]:
                if "attributes" in item:
                    attrs = item["attributes"]
                    if "download_url" in attrs or "url" in attrs:
                        media_count += 1

    if media_count > 0:
        print(f"🖼️  Media URLs found: {media_count}")
    else:
        print("⚠️  No media URLs found - check if posts contain media")

    print("\n" + "=" * 50)
    print("SUMMARY:")

    if len(data_items) > 0:
        print("✅ Valid Patreon API response detected")
        print("✅ Ready to use with the scraper")

        # Quick usage reminder
        print(f"\nTo run the scraper:")
        print(f"python scripts/scraper.py {filepath}")

        return True
    else:
        print("❌ No valid data items found")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_capture.py <captured_file>")
        print("\nExamples:")
        print("python validate_capture.py captured/patreon_capture.har")
        print("python validate_capture.py captured/patreon_posts.json")
        sys.exit(1)

    captured_file = sys.argv[1]
    success = validate_captured_file(captured_file)

    if not success:
        print("\n❌ Validation failed. Please check the capture guide and try again.")
        sys.exit(1)
    else:
        print("\n✅ Validation passed! Your captured data looks good.")
