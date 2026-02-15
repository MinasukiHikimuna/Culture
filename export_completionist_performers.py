"""Export performers tagged with 'Completionist' from local Stash to a JSON file."""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from stashapi.stashapp import StashInterface


load_dotenv()

TAG_NAME = "Completionist"


def connect():
    scheme = os.getenv("STASHAPP_SCHEME")
    host = os.getenv("STASHAPP_HOST")
    port = int(os.getenv("STASHAPP_PORT", "443"))
    api_key = os.getenv("STASHAPP_API_KEY")
    if not host or not api_key:
        print("STASHAPP_HOST and STASHAPP_API_KEY must be set in .env")
        sys.exit(1)
    return StashInterface({"scheme": scheme, "host": host, "port": port, "apikey": api_key})


def find_performers(stash, tag_id):
    performers = []
    page = 1
    while True:
        result = stash.find_performers(
            {"tags": {"value": [tag_id], "modifier": "INCLUDES"}},
            {"page": page, "per_page": 25},
            fragment="id name disambiguation stash_ids { stash_id endpoint }",
        )
        performers.extend(result)
        if len(result) < 25:
            break
        page += 1
    return performers


def main():
    stash = connect()
    tag = stash.find_tag({"name": TAG_NAME})
    if not tag:
        print(f"Tag '{TAG_NAME}' not found in local Stash.")
        sys.exit(1)

    print(f"Found tag '{TAG_NAME}' (ID: {tag['id']}). Querying performers...")
    performers = find_performers(stash, tag["id"])
    print(f"Found {len(performers)} performers.")

    output = {
        "exported_at": datetime.now(UTC).isoformat(),
        "tag": TAG_NAME,
        "count": len(performers),
        "performers": performers,
    }

    output_path = Path(__file__).parent / "completionist_performers.json"
    output_path.write_text(json.dumps(output, indent=2))
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
