"""Import 'Completionist' tag back onto performers from a previously exported JSON."""

import json
import os
import sys
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


def main():
    input_path = Path(__file__).parent / "completionist_performers.json"
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    data = json.loads(input_path.read_text())
    performers = data["performers"]
    print(f"Loaded {len(performers)} performers from {input_path.name}")

    stash = connect()
    tag = stash.find_tag(TAG_NAME)
    if not tag:
        print(f"Tag '{TAG_NAME}' not found in local Stash.")
        sys.exit(1)

    tag_id = tag["id"]
    total = len(performers)
    failed = []

    for i, performer in enumerate(performers, 1):
        name = performer["name"]
        pid = performer["id"]
        try:
            stash.update_performers(
                {"ids": pid, "tag_ids": {"mode": "ADD", "ids": [tag_id]}}
            )
            print(f"[{i}/{total}] Tagged {name} (ID {pid})")
        except Exception as exc:
            print(f"[{i}/{total}] FAILED {name} (ID {pid}): {exc}")
            failed.append(name)

    print(f"\nDone. Tagged {total - len(failed)}/{total} performers.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
