#!/usr/bin/env python3
"""Download missing/incomplete scripts from scriptbin.works."""

import json
import re
import sys
from pathlib import Path

from scriptbin_extractor import ScriptBinExtractor


def script_is_incomplete(script_file: Path) -> str | None:
    """Check if script.txt contains incomplete content."""
    if not script_file.exists():
        return None

    content = script_file.read_text(encoding="utf-8")
    if len(content) < 2000:
        match = re.search(r'https://scriptbin\.works/[^\s\)\]]+', content)
        if match:
            return match.group(0)

    return None


def find_scriptbin_downloads(releases_dir: Path) -> list[dict]:
    """Find releases needing scriptbin downloads."""
    to_download = []

    for release_json in releases_dir.rglob("release.json"):
        release_dir = release_json.parent

        try:
            with open(release_json) as f:
                release = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        script_file = release_dir / "script.txt"

        # Check for incomplete scripts (has scriptbin URL inside)
        scriptbin_url = script_is_incomplete(script_file)
        if scriptbin_url:
            to_download.append({
                "path": release_dir,
                "url": scriptbin_url,
                "type": "incomplete",
            })
            continue

        # Check for missing scripts with scriptbin URL
        if not script_file.exists():
            enrichment = release.get("enrichmentData", {})
            llm_analysis = enrichment.get("llmAnalysis", {}) if enrichment else {}
            script_info = llm_analysis.get("script", {}) if llm_analysis else {}
            script_url = script_info.get("url", "")

            if script_url and "scriptbin.works" in script_url:
                to_download.append({
                    "path": release_dir,
                    "url": script_url,
                    "type": "missing",
                })

    return to_download


def download_scripts(to_download: list[dict], dry_run: bool = False) -> None:
    """Download scripts from scriptbin.works."""
    if not to_download:
        print("No scripts to download.")
        return

    print(f"Found {len(to_download)} scripts to download from scriptbin.works")
    print()

    if dry_run:
        print("DRY RUN - would download:")
        for item in to_download:
            print(f"  [{item['type']}] {item['path'].name}")
            print(f"    URL: {item['url']}")
        return

    # Initialize extractor
    extractor = ScriptBinExtractor()
    extractor.setup_playwright()

    success = 0
    failed = 0

    try:
        for i, item in enumerate(to_download, 1):
            release_dir = item["path"]
            url = item["url"]

            print(f"[{i}/{len(to_download)}] {release_dir.name}")
            print(f"  URL: {url}")

            try:
                script_data = extractor.get_script_data(url)

                if not script_data or not script_data.get("script_content"):
                    print(f"  ❌ No content extracted")
                    failed += 1
                    continue

                # Save script.txt
                script_path = release_dir / "script.txt"
                script_path.write_text(script_data["script_content"], encoding="utf-8")
                print(f"  ✅ Saved: {script_path}")

                # Save script.html if available
                if script_data.get("html_content"):
                    html_path = release_dir / "script.html"
                    html_path.write_text(script_data["html_content"], encoding="utf-8")

                # Update release.json with script metadata
                release_json_path = release_dir / "release.json"
                release = json.loads(release_json_path.read_text())
                release["script"] = {
                    "url": url,
                    "source": "scriptbin.works",
                    "status": "downloaded",
                    "filePath": str(script_path),
                    **{k: v for k, v in script_data.get("metadata", {}).items()
                       if k not in ["url", "source", "status", "filePath"]},
                }
                release_json_path.write_text(
                    json.dumps(release, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

                success += 1

            except Exception as e:
                print(f"  ❌ Error: {e}")
                failed += 1

    finally:
        extractor.close_browser()

    print()
    print(f"Done: {success} succeeded, {failed} failed")


def download_single_url(url: str, release_dir: Path | None = None) -> None:
    """Download a single script from a URL."""
    if "scriptbin.works" not in url:
        print(f"Error: Only scriptbin.works URLs are supported, got: {url}")
        return

    print(f"Downloading: {url}")

    extractor = ScriptBinExtractor()
    extractor.setup_playwright()

    try:
        script_data = extractor.get_script_data(url)

        if not script_data or not script_data.get("script_content"):
            print("❌ No content extracted")
            return

        content = script_data["script_content"]
        # script_content is a list of lines, join them
        if isinstance(content, list):
            content = "\n".join(content)
        print(f"✅ Extracted {len(content)} characters")

        if release_dir:
            # Save to release directory
            script_path = release_dir / "script.txt"
            script_path.write_text(content, encoding="utf-8")
            print(f"✅ Saved: {script_path}")

            if script_data.get("html_content"):
                html_path = release_dir / "script.html"
                html_path.write_text(script_data["html_content"], encoding="utf-8")
                print(f"✅ Saved: {html_path}")

            # Update release.json
            release_json_path = release_dir / "release.json"
            if release_json_path.exists():
                release = json.loads(release_json_path.read_text())
                release["script"] = {
                    "url": url,
                    "source": "scriptbin.works",
                    "status": "downloaded",
                    "filePath": str(script_path),
                    **{k: v for k, v in script_data.get("metadata", {}).items()
                       if k not in ["url", "source", "status", "filePath"]},
                }
                release_json_path.write_text(
                    json.dumps(release, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                print(f"✅ Updated: {release_json_path}")
        else:
            # Preview mode - just print
            print("\n--- Preview (first 500 chars) ---")
            print(content[:500])
            if len(content) > 500:
                print("...")

            if script_data.get("metadata"):
                print("\n--- Metadata ---")
                for k, v in script_data["metadata"].items():
                    if v and k not in ["url", "extracted_at"]:
                        print(f"  {k}: {v}")

    finally:
        extractor.close_browser()


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Single URL mode: <url> [release_dir]
    if args and args[0].startswith("http"):
        url = args[0]
        release_dir = Path(args[1]) if len(args) > 1 else None
        if release_dir and not release_dir.exists():
            print(f"Error: Release directory does not exist: {release_dir}")
            return
        download_single_url(url, release_dir)
        return

    releases_dir = Path("data/releases")
    if not releases_dir.exists():
        print(f"Error: {releases_dir} does not exist")
        return

    to_download = find_scriptbin_downloads(releases_dir)
    download_scripts(to_download, dry_run=dry_run)


if __name__ == "__main__":
    main()
