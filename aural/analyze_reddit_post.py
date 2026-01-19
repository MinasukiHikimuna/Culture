#!/usr/bin/env python3
"""
Enhanced Reddit Post Analyzer with LLM-based Metadata Extraction

Uses LLM for all metadata extraction (performers, script, audio versions)
instead of regex-based preprocessing.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from exceptions import LMStudioUnavailableError


# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")


class EnhancedRedditPostAnalyzer:
    def __init__(
        self,
        lm_studio_url: str | None = None,
        model: str | None = None,
        enable_script_resolution: bool = True,
    ):
        self.lm_studio_url = (
            lm_studio_url
            or os.getenv("LM_STUDIO_URL")
            or "http://localhost:1234/v1/chat/completions"
        )
        self.model = model or "local-model"
        self.enable_script_resolution = enable_script_resolution

    def create_cyoa_detection_prompt(self, post_data: dict) -> str:
        """Creates a prompt to detect Choose Your Own Adventure (CYOA) releases."""
        reddit_data = post_data["reddit_data"]
        title = reddit_data["title"]
        selftext = reddit_data["selftext"]

        return f"""Analyze this Reddit post from r/gonewildaudio to determine if it is a Choose Your Own Adventure (CYOA) release.

CRITICAL: Respond with ONLY valid JSON. No explanations or reasoning.

TITLE: {title}

POST BODY:
{selftext}

WHAT IS A CYOA:
- Multiple audio files that form a DECISION TREE
- Listeners make choices that lead to different audio paths
- Has multiple possible endings based on choices
- Often includes a visual flowchart/roadmap image showing the paths
- Audio files are numbered but NOT meant for sequential listening
- Example: "Audio 0 -> choose Audio 1 OR Audio 2 -> each leads to different endings"

NOT A CYOA (standard releases):
- Simple multi-part series (Part 1, Part 2, Part 3 - sequential listening)
- Gender variants (F4M version, F4F version - same content, different target)
- Audio quality variants (SFX version, no-SFX version)
- Single audio with multiple hosting platforms

Return this exact JSON structure:
{{
  "is_cyoa": true|false,
  "confidence": "high|medium|low",
  "audio_count": <number of audio files detected>,
  "endings_count": <number of endings mentioned, or null if not specified>,
  "has_decision_tree_image": true|false,
  "decision_tree_url": "url to flowchart image or null",
  "reason": "brief explanation of why this is or is not a CYOA"
}}"""

    def detect_cyoa(self, post_data: dict) -> dict:
        """
        Detects if a post is a Choose Your Own Adventure (CYOA) release
        that requires special handling with decision tree mapping.
        """
        try:
            prompt = self.create_cyoa_detection_prompt(post_data)
            llm_response = self.call_llm(prompt)
            result = self.parse_cyoa_detection_response(llm_response)
            return result
        except Exception as e:
            print(f"CYOA detection failed: {e}")
            return {
                "is_cyoa": False,
                "confidence": "low",
                "audio_count": 0,
                "endings_count": None,
                "has_decision_tree_image": False,
                "decision_tree_url": None,
                "reason": f"Detection failed: {e}",
                "detection_error": True,
            }

    def parse_cyoa_detection_response(self, response_text: str) -> dict:
        """Parses and validates the CYOA detection response."""
        try:
            clean_text = re.sub(
                r"<think>[\s\S]*?</think>", "", response_text, flags=re.IGNORECASE
            )
            clean_text = re.sub(r"^[^{]*", "", clean_text)
            clean_text = re.sub(r"[^}]*$", "", clean_text)
            clean_text = clean_text.strip()

            if not clean_text.startswith("{"):
                json_match = re.search(r"\{[\s\S]*\}", response_text)
                clean_text = json_match.group(0) if json_match else response_text

            # Try to parse, and if it fails, attempt repair
            try:
                parsed = json.loads(clean_text)
            except json.JSONDecodeError:
                repaired = self._repair_json(clean_text)
                parsed = json.loads(repaired)

            if not isinstance(parsed.get("is_cyoa"), bool):
                raise ValueError("Missing required field: is_cyoa")

            return parsed
        except Exception as e:
            print(f"Failed to parse CYOA detection response: {response_text}")
            raise ValueError(f"Invalid JSON response from LLM: {e}") from e

    def _extract_audio_urls_from_text(self, text: str) -> list[dict]:
        """Pre-extract all audio platform URLs from text to prevent LLM hallucination."""
        audio_platforms = {
            "soundgasm.net": "Soundgasm",
            "whyp.it": "Whypit",
            "hotaudio.net": "HotAudio",
            "audiochan.com": "Audiochan",
            "erocast.me": "Erocast",
        }

        # Match URLs in markdown links [text](url) and bare URLs
        url_pattern = r"https?://(?:www\.)?(" + "|".join(
            re.escape(domain) for domain in audio_platforms
        ) + r')[^\s\)\]"<>]*'

        urls = []
        seen = set()
        for match in re.finditer(url_pattern, text, re.IGNORECASE):
            url = match.group(0)
            # Clean up trailing punctuation that might have been captured
            url = url.rstrip(".,;:!?")
            if url not in seen:
                seen.add(url)
                # Determine platform from URL
                platform = "Unknown"
                for domain, name in audio_platforms.items():
                    if domain in url.lower():
                        platform = name
                        break
                urls.append({"url": url, "platform": platform, "index": len(urls)})

        return urls

    def create_metadata_extraction_prompt(self, post_data: dict) -> str:
        """Creates a comprehensive metadata extraction prompt."""
        reddit_data = post_data["reddit_data"]
        title = reddit_data["title"]
        selftext = reddit_data["selftext"]
        author = reddit_data["author"]
        link_flair_text = reddit_data.get("link_flair_text") or "No flair"

        # Pre-extract URLs to prevent LLM hallucination
        pre_extracted_urls = self._extract_audio_urls_from_text(selftext)
        self._last_extracted_urls = pre_extracted_urls  # Store for validation

        # Format pre-extracted URLs for the prompt
        if pre_extracted_urls:
            urls_list = "\n".join(
                f"  [{u['index']}] {u['platform']}: {u['url']}"
                for u in pre_extracted_urls
            )
            urls_section = f"""
PRE-EXTRACTED AUDIO URLs (use these EXACT URLs, do NOT modify them):
{urls_list}

CRITICAL: When creating audio_versions, you MUST use the EXACT URLs listed above.
Do NOT retype, modify, truncate, or reconstruct URLs. Copy them exactly as shown."""
        else:
            urls_section = "\nNo audio platform URLs detected in post body."

        return f"""Extract metadata from this Reddit post from r/gonewildaudio.

CRITICAL: Respond with ONLY valid JSON. No explanations or reasoning.

POST AUTHOR (the person who posted this): {author}
TITLE: {title}
FLAIR: {link_flair_text}
{urls_section}

POST BODY:
{selftext}

EXTRACTION RULES:

1. PERFORMERS:
   - The post author "{author}" is ALWAYS the PRIMARY performer
   - Look for ADDITIONAL performers (collaborators who also performed) in:
     * Title patterns: "w Username", "w/ Username", "; w Username" at the end
     * Body patterns: "recorded with u/Username", "collab with u/Username", "live with u/Username"
   - Do NOT include script authors as performers unless they also voice-acted

2. SCRIPT AUTHOR:
   - Look for the person who WROTE the script (separate from performers):
     * Title patterns: "by Username" or "by u/Username" appearing AFTER the tags at the end
     * Body patterns: "Thanks to u/Username for... script", "script by u/Username"
   - If flair is "OC", script author = post author
   - If flair is "Script Fill", someone else wrote the script - find who

3. AUDIO VERSIONS (CRITICAL - proper URL grouping):
   - ONLY use URLs from the PRE-EXTRACTED AUDIO URLs section above
   - Do NOT include URLs from unsupported platforms (chirb.it, clyp.it, vocaroo, etc.)
   - If no pre-extracted URLs exist, set audio_versions to an empty array
   - Supported platforms: soundgasm.net, whyp.it, hotaudio.net, audiochan.com, erocast.me
   - CRITICAL: Multiple URLs from the SAME platform = DIFFERENT audio files, NOT mirrors
     * If you see 2 soundgasm.net URLs, those are 2 SEPARATE audio_versions
     * Mirrors ONLY exist across DIFFERENT platforms (Soundgasm + Whyp.it for same audio)
   - Group URLs ONLY when they are the SAME AUDIO on DIFFERENT platforms:
     * Look for "alternative link", "backup", "mirror", "if X isn't working"
     * Example: "AUDIO HERE (soundgasm)" + "alternative link (whyp.it)" = ONE version
   - Create SEPARATE audio_versions for genuinely DIFFERENT content:
     * Gender variants (F4M vs F4F)
     * Audio quality variants (SFX vs no-SFX, with/without specific sections)
     * "Version WITH X" vs "Version WITHOUT X" = SEPARATE audio_versions
     * Multi-part series (Part 1, Part 2)
     * Bloopers/extras
     * Different durations = different content
   - version_name rules:
     * NEVER include platform names (NOT "Main Audio (Soundgasm)")
     * Use content descriptors: "F4M", "SFX Version", "Part 1", "Bloopers"
     * For single audio: use primary gender tag from title (e.g., "F4M")
   - For EACH audio version, also extract:
     * performers: WHO performs in THIS specific audio
     * tags: Tags specific to THIS audio version

4. SCRIPT URL (CRITICAL - find the ACTUAL script, not the announcement):
   - The script URL is where the SCRIPT TEXT lives, NOT a Reddit "script offer" post
   - Valid script platforms: scriptbin.works, archiveofourown.org (AO3)
   - Look for patterns like:
     * "script is available [here](https://archiveofourown.org/works/...)"
     * "script [here](https://scriptbin.works/...)"
     * "[script](url)" linking to scriptbin or AO3
   - If post links to BOTH a Reddit "script offer" post AND a scriptbin/AO3 URL, use the scriptbin/AO3 URL
   - Do NOT use Reddit URLs as script URLs - those are announcements, not the script itself

5. SERIES:
   - Check if this is part of a series (Part 1, Episode 2, etc.)
   - Look for "sequel to", "prequel to", "continued from"

6. POST TYPE:
   - "audio_release": Post contains audio links - this is an audio release (most common)
   - "verification": Verification post where a performer introduces themselves
     * Title contains [Verification] tag
     * Flair often says "Verification"
     * Usually contains an audio link (treat as audio content)
   - "script_offer": Post is offering a SCRIPT for others to perform - no audio expected
     * Typically posted in r/GWAScriptGuild
     * Flair often says "Script Offer" or similar
     * Contains script link but NO audio platform URLs
     * Author is the script WRITER, not a performer
   - "request": User requesting content (ignore these)
   - "other": Announcements, meta posts, discussions without audio content

Return this exact JSON structure:
{{
  "performers": {{
    "primary": "{author}",
    "additional": ["username1"],
    "confidence": "high|medium|low",
    "notes": "how collaborators were identified"
  }},
  "script": {{
    "author": "username or null",
    "url": "script url or null",
    "fillType": "original|public|private",
    "notes": "how script author was identified"
  }},
  "audio_versions": [
    {{
      "version_name": "F4M",
      "description": "Primary audio version",
      "urls": [
        {{"platform": "Soundgasm", "url": "https://soundgasm.net/..."}},
        {{"platform": "Whypit", "url": "https://whyp.it/..."}},
        {{"platform": "HotAudio", "url": "https://hotaudio.net/..."}},
        {{"platform": "Audiochan", "url": "https://audiochan.com/a/..."}},
        {{"platform": "Erocast", "url": "https://erocast.me/..."}}
      ],
      "performers": ["username1"],
      "tags": ["tag1", "tag2"]
    }}
  ],
  "series": {{
    "isPartOfSeries": false,
    "hasPrequels": false,
    "hasSequels": false,
    "seriesName": "",
    "partNumber": null,
    "confidence": "high|medium|low"
  }},
  "post_type": "audio_release|verification|script_offer|request|other",
  "analysis_notes": "brief observations"
}}"""

    def create_version_naming_prompt(
        self, post_data: dict, audio_versions: list
    ) -> str:
        """Creates version naming prompt for generating file/directory slugs."""
        reddit_data = post_data["reddit_data"]
        title = reddit_data["title"]
        selftext = reddit_data["selftext"]
        post_id = reddit_data.get("post_id") or post_data.get("post_id")

        versions_text = "\n".join(
            f"{i + 1}. {v.get('version_name') or f'Version {i + 1}'}: "
            f"{v.get('description') or ''} | URLs: {', '.join(u['url'] for u in v.get('urls', []))}"
            for i, v in enumerate(audio_versions)
        )

        return f"""You are a file naming expert. Analyze this Reddit post and its audio versions to create optimal flat file naming within a single directory.

CRITICAL: Your response must be ONLY valid JSON. No reasoning or explanations.

POST: {title}
CONTENT: {selftext}
POST_ID: {post_id}

AUDIO VERSIONS DETECTED:
{versions_text}

NAMING PATTERN: {{post_id}}_{{release_slug}}_-_{{version_slug}}.{{ext}}

RELEASE SLUG RULES:
- Extract core title, remove brackets and gender tags
- Convert to lowercase snake_case
- Maximum 40 characters
- Examples: "sweet_southern_hospitality", "anniversary_date", "let_me_cater_to_you"

VERSION SLUG RULES (CRITICAL - each audio MUST have a UNIQUE slug):
1. **Multi-part series** (Part 1, Part 2, Part 3 or named parts):
   - Use part names: "part1_after_show_edge", "part2_lavish_limo_ride", "part3_final_performance"
   - Include part number AND descriptive name for uniqueness

2. **Multi-scenario projects** (8+ audios, different stories):
   - Use scenario names: "intro", "learning_to_ride_horse", "southern_cookin"

3. **Gender variants** (F4M/F4F/M4F/M4M):
   - Use gender tags: "f4m", "f4f", "m4f", "m4m"

4. **Audio quality variants**:
   - "sfx + music" -> "sfx_music"
   - "sfx + no music" -> "sfx_no_music"
   - "just vocals" -> "vocals_only"
   - "with wet sounds" -> "wet_sounds"

5. **Combined variants**: Combine with underscore
   - "f4m_sfx_music", "f4f_vocals_only"

6. **Single version**: Use primary gender tag or "default"

IMPORTANT: Every audio file MUST have a UNIQUE filename. Never use the same slug for multiple audios.

SANITIZATION:
- Lowercase only
- Replace spaces/punctuation with underscores
- Remove brackets, quotes, emojis
- Maximum 30 characters per version slug

Return JSON:
{{
  "release_directory": "{{post_id}}_{{release_slug}}",
  "release_slug": "{{sanitized_release_title}}",
  "audio_files": [
    {{
      "filename": "{{post_id}}_{{release_slug}}_-_{{version_slug}}.{{ext}}",
      "version_slug": "{{sanitized_version_name}}",
      "display_name": "{{human_readable_version_name}}",
      "detected_tags": ["{{tag1}}", "{{tag2}}"],
      "audio_urls": ["{{url1}}", "{{url2}}"],
      "metadata_file": "{{post_id}}_{{release_slug}}_-_{{version_slug}}.json"
    }}
  ],
  "structure_type": "{{multi_scenario|gender_variants|quality_variants|combined_variants|single_version}}"
}}"""

    def call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """Calls the local LLM API to analyze the post."""
        try:
            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    self.lm_studio_url,
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": "Respond with valid JSON only. No reasoning. "
                                "No explanations. No text outside JSON.\n\n" + prompt,
                            },
                        ],
                        "temperature": 0.1,
                        "max_tokens": max_tokens,
                    },
                )

                if response.status_code != 200:
                    raise ValueError(
                        f"API request failed: {response.status_code} {response.text}"
                    )

                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.ConnectError as e:
            raise LMStudioUnavailableError(self.lm_studio_url, e) from e

    def _repair_json(self, json_str: str) -> str:
        """Attempts to repair common JSON malformations from LLM output."""
        import re

        repaired = json_str

        # Step 1: Fix invalid escape sequences
        # Common invalid escapes from LLMs: \s, \d, \w, \S, \D, \W, etc.
        # These are regex patterns that LLMs sometimes include in JSON strings
        invalid_escapes = [
            r"\\s", r"\\S", r"\\d", r"\\D", r"\\w", r"\\W",
            r"\\v", r"\\h", r"\\c", r"\\p", r"\\P", r"\\x",
            r"\\[0-9]", r"\\e", r"\\a", r"\\z", r"\\Z"
        ]

        # Replace invalid escapes with their literal character representation
        # We need to be careful not to break valid JSON escapes like \n, \t, \", \\, etc.
        for pattern in invalid_escapes:
            # Only replace if it's not already properly escaped (i.e., not \\\\s)
            repaired = re.sub(
                pattern,
                lambda m: m.group(0).replace("\\", ""),
                repaired
            )

        # Step 2: Fix common comma issues in arrays/objects
        # Missing comma between array elements: "] [" -> "], ["
        repaired = re.sub(r"\]\s*\[", "], [", repaired)

        # Missing comma between object elements: "} {" -> "}, {"
        repaired = re.sub(r"\}\s*\{", "}, {", repaired)

        # Missing comma after closing bracket before opening brace: "] {" -> "], {"
        repaired = re.sub(r"\]\s*\{", "], {", repaired)

        # Missing comma after closing brace before opening bracket: "} [" -> "}, ["
        repaired = re.sub(r"\}\s*\[", "}, [", repaired)

        # Missing comma between string value and next key: `"value" "key"` -> `"value", "key"`
        repaired = re.sub(r'"\s+"([a-zA-Z_])', r'", "\1', repaired)

        # Step 3: Handle missing closing brackets/braces
        open_braces = repaired.count("{")
        close_braces = repaired.count("}")
        open_brackets = repaired.count("[")
        close_brackets = repaired.count("]")

        missing_brackets = open_brackets - close_brackets
        missing_braces = open_braces - close_braces

        if missing_brackets > 0 or missing_braces > 0:
            # Find the position just before the final closing braces
            # We need to insert missing ] before the final }
            repaired = repaired.rstrip()

            # Remove trailing braces temporarily
            trailing_braces = ""
            while repaired.endswith("}"):
                trailing_braces = "}" + trailing_braces
                repaired = repaired[:-1]

            # Add missing brackets
            repaired += "]" * missing_brackets

            # Add back the trailing braces, plus any missing ones
            repaired += trailing_braces
            if missing_braces > 0:
                repaired += "}" * missing_braces

        return repaired

    def _validate_and_fix_urls(self, parsed: dict) -> dict:
        """Validate and fix URLs in parsed response against pre-extracted URLs."""
        if not hasattr(self, "_last_extracted_urls") or not self._last_extracted_urls:
            return parsed

        valid_urls = {u["url"] for u in self._last_extracted_urls}
        valid_urls_lower = {u["url"].lower(): u["url"] for u in self._last_extracted_urls}

        def find_best_match(llm_url: str) -> str | None:
            """Find the best matching pre-extracted URL for an LLM-provided URL."""
            # Exact match
            if llm_url in valid_urls:
                return llm_url

            # Case-insensitive match
            if llm_url.lower() in valid_urls_lower:
                return valid_urls_lower[llm_url.lower()]

            # Prefix match (LLM truncated the URL)
            llm_lower = llm_url.lower().rstrip("/")
            for original in self._last_extracted_urls:
                original_lower = original["url"].lower().rstrip("/")
                if original_lower.startswith(llm_lower) or llm_lower.startswith(original_lower):
                    return original["url"]

            # Fuzzy match: find URL with longest common prefix
            best_match = None
            best_score = 0
            for original in self._last_extracted_urls:
                # Calculate common prefix length
                original_lower = original["url"].lower()
                common_len = 0
                for i, (a, b) in enumerate(zip(llm_lower, original_lower, strict=False)):
                    if a == b:
                        common_len = i + 1
                    else:
                        break
                # Require at least matching the domain and user path
                if common_len > best_score and common_len > 40:
                    best_score = common_len
                    best_match = original["url"]

            return best_match

        # Fix URLs in audio_versions
        fixed_count = 0
        for version in parsed.get("audio_versions", []):
            for url_entry in version.get("urls", []):
                llm_url = url_entry.get("url", "")
                if llm_url and llm_url not in valid_urls:
                    fixed_url = find_best_match(llm_url)
                    if fixed_url:
                        print(f"  URL fix: {llm_url[:60]}... -> {fixed_url[:60]}...")
                        url_entry["url"] = fixed_url
                        fixed_count += 1
                    else:
                        print(f"  WARNING: Could not match LLM URL to pre-extracted: {llm_url}")

        if fixed_count > 0:
            print(f"  Fixed {fixed_count} hallucinated URL(s)")

        return parsed

    def _add_missing_urls_as_versions(self, parsed: dict) -> dict:
        """
        Add missing pre-extracted URLs as separate audio_versions.

        When the LLM fails to include all URLs (common with large collab posts),
        this method creates audio_versions for each missing URL.
        """
        if not hasattr(self, "_last_extracted_urls") or not self._last_extracted_urls:
            return parsed

        # Collect all URLs already in audio_versions
        included_urls = set()
        for version in parsed.get("audio_versions", []):
            for url_entry in version.get("urls", []):
                url = url_entry.get("url", "")
                if url:
                    included_urls.add(url.lower().rstrip("/"))

        # Find missing URLs
        missing_urls = []
        for pre_extracted in self._last_extracted_urls:
            url = pre_extracted.get("url", "")
            url_normalized = url.lower().rstrip("/")
            if url and url_normalized not in included_urls:
                missing_urls.append(pre_extracted)

        if not missing_urls:
            return parsed

        # Only add missing URLs if a significant number were missed
        # (to avoid duplicating due to minor URL normalization differences)
        total_pre_extracted = len(self._last_extracted_urls)
        missing_count = len(missing_urls)

        # If more than 50% of URLs are missing, likely LLM truncation issue
        if missing_count < 3 or (missing_count / total_pre_extracted) < 0.5:
            return parsed

        print(f"  WARNING: LLM missed {missing_count}/{total_pre_extracted} URLs, adding as separate audio_versions")

        # Create audio_versions for missing URLs
        for url_info in missing_urls:
            url = url_info.get("url", "")
            platform = url_info.get("platform", "Unknown")

            # Extract version name from URL path
            version_name = self._extract_version_name_from_url(url)

            new_version = {
                "version_name": version_name,
                "description": f"Audio from {platform}",
                "urls": [{"platform": platform, "url": url}],
                "performers": [],  # Unknown without context
                "tags": [],
                "auto_added": True,  # Mark as automatically added
            }
            parsed["audio_versions"].append(new_version)

        return parsed

    def _extract_version_name_from_url(self, url: str) -> str:
        """Extract a human-readable version name from a URL."""
        parsed_url = urllib.parse.urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")

        if len(path_parts) >= 2:
            # For soundgasm: /u/username/audio-title
            # For whyp.it: /tracks/id/audio-title
            audio_slug = path_parts[-1]
            # Convert slug to readable name
            audio_slug = audio_slug.replace("-", " ").replace("_", " ")
            # Clean up common prefixes
            for prefix in ["f4m ", "f4f ", "m4f ", "m4m ", "a4a "]:
                if audio_slug.lower().startswith(prefix):
                    audio_slug = audio_slug[len(prefix):]
            # Capitalize words
            words = audio_slug.split()
            if words:
                return " ".join(word.capitalize() for word in words[:6])  # Limit length

        return "Audio"

    def parse_response(self, response_text: str) -> dict:
        """Parses and validates the LLM response."""
        try:
            # Remove any reasoning tokens and other unwanted text
            clean_text = re.sub(
                r"<think>[\s\S]*?</think>", "", response_text, flags=re.IGNORECASE
            )
            clean_text = re.sub(r"^[^{]*", "", clean_text)  # Remove before first {
            clean_text = re.sub(r"[^}]*$", "", clean_text)  # Remove after last }
            clean_text = clean_text.strip()

            # If we still don't have clean JSON, try to extract it
            if not clean_text.startswith("{"):
                json_match = re.search(r"\{[\s\S]*\}", response_text)
                clean_text = json_match.group(0) if json_match else response_text

            # Try to parse, and if it fails, attempt repair
            try:
                parsed = json.loads(clean_text)
            except json.JSONDecodeError:
                repaired = self._repair_json(clean_text)
                parsed = json.loads(repaired)

            # Validate required fields for metadata extraction
            if "performers" not in parsed:
                raise ValueError("Missing required field: performers")
            if "audio_versions" not in parsed:
                raise ValueError("Missing required field: audio_versions")
            if "series" not in parsed:
                raise ValueError("Missing required field: series")

            # Validate and fix URLs against pre-extracted URLs
            parsed = self._validate_and_fix_urls(parsed)

            # Check for missing URLs and add them as separate audio_versions
            parsed = self._add_missing_urls_as_versions(parsed)

            return parsed
        except Exception as e:
            print(f"Failed to parse LLM response: {response_text}")
            raise ValueError(f"Invalid JSON response from LLM: {e}") from e

    def parse_version_naming_response(self, response_text: str) -> dict:
        """Parses and validates the version naming LLM response."""
        try:
            # Remove any reasoning tokens and other unwanted text
            clean_text = re.sub(
                r"<think>[\s\S]*?</think>", "", response_text, flags=re.IGNORECASE
            )
            clean_text = re.sub(r"^[^{]*", "", clean_text)
            clean_text = re.sub(r"[^}]*$", "", clean_text)
            clean_text = clean_text.strip()

            if not clean_text.startswith("{"):
                json_match = re.search(r"\{[\s\S]*\}", response_text)
                clean_text = json_match.group(0) if json_match else response_text

            # Try to parse, and if it fails, attempt repair
            try:
                parsed = json.loads(clean_text)
            except json.JSONDecodeError:
                repaired = self._repair_json(clean_text)
                parsed = json.loads(repaired)

            # Validate version naming response structure
            if not all(
                k in parsed
                for k in ["release_directory", "release_slug", "audio_files"]
            ):
                raise ValueError("Missing required fields for version naming")

            return parsed
        except Exception as e:
            print(f"Failed to parse version naming LLM response: {response_text}")
            raise ValueError(f"Invalid JSON response from LLM: {e}") from e

    def generate_version_naming(self, post_data: dict, audio_versions: list) -> dict:
        """Generates version naming information using LLM."""
        try:
            prompt = self.create_version_naming_prompt(post_data, audio_versions)
            # Use higher token limit for CYOA or releases with many audio files
            max_tokens = 4000 if len(audio_versions) > 5 else 2000
            llm_response = self.call_llm(prompt, max_tokens=max_tokens)
            naming_data = self.parse_version_naming_response(llm_response)
            return naming_data
        except Exception as e:
            print(f"Version naming generation failed: {e}")
            # Fallback to simple naming
            return self.generate_fallback_naming(post_data, audio_versions)

    def expand_cyoa_audio_versions(
        self, audio_versions: list, post_data: dict
    ) -> list:
        """
        Expand CYOA audio_versions where multiple URLs were incorrectly grouped.

        For CYOA releases, each audio URL should be its own audio_version since
        they represent different audio files (intro, endings, etc.), not mirrors
        of the same audio on different platforms.
        """
        expanded = []
        selftext = post_data.get("reddit_data", {}).get("selftext", "")

        for version in audio_versions:
            urls = version.get("urls", [])

            # Check if this version has multiple URLs from the same platform
            # That's the signal that URLs were incorrectly grouped
            platforms = [u.get("platform", "").lower() for u in urls]
            platform_counts = {}
            for p in platforms:
                platform_counts[p] = platform_counts.get(p, 0) + 1

            # If any platform appears more than once, these are separate audios
            has_duplicate_platforms = any(count > 1 for count in platform_counts.values())

            if not has_duplicate_platforms or len(urls) <= 1:
                # No expansion needed
                expanded.append(version)
                continue

            # Expand each URL into its own audio_version
            print(f"  Expanding CYOA version with {len(urls)} URLs into separate audio_versions")

            for url_info in urls:
                url = url_info.get("url", "")

                # Try to extract a descriptive name from the URL or post body
                version_name = self._extract_cyoa_version_name(url, selftext)

                expanded_version = {
                    "version_name": version_name,
                    "description": version.get("description", ""),
                    "urls": [url_info],
                    "performers": version.get("performers", []),
                    "tags": version.get("tags", []),
                }
                expanded.append(expanded_version)

        return expanded

    def _extract_cyoa_version_name(self, url: str, selftext: str) -> str:
        """Extract a descriptive name for a CYOA audio from its URL or context."""
        import urllib.parse

        # Try to get name from URL path
        parsed = urllib.parse.urlparse(url)
        path_parts = parsed.path.strip("/").split("/")

        if path_parts:
            # Last part is usually the audio identifier
            url_name = path_parts[-1]
            # Convert URL slug to readable name
            url_name = url_name.replace("-", " ").replace("_", " ")
            # Capitalize words
            url_name = " ".join(word.capitalize() for word in url_name.split())
            if url_name and len(url_name) > 3:
                return url_name

        return "CYOA Audio"

    def generate_fallback_naming(self, post_data: dict, audio_versions: list) -> dict:
        """Generates fallback naming when LLM fails."""
        post_id = post_data.get("reddit_data", {}).get("post_id") or post_data.get(
            "post_id"
        )
        title = post_data.get("reddit_data", {}).get("title", "")

        # Simple slug generation
        release_slug = re.sub(r"\[.*?\]", "", title)  # Remove brackets
        release_slug = re.sub(r"[^\w\s]", "", release_slug)  # Remove special chars
        release_slug = release_slug.strip().lower()
        release_slug = re.sub(r"\s+", "_", release_slug)
        release_slug = release_slug[:40]

        audio_files = []
        for index, version in enumerate(audio_versions):
            version_slug = version.get("version_name")
            if version_slug:
                version_slug = version_slug.lower()
                version_slug = re.sub(r"\s+", "_", version_slug)
                version_slug = re.sub(r"[^\w_]", "", version_slug)
            else:
                version_slug = f"version_{index + 1}"

            audio_files.append(
                {
                    "filename": f"{post_id}_{release_slug}_-_{version_slug}.m4a",
                    "version_slug": version_slug,
                    "display_name": version.get("version_name")
                    or f"Version {index + 1}",
                    "detected_tags": [],
                    "audio_urls": [u["url"] for u in version.get("urls", [])],
                    "metadata_file": f"{post_id}_{release_slug}_-_{version_slug}.json",
                }
            )

        return {
            "release_directory": f"{post_id}_{release_slug}",
            "release_slug": release_slug,
            "audio_files": audio_files,
            "structure_type": "multiple_versions"
            if len(audio_versions) > 1
            else "single_version",
        }

    def analyze_post(self, file_path: str | Path) -> dict:
        """Analyzes a single Reddit post file using LLM-based metadata extraction."""
        file_path = Path(file_path)

        try:
            with file_path.open(encoding="utf-8") as f:
                post_data = json.load(f)

            if not post_data.get("reddit_data"):
                raise ValueError("Post data missing required reddit_data")

            reddit_data = post_data["reddit_data"]

            # Handle link posts (is_self=False) that have no selftext but link to audio
            if not reddit_data.get("selftext"):
                if not reddit_data.get("is_self", True) and reddit_data.get("url"):
                    # Create synthetic selftext from the link post URL
                    reddit_data["selftext"] = reddit_data["url"]
                else:
                    raise ValueError(
                        "Post data missing required reddit_data.selftext field"
                    )

            print(f"Analyzing post: {post_data['reddit_data']['title']}")

            # Use LLM for comprehensive metadata extraction
            prompt = self.create_metadata_extraction_prompt(post_data)

            # Adaptive token limit based on number of pre-extracted URLs
            # Each audio_version needs ~200-300 tokens in the response
            url_count = len(getattr(self, "_last_extracted_urls", []))
            if url_count > 20:
                max_tokens = 8000
            elif url_count > 10:
                max_tokens = 4000
            else:
                max_tokens = 2000

            llm_response = self.call_llm(prompt, max_tokens=max_tokens)
            analysis = self.parse_response(llm_response)

            # Ensure performers has count field for compatibility
            if analysis.get("performers"):
                analysis["performers"]["count"] = 1 + len(
                    analysis["performers"].get("additional") or []
                )

            # Generate version naming information
            audio_versions = analysis.get("audio_versions", [])
            print(
                f"Generating version naming for {len(audio_versions)} audio version(s)..."
            )
            version_naming = self.generate_version_naming(post_data, audio_versions)

            # Enhance audio_versions with slug information
            if version_naming and version_naming.get("audio_files"):
                enhanced_versions = []
                for index, version in enumerate(analysis["audio_versions"]):
                    naming_info = (
                        version_naming["audio_files"][index]
                        if index < len(version_naming["audio_files"])
                        else version_naming["audio_files"][0]
                    )
                    enhanced_versions.append(
                        {
                            **version,
                            "slug": naming_info.get("version_slug")
                            or f"version_{index + 1}",
                            "filename": naming_info.get("filename")
                            or f"{post_data.get('post_id')}_audio_{index + 1}.m4a",
                            "metadata_file": naming_info.get("metadata_file")
                            or f"{post_data.get('post_id')}_audio_{index + 1}.json",
                        }
                    )
                analysis["audio_versions"] = enhanced_versions

            # Add version naming metadata
            analysis["version_naming"] = version_naming

            # Detect CYOA structure
            print("Checking for CYOA structure...")
            cyoa_detection = self.detect_cyoa(post_data)
            analysis["cyoa_detection"] = cyoa_detection

            if cyoa_detection.get("is_cyoa"):
                print(
                    f"  CYOA detected ({cyoa_detection.get('confidence')} confidence): "
                    f"{cyoa_detection.get('reason')}"
                )

                # Expand CYOA audio_versions if URLs were incorrectly grouped
                original_count = len(analysis["audio_versions"])
                expanded_versions = self.expand_cyoa_audio_versions(
                    analysis["audio_versions"], post_data
                )

                if len(expanded_versions) > original_count:
                    print(
                        f"  Expanded {original_count} audio_version(s) to "
                        f"{len(expanded_versions)} for CYOA"
                    )
                    analysis["audio_versions"] = expanded_versions

                    # Regenerate version naming for expanded versions
                    print("  Regenerating version naming for expanded CYOA...")
                    version_naming = self.generate_version_naming(
                        post_data, expanded_versions
                    )
                    analysis["version_naming"] = version_naming

                    # Re-enhance audio_versions with new slug information
                    if version_naming and version_naming.get("audio_files"):
                        enhanced_versions = []
                        for index, version in enumerate(expanded_versions):
                            naming_info = (
                                version_naming["audio_files"][index]
                                if index < len(version_naming["audio_files"])
                                else version_naming["audio_files"][0]
                            )
                            enhanced_versions.append(
                                {
                                    **version,
                                    "slug": naming_info.get("version_slug")
                                    or f"version_{index + 1}",
                                    "filename": naming_info.get("filename")
                                    or f"{post_data.get('post_id')}_audio_{index + 1}.m4a",
                                    "metadata_file": naming_info.get("metadata_file")
                                    or f"{post_data.get('post_id')}_audio_{index + 1}.json",
                                }
                            )
                        analysis["audio_versions"] = enhanced_versions

            # Add metadata
            analysis["metadata"] = {
                "post_id": post_data.get("post_id"),
                "username": post_data.get("username"),
                "title": post_data["reddit_data"]["title"],
                "date": post_data.get("date"),
                "reddit_url": post_data.get("reddit_url"),
                "analyzed_at": datetime.now().isoformat(),
                "extraction_method": "llm",
                "model": self.model,
            }

            return analysis
        except Exception as e:
            raise RuntimeError(f"Failed to analyze {file_path}: {e}") from e

    def analyze_directory(
        self, dir_path: str | Path, output_path: str | Path | None = None
    ) -> list:
        """Processes multiple post files in a directory."""
        dir_path = Path(dir_path)
        files = sorted(dir_path.glob("*.json"))

        results = []

        for file in files:
            try:
                print(f"Processing {file.name}...")
                analysis = self.analyze_post(file)
                results.append(analysis)

                # Small delay to avoid overwhelming the LLM
                import time

                time.sleep(2)
            except Exception as e:
                print(f"Error processing {file}: {e}")
                results.append(
                    {
                        "error": str(e),
                        "file": str(file),
                        "analyzed_at": datetime.now().isoformat(),
                    }
                )

        if output_path:
            output_path = Path(output_path)
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Results saved to {output_path}")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Reddit Post Analyzer with LLM-based Metadata Extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python analyze_reddit_post.py aural_data/index/reddit/alekirser/1amzk7q.json
  uv run python analyze_reddit_post.py aural_data/index/reddit/alekirser/ --output results.json
  uv run python analyze_reddit_post.py post.json --model mistral-7b --no-script-resolution
""",
    )
    parser.add_argument("input_path", help="Path to post JSON file or directory")
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for results (JSON). If not specified, outputs to stdout",
    )
    parser.add_argument(
        "--url",
        dest="lm_studio_url",
        help="LM Studio API URL (default: http://localhost:1234/v1/chat/completions)",
    )
    parser.add_argument(
        "--model",
        default="local-model",
        help="Model name (default: local-model)",
    )
    parser.add_argument(
        "--no-script-resolution",
        action="store_true",
        help="Disable script URL resolution",
    )

    args = parser.parse_args()

    input_path = Path(args.input_path)

    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        return 1

    analyzer = EnhancedRedditPostAnalyzer(
        lm_studio_url=args.lm_studio_url,
        model=args.model,
        enable_script_resolution=not args.no_script_resolution,
    )

    try:
        if input_path.is_dir():
            results = analyzer.analyze_directory(input_path, args.output)
        else:
            results = analyzer.analyze_post(input_path)

            if args.output:
                output_path = Path(args.output)
                with output_path.open("w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"Results saved to {output_path}")
            else:
                print(json.dumps(results, indent=2, ensure_ascii=False))

        print("Enhanced analysis complete!")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
