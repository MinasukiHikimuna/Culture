#!/usr/bin/env python3
"""Find releases that have script URLs available but where scripts haven't been downloaded."""

import json
import re
from pathlib import Path

import config as aural_config


def script_is_incomplete(script_file: Path) -> str | None:
    """
    Check if script.txt contains incomplete content (just a Reddit post with a link).

    Returns the scriptbin URL if found (indicating incomplete), None otherwise.
    """
    if not script_file.exists():
        return None

    content = script_file.read_text(encoding="utf-8")

    # Check if content is small and contains a scriptbin link
    # Real scripts are typically much longer than Reddit post summaries
    if len(content) < 2000:
        # Look for scriptbin.works links in the content
        match = re.search(r'https://scriptbin\.works/[^\s\)\]]+', content)
        if match:
            return match.group(0)

    return None


def find_missing_scripts(releases_dir: Path) -> None:
    """Scan releases and report on script download status."""
    total_releases = 0
    has_script_url = 0
    scripts_downloaded = 0
    missing_scripts: list[dict] = []
    incomplete_scripts: list[dict] = []

    for release_json in releases_dir.rglob("release.json"):
        total_releases += 1
        release_dir = release_json.parent

        try:
            with open(release_json) as f:
                release = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read {release_json}: {e}")
            continue

        # Check for script URL in enrichmentData.llmAnalysis.script.url
        script_url = None
        enrichment = release.get("enrichmentData", {})
        if enrichment:
            llm_analysis = enrichment.get("llmAnalysis", {})
            if llm_analysis:
                script_info = llm_analysis.get("script", {})
                if script_info:
                    script_url = script_info.get("url")

        if not script_url:
            continue

        has_script_url += 1

        # Check if script is downloaded
        script_file = release_dir / "script.txt"
        top_script = release.get("script", {})

        # First check for incomplete scripts (Reddit post saved instead of actual script)
        scriptbin_url = script_is_incomplete(script_file)
        if scriptbin_url:
            incomplete_scripts.append({
                "path": str(release_dir),
                "script_url": script_url,
                "scriptbin_url": scriptbin_url,
            })
            continue

        is_downloaded = (
            script_file.exists()
            or (isinstance(top_script, dict) and top_script.get("status") == "downloaded")
        )

        if is_downloaded:
            scripts_downloaded += 1
        else:
            missing_scripts.append({
                "path": str(release_dir),
                "script_url": script_url,
            })

    # Print report
    print("Script Download Status Report")
    print("=" * 50)
    print(f"Total releases scanned: {total_releases}")
    print(f"Releases with script URLs: {has_script_url}")
    print(f"Scripts downloaded: {scripts_downloaded}")
    print(f"Scripts incomplete (failed scriptbin): {len(incomplete_scripts)}")
    print(f"Scripts missing: {len(missing_scripts)}")
    print()

    if incomplete_scripts:
        print("Incomplete Scripts (need re-download from scriptbin):")
        print("-" * 50)
        for i, item in enumerate(incomplete_scripts, 1):
            print(f"{i}. {item['path']}")
            print(f"   Scriptbin URL: {item['scriptbin_url']}")
            print()
        print("\nCommands to download incomplete scripts:")
        print("-" * 50)
        for item in incomplete_scripts:
            print(f"uv run python download_missing_scripts.py {item['scriptbin_url']} {item['path']}")
        print()

    if missing_scripts:
        print("Missing Scripts:")
        print("-" * 50)
        for i, item in enumerate(missing_scripts, 1):
            print(f"{i}. {item['path']}")
            print(f"   Script URL: {item['script_url']}")
            print()

        # Filter scriptbin URLs for easy download commands
        scriptbin_missing = [s for s in missing_scripts if "scriptbin.works" in s["script_url"]]
        if scriptbin_missing:
            print("\nCommands to download missing scriptbin scripts:")
            print("-" * 50)
            for item in scriptbin_missing:
                print(f"uv run python download_missing_scripts.py {item['script_url']} {item['path']}")
            print()


def main() -> None:
    releases_dir = aural_config.RELEASES_DIR
    if not releases_dir.exists():
        print(f"Error: {releases_dir} does not exist")
        return

    find_missing_scripts(releases_dir)


if __name__ == "__main__":
    main()
