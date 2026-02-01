"""One-off script to normalize tag filenames to match Stashapp casing."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libraries"))

from libraries.client_stashapp import StashAppClient


TAG_DIR = Path("/Volumes/Culture 1/Tags")


def main():
    client = StashAppClient()

    # Collect unique tag stems from .webm and .json files
    stems = {p.stem for p in TAG_DIR.iterdir() if p.suffix in (".webm", ".json")}

    for stem in sorted(stems):
        tags = client.stash.find_tags(f={"name": {"value": stem, "modifier": "EQUALS"}})
        if not tags:
            print(f"  SKIP  {stem} (not found in Stashapp)")
            continue

        canonical = tags[0]["name"]
        if canonical == stem:
            print(f"  OK    {stem}")
            continue

        for ext in (".webm", ".json"):
            old = TAG_DIR / f"{stem}{ext}"
            new = TAG_DIR / f"{canonical}{ext}"
            if old.exists():
                old.rename(new)
                print(f"  RENAME {old.name} -> {new.name}")


if __name__ == "__main__":
    main()
