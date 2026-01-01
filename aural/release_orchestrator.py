#!/usr/bin/env python3
"""
Release Orchestrator

Coordinates the entire release extraction workflow:
1. Discovery (Reddit/Patreon posts)
2. Analysis (LLM enrichment)
3. Audio extraction (platform-agnostic)
4. Release aggregation
5. Storage organization

All files are stored directly in data/releases/{performer}/{release_dir}/
"""

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from hotaudio_extractor import HotAudioExtractor
from scriptbin_extractor import ScriptBinExtractor
from soundgasm_extractor import SoundgasmExtractor
from whypit_extractor import WhypitExtractor


@dataclass
class AudioSource:
    """Unified audio source schema."""

    audio: dict = field(default_factory=lambda: {
        "sourceUrl": None,
        "downloadUrl": None,
        "filePath": None,
        "format": None,
        "fileSize": None,
        "checksum": {}
    })
    metadata: dict = field(default_factory=lambda: {
        "title": None,
        "author": None,
        "description": None,
        "tags": [],
        "duration": None,
        "uploadDate": None,
        "extractedAt": None,
        "platform": {"name": None, "extractorVersion": None}
    })
    platform_data: dict = field(default_factory=dict)
    backup_files: dict = field(default_factory=lambda: {"html": None, "metadata": None})
    version_info: dict | None = None
    alternate_sources: list | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "audio": self.audio,
            "metadata": self.metadata,
            "platformData": self.platform_data,
            "backupFiles": self.backup_files,
        }
        if self.version_info:
            result["versionInfo"] = self.version_info
        if self.alternate_sources:
            result["alternateSources"] = self.alternate_sources
        return result


@dataclass
class Release:
    """Release - aggregates multiple audio sources and enrichment data."""

    id: str = ""
    title: str | None = None
    primary_performer: str | None = None
    additional_performers: list = field(default_factory=list)
    script_author: str | None = None
    release_date: str | None = None
    enrichment_data: dict = field(default_factory=lambda: {
        "reddit": None,
        "patreon": None,
        "llmAnalysis": None,
        "gwasi": None
    })
    audio_sources: list = field(default_factory=list)
    script: dict | None = None
    artwork: list = field(default_factory=list)
    aggregated_at: str = ""
    version: str = "1.0"

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
        if not self.aggregated_at:
            self.aggregated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _generate_id(self) -> str:
        """Generate a unique ID for the release."""
        data = f"{self.title}-{self.primary_performer}-{datetime.now().timestamp()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def add_audio_source(self, audio_source: AudioSource | dict):
        """Add an audio source to the release."""
        if isinstance(audio_source, AudioSource):
            self.audio_sources.append(audio_source.to_dict())
        else:
            self.audio_sources.append(audio_source)

    def get_audio_sources_by_platform(self, platform_name: str) -> list:
        """Get audio sources by platform."""
        return [
            source for source in self.audio_sources
            if source.get("metadata", {}).get("platform", {}).get("name") == platform_name
        ]

    def has_all_variants(self, expected_variants: list[str] | None = None) -> bool:
        """Check if release has all expected audio variants."""
        if expected_variants is None:
            expected_variants = ["M4F", "F4M"]

        found_variants = set()

        for source in self.audio_sources:
            metadata = source.get("metadata", {})
            all_text = " ".join([
                metadata.get("title") or "",
                metadata.get("description") or "",
                *metadata.get("tags", [])
            ]).upper()

            for variant in expected_variants:
                if variant in all_text:
                    found_variants.add(variant)

        return all(v in found_variants for v in expected_variants)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "primaryPerformer": self.primary_performer,
            "additionalPerformers": self.additional_performers,
            "scriptAuthor": self.script_author,
            "releaseDate": self.release_date,
            "enrichmentData": self.enrichment_data,
            "audioSources": self.audio_sources,
            "script": self.script,
            "artwork": self.artwork,
            "aggregatedAt": self.aggregated_at,
            "version": self.version
        }


class ReleaseOrchestrator:
    """Main orchestrator class for release extraction workflow."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = {
            "dataDir": config.get("dataDir", "data"),
            "validateExtractions": config.get("validateExtractions", True),
            **config
        }

        # Platform extractors registry
        self.extractors: dict[str, dict] = {}

        # Initialize default extractors
        self.register_extractor("soundgasm", {
            "pattern": re.compile(r"soundgasm\.net", re.IGNORECASE),
            "class": SoundgasmExtractor
        })

        self.register_extractor("whypit", {
            "pattern": re.compile(r"whyp\.it", re.IGNORECASE),
            "class": WhypitExtractor
        })

        self.register_extractor("hotaudio", {
            "pattern": re.compile(r"hotaudio\.net", re.IGNORECASE),
            "class": HotAudioExtractor
        })

        # Track active extractor instances for cleanup
        self.active_extractors: dict[str, Any] = {}

        # Platform priority for selecting preferred audio source
        self.platform_priority = ["soundgasm", "whypit", "hotaudio"]

    def register_extractor(self, platform: str, config: dict):
        """Register a platform extractor."""
        self.extractors[platform] = config

    def get_extractor_for_url(self, url: str) -> tuple[str, dict] | None:
        """Get appropriate extractor for a URL."""
        for platform, config in self.extractors.items():
            if config["pattern"].search(url):
                return platform, config
        return None

    def sort_urls_by_priority(self, urls: list[dict]) -> list[dict]:
        """Sort URLs by platform priority."""
        if not urls:
            return []

        def get_priority(url_info: dict) -> int:
            platform = (url_info.get("platform") or "").lower()
            try:
                return self.platform_priority.index(platform)
            except ValueError:
                return 99  # Unknown platforms get lowest priority

        return sorted(urls, key=get_priority)

    def extract_audio(self, url: str, target_path: dict) -> AudioSource:
        """
        Extract audio from URL directly to target path.

        Args:
            url: Audio URL to extract
            target_path: Dict with 'dir' and 'basename' keys

        Returns:
            AudioSource with extraction results
        """
        # Find appropriate extractor
        extractor_info = self.get_extractor_for_url(url)
        if not extractor_info:
            raise ValueError(f"No extractor found for URL: {url}")

        platform, config = extractor_info
        print(f"🔧 Using {platform} extractor for: {url}")

        try:
            # Get or create extractor instance
            extractor = self.active_extractors.get(platform)
            if not extractor:
                extractor_class = config["class"]
                extractor = extractor_class({"request_delay": 2.0})

                if hasattr(extractor, "setup_playwright"):
                    extractor.setup_playwright()

                self.active_extractors[platform] = extractor

            # Extract audio directly to target path
            result = extractor.extract(url, target_path)

            # Transform to AudioSource
            audio_source = self.normalize_extractor_result(result, platform)

            return audio_source

        except Exception as error:
            print(f"❌ Extraction failed for {url}: {error}")
            raise

    def cleanup(self):
        """Cleanup all active extractors."""
        for platform, extractor in self.active_extractors.items():
            if hasattr(extractor, "close_browser"):
                extractor.close_browser()
                print(f"🔒 Closed {platform} extractor")
        self.active_extractors.clear()

    def normalize_extractor_result(self, result: dict, platform: str) -> AudioSource:
        """Normalize extractor results to unified schema."""
        # If already an AudioSource, return as-is
        if isinstance(result, AudioSource):
            return result

        # Transform from extractor format to AudioSource schema
        audio = result.get("audio", {})
        metadata = result.get("metadata", {})

        audio_source = AudioSource(
            audio={
                "sourceUrl": audio.get("sourceUrl") or result.get("sourceUrl") or result.get("url"),
                "downloadUrl": audio.get("downloadUrl") or result.get("audioUrl"),
                "filePath": audio.get("filePath") or result.get("filePath"),
                "format": audio.get("format") or result.get("format", "m4a"),
                "fileSize": audio.get("fileSize") or result.get("fileSize"),
                "checksum": audio.get("checksum") or result.get("checksum", {}),
            },
            metadata={
                "title": metadata.get("title") or result.get("title"),
                "author": metadata.get("author") or result.get("author") or result.get("user"),
                "description": metadata.get("description") or result.get("description", ""),
                "tags": metadata.get("tags") or result.get("tags", []),
                "duration": metadata.get("duration") or result.get("duration"),
                "uploadDate": metadata.get("uploadDate") or result.get("uploadDate"),
                "extractedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "platform": {
                    "name": platform,
                    "extractorVersion": metadata.get("platform", {}).get("extractorVersion", "1.0")
                }
            },
            platform_data=result.get("platformData", {}),
            backup_files={
                "html": result.get("backupFiles", {}).get("html") or result.get("htmlBackup"),
                "metadata": result.get("backupFiles", {}).get("metadata") or result.get("metadataFile")
            }
        )

        return audio_source

    def process_post(self, post: dict, llm_analysis: dict | None = None) -> Release:
        """Process a Reddit/Patreon post into a release."""
        print(f"🎯 Processing post: {post.get('title', 'Unknown')}")

        # Determine target directory structure first
        data_dir = Path(self.config["dataDir"])

        if llm_analysis and llm_analysis.get("version_naming", {}).get("release_directory"):
            release_dir = data_dir / "releases" / post.get("author", "unknown") / llm_analysis["version_naming"]["release_directory"]
        else:
            # Generate a stable ID based on post ID for fallback
            stable_id = post.get("id") or hashlib.sha256(
                f"{post.get('title', '')}-{post.get('author', '')}".encode()
            ).hexdigest()[:16]
            release_dir = data_dir / "releases" / post.get("author", "unknown") / stable_id

        # Check if release already exists
        release_path = release_dir / "release.json"
        if release_path.exists():
            try:
                existing_data = json.loads(release_path.read_text(encoding="utf-8"))
                print(f"⏭️  Release already exists: {release_dir}")
                print(f"   Audio sources: {len(existing_data.get('audioSources', []))}")

                # Return a Release object with the existing data
                release = Release(
                    id=existing_data.get("id", ""),
                    title=existing_data.get("title"),
                    primary_performer=existing_data.get("primaryPerformer"),
                    additional_performers=existing_data.get("additionalPerformers", []),
                    script_author=existing_data.get("scriptAuthor"),
                    release_date=existing_data.get("releaseDate"),
                    enrichment_data=existing_data.get("enrichmentData", {}),
                    audio_sources=existing_data.get("audioSources", []),
                    script=existing_data.get("script"),
                    artwork=existing_data.get("artwork", []),
                    aggregated_at=existing_data.get("aggregatedAt", ""),
                    version=existing_data.get("version", "1.0")
                )
                return release
            except json.JSONDecodeError:
                pass  # Proceed with creation

        # Create release object
        release = Release(
            title=post.get("title"),
            primary_performer=post.get("author"),
            release_date=post.get("created_utc"),
            enrichment_data={
                "reddit": post,
                "patreon": None,
                "llmAnalysis": llm_analysis,
                "gwasi": None
            }
        )

        release_dir.mkdir(parents=True, exist_ok=True)

        # Extract audio URLs from post and analysis
        audio_urls = self.extract_audio_urls(post, llm_analysis)
        print(f"🔗 Found {len(audio_urls)} unique audio URL{'s' if len(audio_urls) != 1 else ''}")

        # Process each audio version with proper naming
        if llm_analysis and llm_analysis.get("audio_versions"):
            for i, audio_version in enumerate(llm_analysis["audio_versions"]):
                if audio_version.get("urls"):
                    # Sort URLs by platform priority
                    sorted_urls = self.sort_urls_by_priority(audio_version["urls"])
                    audio_source = None
                    used_url = None

                    # Determine basename for this version
                    if audio_version.get("filename"):
                        # Remove extension
                        basename = re.sub(r"\.[^.]+$", "", audio_version["filename"])
                    else:
                        release_slug = llm_analysis.get("version_naming", {}).get("release_slug") or release.id
                        basename = f"{release_slug}_{audio_version.get('slug', i)}"

                    target_path = {"dir": str(release_dir), "basename": basename}

                    # Try each platform in priority order with retries
                    for url_info in sorted_urls:
                        max_retries = 3
                        retry_count = 0

                        while retry_count < max_retries:
                            try:
                                version_name = audio_version.get("version_name") or f"Version {i + 1}"
                                print(f"📥 Extracting: {url_info['url']} ({version_name})")
                                audio_source = self.extract_audio(url_info["url"], target_path)
                                used_url = url_info
                                break  # Success, exit retry loop
                            except Exception as error:
                                retry_count += 1
                                if retry_count < max_retries:
                                    print(f"⚠️  Retry {retry_count}/{max_retries} for {url_info.get('platform', 'unknown')}: {error}")
                                else:
                                    print(f"❌ Failed {url_info.get('platform', 'unknown')} after {max_retries} retries: {error}")

                        if audio_source:
                            break  # Success, don't try other platforms

                    if audio_source:
                        # Add version-specific metadata
                        audio_source.version_info = {
                            "slug": audio_version.get("slug"),
                            "version_name": audio_version.get("version_name"),
                            "description": audio_version.get("description"),
                            "performers": audio_version.get("performers", []),
                            "tags": audio_version.get("tags", [])
                        }

                        # Store alternate sources
                        audio_source.alternate_sources = [
                            {"platform": u.get("platform"), "url": u.get("url")}
                            for u in sorted_urls
                            if u.get("url") != used_url.get("url")
                        ]

                        release.add_audio_source(audio_source)
                        print(f"✅ Added audio source: {audio_version.get('version_name', 'Version')} from {audio_source.metadata['platform']['name']}")
                    else:
                        print(f"❌ All platforms failed for {audio_version.get('version_name') or f'Version {i + 1}'}")
        else:
            # Fallback: process URLs directly (old method)
            for i, url in enumerate(audio_urls):
                try:
                    print(f"📥 Extracting: {url}")

                    basename = f"{release.id}_audio_{i}"
                    target_path = {"dir": str(release_dir), "basename": basename}
                    audio_source = self.extract_audio(url, target_path)

                    release.add_audio_source(audio_source)
                    print(f"✅ Added audio source from {audio_source.metadata['platform']['name']}")
                except Exception as error:
                    print(f"❌ Failed to extract {url}: {error}")

        # Fail early if no audio sources were downloaded
        if not release.audio_sources:
            self.cleanup()
            raise ValueError("No audio sources could be downloaded - all extractions failed")

        # Extract script if available
        if llm_analysis and llm_analysis.get("script", {}).get("url"):
            try:
                release.script = self.extract_script(llm_analysis["script"], release_dir)
            except Exception as error:
                print(f"❌ Failed to extract script: {error}")

        # Save release
        self.save_release(release)

        # Cleanup extractors
        self.cleanup()

        print(f"✅ Release processed: {release.id}")
        return release

    def extract_audio_urls(self, post: dict, llm_analysis: dict | None = None) -> list[str]:
        """Extract audio URLs from post and analysis."""
        urls = set()

        # From post content
        url_regex = re.compile(
            r"https?://(?:www\.)?(soundgasm\.net|whyp\.it|hotaudio\.net)[^\s\]]+",
            re.IGNORECASE
        )
        post_content = post.get("content") or post.get("selftext") or ""
        matches = url_regex.findall(post_content)
        for match in matches:
            # The regex captures just the domain, we need the full URL
            full_matches = re.findall(
                rf"https?://(?:www\.)?{re.escape(match)}[^\s\]]+",
                post_content,
                re.IGNORECASE
            )
            urls.update(full_matches)

        # Better approach: find all URLs directly
        all_urls = re.findall(
            r"https?://(?:www\.)?(?:soundgasm\.net|whyp\.it|hotaudio\.net)[^\s\]\)]+",
            post_content,
            re.IGNORECASE
        )
        urls.update(all_urls)

        # From LLM analysis
        if llm_analysis and llm_analysis.get("audio_versions"):
            for version in llm_analysis["audio_versions"]:
                if version.get("urls"):
                    for url_info in version["urls"]:
                        urls.add(url_info.get("url", ""))

        # Remove empty strings
        urls.discard("")

        return list(urls)

    def extract_script(self, script_info: dict, release_dir: Path) -> dict:
        """
        Extract script from URL and save to release directory.

        Args:
            script_info: Script info object with url, author, fillType
            release_dir: Directory to save the script

        Returns:
            Script data including content and metadata
        """
        url = script_info.get("url", "")
        author = script_info.get("author")
        fill_type = script_info.get("fillType")

        print(f"📝 Extracting script: {url}")

        try:
            # Resolve the URL (handles Reddit share URLs, redirects, etc.)
            resolved_url = self.resolve_script_url(url)
            print(f"   Resolved URL: {resolved_url}")

            script_content = None
            html_content = None
            script_metadata = {
                "originalUrl": url,
                "resolvedUrl": resolved_url,
                "author": author,
                "fillType": fill_type,
                "extractedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }

            if "scriptbin.works" in resolved_url:
                result = self.extract_scriptbin_script(resolved_url)
                script_content = result.get("content")
                html_content = result.get("htmlContent")
                script_metadata.update(result.get("metadata", {}))
            elif "reddit.com" in resolved_url:
                result = self.extract_reddit_script(resolved_url)
                script_content = result.get("content")
                html_content = result.get("htmlContent")
                script_metadata.update(result.get("metadata", {}))
            else:
                print(f"⚠️  Unknown script source: {resolved_url}")
                script_metadata["status"] = "unsupported_source"
                return script_metadata

            # Save script if we got content
            if script_content:
                script_path = release_dir / "script.txt"
                script_path.write_text(script_content, encoding="utf-8")
                script_metadata["filePath"] = str(script_path)
                script_metadata["status"] = "downloaded"
                print(f"✅ Script saved: {script_path}")

            # Save HTML backup if available
            if html_content:
                html_path = release_dir / "script.html"
                html_path.write_text(html_content, encoding="utf-8")
                script_metadata["htmlFilePath"] = str(html_path)
                print(f"✅ Script HTML saved: {html_path}")

            # Save script metadata
            metadata_path = release_dir / "script_metadata.json"
            metadata_path.write_text(
                json.dumps(script_metadata, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            return script_metadata

        except Exception as error:
            print(f"❌ Script extraction failed: {error}")
            return {
                "originalUrl": url,
                "author": author,
                "fillType": fill_type,
                "status": "failed",
                "error": str(error)
            }

    def resolve_script_url(self, url: str) -> str:
        """Resolve script URLs (handle redirects, share links, etc.)."""
        # Handle Reddit share URLs (format: reddit.com/r/.../s/xxx)
        if "/s/" in url:
            try:
                response = httpx.head(url, follow_redirects=True, timeout=30.0)
                return str(response.url)
            except Exception as error:
                print(f"⚠️  Could not resolve redirect for {url}: {error}")
                return url
        return url

    def extract_scriptbin_script(self, url: str) -> dict:
        """Extract script content from scriptbin.works using ScriptBinExtractor."""
        try:
            # Get or create scriptbin extractor instance
            extractor = self.active_extractors.get("scriptbin")
            if not extractor:
                extractor = ScriptBinExtractor()
                extractor.setup_playwright()
                self.active_extractors["scriptbin"] = extractor

            # Extract script data
            script_data = extractor.get_script_data(url)

            if not script_data or not script_data.get("script_content"):
                return {
                    "content": None,
                    "htmlContent": script_data.get("html_content") if script_data else None,
                    "metadata": {
                        "source": "scriptbin.works",
                        "url": url,
                        "note": "Could not extract script content"
                    }
                }

            # Join the script lines into a single content string
            content = "\n".join(script_data["script_content"])

            return {
                "content": content,
                "htmlContent": script_data.get("html_content"),
                "metadata": {
                    "source": "scriptbin.works",
                    "title": script_data.get("title"),
                    "author": script_data.get("author") or script_data.get("username"),
                    "wordCount": script_data.get("word_count"),
                    "characterCount": script_data.get("character_count"),
                    "performers": script_data.get("performers"),
                    "listeners": script_data.get("listeners"),
                    "tags": script_data.get("tags"),
                    "shortLink": script_data.get("short_link")
                }
            }

        except Exception as error:
            raise ValueError(f"Scriptbin extraction failed: {error}")

    def extract_reddit_script(self, url: str) -> dict:
        """
        Extract script content from Reddit post.
        If the post contains a link to scriptbin.works, follows that link.
        """
        try:
            # Clean URL - remove query params and ensure proper format
            from urllib.parse import urlparse
            parsed = urlparse(url)
            clean_path = parsed.path.rstrip("/")
            json_url = f"https://www.reddit.com{clean_path}.json"

            response = httpx.get(
                json_url,
                headers={
                    "User-Agent": "gwasi-extractor/1.0 (audio archival tool)",
                    "Accept": "application/json"
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                raise ValueError(f"Unexpected content type: {content_type}")

            data = response.json()

            # Reddit API returns array: [post, comments]
            post = data[0]["data"]["children"][0]["data"] if data else None

            if not post:
                raise ValueError("Could not find post data")

            post_content = post.get("selftext", "")
            title = post.get("title", "")
            post_author = post.get("author", "")

            reddit_metadata = {
                "source": "reddit",
                "title": title,
                "postAuthor": post_author,
                "postId": post.get("id"),
                "subreddit": post.get("subreddit"),
                "created": datetime.fromtimestamp(post["created_utc"]).isoformat() if post.get("created_utc") else None,
                "redditPostUrl": url
            }

            # Check if this Reddit post links to scriptbin.works
            scriptbin_match = re.search(
                r"https?://(?:www\.)?scriptbin\.works/[^\s\)\]]+",
                post_content,
                re.IGNORECASE
            )

            if scriptbin_match:
                scriptbin_url = scriptbin_match.group(0)
                print(f"   Found scriptbin.works link: {scriptbin_url}")

                try:
                    scriptbin_result = self.extract_scriptbin_script(scriptbin_url)

                    if scriptbin_result.get("content"):
                        return {
                            "content": scriptbin_result["content"],
                            "htmlContent": scriptbin_result.get("htmlContent"),
                            "metadata": {
                                **reddit_metadata,
                                **scriptbin_result.get("metadata", {}),
                                "source": "scriptbin.works",
                                "scriptbinUrl": scriptbin_url,
                                "redditScriptOfferPost": post_content
                            }
                        }
                except Exception as scriptbin_error:
                    print(f"   ⚠️  Could not extract from scriptbin.works: {scriptbin_error}")

            # No scriptbin link found, or extraction failed - return Reddit post content
            return {
                "content": post_content,
                "metadata": reddit_metadata
            }

        except Exception as error:
            raise ValueError(f"Reddit script extraction failed: {error}")

    def save_release(self, release: Release):
        """Save release to storage using new naming structure."""
        data_dir = Path(self.config["dataDir"])

        # Use version naming if available
        if release.enrichment_data.get("llmAnalysis", {}).get("version_naming", {}).get("release_directory"):
            release_dir = (
                data_dir / "releases" /
                release.primary_performer /
                release.enrichment_data["llmAnalysis"]["version_naming"]["release_directory"]
            )
        else:
            release_dir = data_dir / "releases" / release.primary_performer / release.id

        release_dir.mkdir(parents=True, exist_ok=True)

        # Save release metadata
        release_path = release_dir / "release.json"
        release_path.write_text(
            json.dumps(release.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Update release index
        self.update_release_index(release)

        print(f"💾 Release saved: {release_path}")

    def update_release_index(self, release: Release):
        """Update global release index."""
        data_dir = Path(self.config["dataDir"])
        index_path = data_dir / "releases" / "index.json"

        index = {"releases": []}
        try:
            if index_path.exists():
                index = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            pass

        # Add or update release in index
        index_entry = {
            "id": release.id,
            "title": release.title,
            "primaryPerformer": release.primary_performer,
            "audioSourceCount": len(release.audio_sources),
            "platforms": list(set(
                s.get("metadata", {}).get("platform", {}).get("name")
                for s in release.audio_sources
                if s.get("metadata", {}).get("platform", {}).get("name")
            )),
            "aggregatedAt": release.aggregated_at
        }

        # Find existing entry
        existing_index = next(
            (i for i, r in enumerate(index["releases"]) if r.get("id") == release.id),
            None
        )

        if existing_index is not None:
            index["releases"][existing_index] = index_entry
        else:
            index["releases"].append(index_entry)

        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def validate_extraction(self, audio_source: AudioSource) -> bool:
        """Validate extraction results."""
        if not self.config.get("validateExtractions", True):
            return True

        audio = audio_source.audio
        metadata = audio_source.metadata

        validations = {
            "hasFile": bool(audio.get("filePath")),
            "hasTitle": bool(metadata.get("title")),
            "hasAuthor": bool(metadata.get("author")),
            "hasChecksum": bool(audio.get("checksum", {}).get("sha256")),
            "fileExists": False
        }

        # Check if file exists
        if audio.get("filePath"):
            validations["fileExists"] = Path(audio["filePath"]).exists()

        is_valid = all(validations.values())

        if not is_valid:
            print(f"⚠️  Validation warnings: {validations}")

        return is_valid


def main():
    """CLI entry point for testing."""
    parser = argparse.ArgumentParser(
        description="Release Orchestrator - Process posts into releases"
    )
    parser.add_argument(
        "post_file",
        nargs="?",
        help="JSON file containing post data"
    )
    parser.add_argument(
        "--analysis",
        "-a",
        help="JSON file containing LLM analysis"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="data",
        help="Output directory (default: data)"
    )

    args = parser.parse_args()

    if not args.post_file:
        parser.print_help()
        print("\nExample:")
        print("  uv run python release_orchestrator.py post.json --analysis analysis.json")
        return 1

    try:
        # Load post data
        post_path = Path(args.post_file)
        if not post_path.exists():
            print(f"❌ Post file not found: {args.post_file}")
            return 1

        post = json.loads(post_path.read_text(encoding="utf-8"))

        # Load analysis if provided
        llm_analysis = None
        if args.analysis:
            analysis_path = Path(args.analysis)
            if analysis_path.exists():
                llm_analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

        # Create orchestrator and process
        orchestrator = ReleaseOrchestrator({"dataDir": args.output_dir})
        release = orchestrator.process_post(post, llm_analysis)

        print("\n✅ Processing complete!")
        print(f"📁 Release ID: {release.id}")
        print(f"🎵 Audio sources: {len(release.audio_sources)}")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
