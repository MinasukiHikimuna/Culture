#!/usr/bin/env python3
"""
HotAudio Extractor

Complete extractor that:
1. Captures segment keys via JSON.parse hook (avoids tamper detection)
2. Downloads HAX file directly from CDN
3. Decrypts all segments using tree-based key derivation
4. Outputs playable M4A file

Supports single-page CYOA content with multiple embedded tracks.
Tracks are identified via data-tid attributes on heading elements.

Uses async Playwright API for reliable CDP console message capture.
"""

import argparse
import asyncio
import functools
import hashlib
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from dotenv import load_dotenv
from playwright.async_api import async_playwright


# Make print flush immediately for real-time progress updates
print = functools.partial(print, flush=True)


def sha256_hex(data: bytes) -> str:
    """Calculate SHA256 hash and return as hex string."""
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> bytes:
    """Calculate SHA256 hash and return as bytes."""
    return hashlib.sha256(data).digest()


class KeyTree:
    """Tree-based key derivation for HotAudio segments."""

    def __init__(self, keys: dict[str, str]):
        self.keys: dict[int, bytes] = {}
        for node_str, hex_key in keys.items():
            self.keys[int(node_str)] = bytes.fromhex(hex_key)

    def derive_key(self, node_index: int) -> bytes:
        """Derive key for a given node index using tree traversal."""
        # Find the highest bit position (tree depth)
        n = int(math.log2(node_index))
        depth = -1
        ancestor_key = None

        # Search from root (depth 0) to leaf (depth n) for an ancestor we have
        # At depth d, the ancestor node is node_index >> (n - d)
        for d in range(n + 1):
            ancestor_node = node_index >> (n - d)
            if ancestor_node in self.keys:
                depth = d
                ancestor_key = self.keys[ancestor_node]
                break

        if ancestor_key is None:
            raise ValueError(f"No applicable key available for node {node_index}")

        # Derive from ancestor down to target
        current_key = ancestor_key
        for d in range(depth + 1, n + 1):
            child_node = node_index >> (n - d)
            # Match JS Uint8Array behavior: wrap to single byte (modulo 256)
            current_key = sha256_bytes(current_key + bytes([child_node & 0xFF]))

        return current_key

    def get_segment_key(self, segment_index: int, segment_count: int) -> bytes:
        """Get decryption key for a specific segment."""
        tree_depth = math.ceil(math.log2(segment_count))
        segment_key_base = 1 + (1 << (tree_depth + 1))
        node_index = segment_key_base + segment_index
        return self.derive_key(node_index)


def parse_bencode(buffer: bytes, offset: int = 0) -> tuple:
    """Parse bencode-encoded data."""
    char = chr(buffer[offset])

    if char == "d":
        result = {}
        offset += 1
        while chr(buffer[offset]) != "e":
            key, offset = parse_bencode(buffer, offset)
            value, offset = parse_bencode(buffer, offset)
            if isinstance(key, bytes):
                key = key.decode("utf-8", errors="replace")
            result[key] = value
        return result, offset + 1

    if char == "i":
        offset += 1
        num_str = ""
        while chr(buffer[offset]) != "e":
            num_str += chr(buffer[offset])
            offset += 1
        return int(num_str), offset + 1

    if char.isdigit():
        len_str = char
        offset += 1
        while chr(buffer[offset]) != ":":
            len_str += chr(buffer[offset])
            offset += 1
        offset += 1
        length = int(len_str)
        data = buffer[offset : offset + length]
        return data, offset + length

    if char == "l":
        result = []
        offset += 1
        while chr(buffer[offset]) != "e":
            item, offset = parse_bencode(buffer, offset)
            result.append(item)
        return result, offset + 1

    raise ValueError(f"Unknown bencode type at offset {offset}: {char}")


class HotAudioExtractor:
    """Extract and decrypt audio from HotAudio using async Playwright."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.platform = "hotaudio"
        self.request_delay = config.get("request_delay", 2.0)
        self.last_request_time = 0
        self.browser = None
        self.playwright = None
        self.captured_data: dict = {}

    def setup_playwright(self):
        """
        Setup Playwright browser (no-op for HotAudio since it manages its own browser).

        This method exists for interface compatibility with ReleaseOrchestrator.
        HotAudio extractor launches browser per extraction due to key capture requirements.
        """

    def close_browser(self):
        """Close browser if open (sync wrapper for compatibility)."""
        # Async cleanup is handled in extract method

    def ensure_rate_limit(self):
        """Ensure rate limiting between requests."""
        now = time.time()
        time_since_last_request = now - self.last_request_time

        if time_since_last_request < self.request_delay:
            delay = self.request_delay - time_since_last_request
            print(f"  Rate limiting: waiting {delay * 1000:.0f}ms")
            time.sleep(delay)

        self.last_request_time = time.time()

    def _download_and_parse_hax(self, hax_url: str) -> tuple[bytes, dict, list[dict]]:
        """
        Download HAX file and parse its metadata.

        Returns:
            Tuple of (hax_buffer, metadata_dict, segments_list)
        """
        print("Downloading HAX file from CDN...")
        with httpx.Client() as client:
            response = client.get(hax_url)
            response.raise_for_status()

        hax_buffer = response.content
        print(f"Downloaded {len(hax_buffer) / 1024:.1f} KB")

        # Parse HAX header
        magic = hax_buffer[:4].decode("utf-8")
        if magic != "HAX0":
            raise ValueError(f"Invalid HAX magic: {magic}")

        # Find metadata start (bencode dict starts with 'd')
        meta_start = 16
        while meta_start < 64 and hax_buffer[meta_start] != 0x64:
            meta_start += 1

        metadata, _ = parse_bencode(hax_buffer, meta_start)

        codec = (
            metadata["codec"].decode("utf-8")
            if isinstance(metadata["codec"], bytes)
            else metadata["codec"]
        )
        print(f"  Codec: {codec}")
        print(f"  Duration: {metadata['durationMs'] / 1000:.1f}s")
        print(f"  Segments: {metadata['segmentCount']}")

        # Parse segment table
        segment_data = metadata["segments"]
        segments = []
        for i in range(metadata["segmentCount"]):
            offset = int.from_bytes(
                segment_data[i * 8 : i * 8 + 4], byteorder="little"
            )
            pts = int.from_bytes(
                segment_data[i * 8 + 4 : i * 8 + 8], byteorder="little"
            )
            segments.append({"offset": offset, "pts": pts, "index": i})

        # Calculate segment sizes
        for i in range(len(segments) - 1):
            segments[i]["size"] = segments[i + 1]["offset"] - segments[i]["offset"]
        segments[-1]["size"] = len(hax_buffer) - segments[-1]["offset"]

        return hax_buffer, metadata, segments

    def discover_tracks(self, url: str) -> list[dict]:
        """
        Discover all audio tracks on a HotAudio page.

        Single-page CYOA content embeds multiple tracks identified by data-tid
        attributes on heading elements (h1, h2).

        Args:
            url: HotAudio URL to scan

        Returns:
            List of track dicts with keys: tid, title, tag (h1/h2), index
        """
        return asyncio.run(self._discover_tracks_async(url))

    async def _discover_tracks_async(self, url: str) -> list[dict]:
        """Async implementation of track discovery."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )

        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            page = await context.new_page()

            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Extract all tracks with data-tid attributes
            tracks = await page.evaluate(
                """() => {
                const tracks = [];
                const elements = document.querySelectorAll('[data-tid]');

                elements.forEach((el, index) => {
                    const tid = el.getAttribute('data-tid');
                    const title = el.textContent.trim();
                    const tag = el.tagName.toLowerCase();
                    const parentTag = el.parentElement?.tagName.toLowerCase();

                    tracks.push({
                        tid: tid,
                        title: title,
                        tag: parentTag || tag,
                        index: index
                    });
                });

                return tracks;
            }"""
            )

            # Also get page metadata
            page_meta = await page.evaluate(
                """() => {
                const title = document.querySelector('.text-4xl')?.textContent.trim();
                const byLink = document.querySelector('a[href^="/u/"]');
                const author = byLink?.textContent.trim();

                return { pageTitle: title, author: author };
            }"""
            )

            # Enrich tracks with page metadata
            for track in tracks:
                track["pageTitle"] = page_meta.get("pageTitle")
                track["author"] = page_meta.get("author")
                track["sourceUrl"] = url

            return tracks

        finally:
            await browser.close()
            await playwright.stop()

    def extract_all(self, url: str, target_path: dict) -> dict:
        """
        Extract ALL audio tracks from a HotAudio page (for CYOA content).

        This method discovers all tracks on the page and extracts each one.

        Args:
            url: HotAudio URL to extract
            target_path: Dict with 'dir' key for output directory

        Returns:
            Dict with 'tracks' list containing results for each extracted track
        """
        return asyncio.run(self._extract_all_async(url, target_path))

    async def _extract_all_async(self, url: str, target_path: dict) -> dict:
        """Async implementation of extract_all."""
        output_dir = Path(target_path.get("dir", "./data/hotaudio"))
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check for cached multi-track result
        url_parts = url.rstrip("/").split("/")
        slug = url_parts[-1] or "audio"
        multi_json_path = output_dir / f"{slug}_tracks.json"

        if multi_json_path.exists():
            try:
                cached = json.loads(multi_json_path.read_text(encoding="utf-8"))
                if cached.get("tracks") and len(cached["tracks"]) > 0:
                    print(f"  Using cached multi-track extraction for: {url}")
                    return cached
            except json.JSONDecodeError:
                pass

        print("HotAudio Multi-Track Extractor")
        print("==============================\n")
        print(f"URL: {url}\n")

        # Launch browser
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )

        # Add init script for key capture
        await context.add_init_script(
            script="""
            window.__pendingKeyCaptures = window.__pendingKeyCaptures || [];
            window.__pendingMetadataCaptures = window.__pendingMetadataCaptures || [];
            window.__capturedHaxUrls = window.__capturedHaxUrls || [];
            window.__hookInstalled = true;

            const originalJSONParse = JSON.parse.bind(JSON);
            JSON.parse = function(text) {
                const result = originalJSONParse(text);
                if (result && typeof result === 'object') {
                    if (result.keys && typeof result.keys === 'object' && !result.tracks) {
                        window.__pendingKeyCaptures.push(result.keys);
                    }
                    if (result.tracks && Array.isArray(result.tracks)) {
                        const track = result.tracks[0];
                        window.__pendingMetadataCaptures.push({
                            title: track?.title,
                            artist: track?.artist,
                            duration: track?.duration,
                            pid: result.pid,
                            src: track?.src
                        });
                    }
                }
                return result;
            };
            """
        )

        page = await context.new_page()

        # Capture HAX URLs from network
        captured_hax_urls: list[str] = []

        async def handle_route(route, request):
            req_url = request.url
            is_hax_url = ".hax" in req_url or (
                "/a/" in req_url and "cdn.hotaudio" in req_url
            )
            if is_hax_url and req_url not in captured_hax_urls:
                captured_hax_urls.append(req_url)
            await route.continue_()

        await page.route("**/*", handle_route)

        try:
            # Navigate to page
            print("Navigating to page...")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Discover all tracks
            tracks_info = await page.evaluate(
                """() => {
                const tracks = [];
                const elements = document.querySelectorAll('[data-tid]');

                elements.forEach((el, index) => {
                    const tid = el.getAttribute('data-tid');
                    const title = el.textContent.trim();
                    const parentTag = el.parentElement?.tagName.toLowerCase();

                    tracks.push({
                        tid: tid,
                        title: title,
                        tag: parentTag,
                        index: index,
                        element_selector: `[data-tid="${tid}"]`
                    });
                });

                // Also get page metadata
                const pageTitle = document.querySelector('.text-4xl')?.textContent.trim();
                const byLink = document.querySelector('a[href^="/u/"]');
                const author = byLink?.textContent.trim();

                return { tracks, pageTitle, author };
            }"""
            )

            tracks = tracks_info.get("tracks", [])
            page_title = tracks_info.get("pageTitle", slug)
            author = tracks_info.get("author")

            print(f"Found {len(tracks)} tracks on page:")
            for t in tracks:
                print(f"  [{t['index']}] tid={t['tid']}: {t['title'][:50]}...")

            if len(tracks) <= 1:
                # Single track - use standard extraction
                print("\nSingle track detected, using standard extraction...")
                await browser.close()
                await playwright.stop()
                result = await self._extract_async(url, target_path)
                return {"tracks": [result], "isCYOA": False, "pageTitle": page_title}

            print(f"\nMulti-track CYOA detected! Extracting {len(tracks)} tracks...\n")

            results = []

            for i, track_info in enumerate(tracks):
                tid = track_info["tid"]
                track_title = track_info["title"]
                safe_title = "".join(
                    c if c.isalnum() or c in " -_" else "" for c in track_title
                )[:40].strip()
                track_basename = f"{slug}_{i:02d}_{safe_title}".replace(" ", "-")

                print(f"\n{'=' * 60}")
                print(f"Track {i + 1}/{len(tracks)}: {track_title}")
                print(f"{'=' * 60}")

                # Reset captured data for this track
                self.captured_data = {
                    "hax_url": None,
                    "segment_keys": {},
                    "metadata": None,
                }

                # Clear any pending keys from previous track before switching
                await page.evaluate("() => { window.__pendingKeyCaptures = []; }")

                # Record the current HAX URL count so we can detect new ones
                hax_count_before = len(captured_hax_urls)

                # Click on the track heading to switch to it
                print(f"  Switching to track (tid={tid})...")
                await page.click(f'[data-tid="{tid}"]')
                await page.wait_for_timeout(3000)

                # Check if player is currently playing (need to ensure it starts fresh)
                is_paused = await page.evaluate(
                    """() => {
                    const btn = document.querySelector('#player-playpause');
                    return btn && btn.classList.contains('paused');
                }"""
                )

                # If already playing, pause first to reset state
                if not is_paused:
                    play_button = await page.query_selector("#player-playpause")
                    if play_button:
                        await play_button.click()
                        await page.wait_for_timeout(500)

                # Mute audio before playback
                await page.evaluate('document.querySelector("#player-volume").value = 0')

                # Click play to trigger key exchange for this track
                print("  Starting playback to capture keys...")
                play_button = await page.query_selector("#player-playpause")
                if play_button:
                    await play_button.click()
                    # Wait for key exchange to complete
                    await page.wait_for_timeout(4000)

                # Download HAX file early to get actual segment count
                track_hax_data = None
                actual_segment_count = None
                if len(captured_hax_urls) > hax_count_before:
                    track_hax_url = captured_hax_urls[hax_count_before]
                    self.captured_data["hax_url"] = track_hax_url
                    try:
                        track_hax_data = self._download_and_parse_hax(track_hax_url)
                        actual_segment_count = track_hax_data[1]["segmentCount"]
                        print(f"  Actual segment count: {actual_segment_count}")
                    except Exception as e:
                        print(f"  Warning: Early HAX download failed: {e}")

                # Get track duration as fallback
                track_duration = await page.evaluate(
                    """() => {
                    const progressEl = document.querySelector('#player-progress-text');
                    if (progressEl) {
                        const parts = progressEl.textContent.split('/');
                        if (parts.length === 2) {
                            const [min, sec] = parts[1].trim().split(':').map(Number);
                            return min * 60 + sec;
                        }
                    }
                    return 60;  // Default to 60 seconds if we can't parse
                }"""
                )
                print(f"  Track duration: {int(track_duration // 60)}:{int(track_duration % 60):02d}")

                # Use actual segment count if available, otherwise estimate
                if actual_segment_count:
                    target_segments = actual_segment_count
                else:
                    target_segments = math.ceil(track_duration)

                # Helper to find uncovered segments using tree key derivation
                def find_uncovered_segments(segment_count: int) -> list[int]:
                    tree_depth = math.ceil(math.log2(segment_count))
                    segment_key_base = 1 + (1 << (tree_depth + 1))
                    keys = [int(k) for k in self.captured_data["segment_keys"]]

                    uncovered = []
                    for seg in range(segment_count):
                        node = segment_key_base + seg
                        n = int(math.log2(node))
                        covered = False

                        for d in range(n + 1):
                            ancestor = node >> (n - d)
                            if ancestor in keys:
                                covered = True
                                break

                        if not covered:
                            uncovered.append(seg)
                    return uncovered

                # Set 4x playback speed via speed menu UI hack (HotAudio caps at ~4x)
                await page.evaluate(
                    """() => {
                    const speedOptions = document.querySelectorAll('.speed-option');
                    speedOptions.forEach(opt => {
                        if (opt.textContent.trim() === '2.0x' || opt.textContent.trim() === '4.0x') {
                            opt.textContent = '4.0x';
                            speedOptions.forEach(o => o.classList.remove('bg-slate-600'));
                            opt.classList.add('bg-slate-600');
                            opt.click();
                        }
                    });
                }"""
                )

                # Wait for all segments to be covered by keys
                playback_speed = 4.0
                start_time = time.time()
                last_playback_secs = 0
                slow_progress_count = 0
                reload_attempts = 0
                max_reload_attempts = 3

                def parse_time_info(time_str: str) -> tuple[int, int] | None:
                    """Parse 'MM:SS / MM:SS' format to (current_secs, total_secs)."""
                    if " / " not in time_str:
                        return None
                    try:
                        current_str, total_str = time_str.split(" / ")
                        current_parts = current_str.strip().split(":")
                        total_parts = total_str.strip().split(":")
                        current_secs = int(current_parts[0]) * 60 + int(current_parts[1])
                        total_secs = int(total_parts[0]) * 60 + int(total_parts[1])
                        return current_secs, total_secs
                    except (ValueError, IndexError):
                        return None

                print(f"  Collecting keys at {playback_speed}x speed...")

                while True:
                    await page.wait_for_timeout(10000)  # Check every 10 seconds

                    # Flush any captured keys
                    pending_keys = await page.evaluate(
                        """() => {
                        const pending = window.__pendingKeyCaptures || [];
                        window.__pendingKeyCaptures = [];
                        return pending;
                    }"""
                    )
                    for keys in pending_keys:
                        self.captured_data["segment_keys"].update(keys)

                    # Check coverage
                    current_keys = len(self.captured_data["segment_keys"])
                    uncovered = find_uncovered_segments(target_segments)
                    elapsed = int(time.time() - start_time)

                    # Get current playback position
                    time_info = await page.evaluate(
                        """() => {
                        const progressText = document.querySelector('#player-progress-text');
                        return progressText ? progressText.textContent : 'unknown';
                    }"""
                    )

                    covered_count = target_segments - len(uncovered)
                    print(
                        f"  {elapsed}s: {time_info} - {current_keys} keys, "
                        f"{covered_count}/{target_segments} covered"
                    )

                    if not uncovered:
                        print("  All segments covered!")
                        break

                    # Parse current playback position
                    parsed = parse_time_info(time_info)
                    if parsed:
                        current_secs, total_secs = parsed

                        # Check if playback reached the end
                        if current_secs >= total_secs:
                            print("  Playback ended, waiting 10s for final keys...")
                            await page.wait_for_timeout(10000)
                            # Flush final keys
                            pending_keys = await page.evaluate(
                                """() => {
                                const pending = window.__pendingKeyCaptures || [];
                                window.__pendingKeyCaptures = [];
                                return pending;
                            }"""
                            )
                            for keys in pending_keys:
                                self.captured_data["segment_keys"].update(keys)
                            print("  Playback completed")
                            break

                        # Detect slow progress: at 4x speed, expect ~40s progress per 10s real time
                        # Be lenient: consider it slow if < 10s progress per 10s check (less than 1x)
                        progress = current_secs - last_playback_secs
                        if progress < 10:
                            slow_progress_count += 1
                            if slow_progress_count == 2:
                                # Try clicking play to resume
                                print("  Slow progress detected, attempting to resume...")
                                play_button = await page.query_selector("#player-playpause")
                                if play_button:
                                    await play_button.click()
                                    await page.wait_for_timeout(1000)
                                    await play_button.click()
                            elif slow_progress_count >= 5:
                                # Resume clicks aren't helping, reload the page
                                reload_attempts += 1
                                if reload_attempts >= max_reload_attempts:
                                    print(f"  Extraction failed after {max_reload_attempts} reload attempts")
                                    break
                                print(f"  Reloading page (attempt {reload_attempts}/{max_reload_attempts})...")
                                await page.reload(wait_until="networkidle", timeout=60000)
                                await page.wait_for_selector("#player-playpause", timeout=10000)
                                await page.evaluate('document.querySelector("#player-volume").value = 0')
                                play_button = await page.query_selector("#player-playpause")
                                if play_button:
                                    await play_button.click()
                                    await page.wait_for_timeout(1000)
                                # Re-select the track we were working on
                                selector = ".track-item, .playlist-item, [data-track-index]"
                                track_elements = await page.query_selector_all(selector)
                                if i < len(track_elements):
                                    await track_elements[i].click()
                                    await page.wait_for_timeout(2000)
                                # Set 4x playback speed
                                await page.evaluate(
                                    """() => {
                                    const speedOptions = document.querySelectorAll('.speed-option');
                                    speedOptions.forEach(opt => {
                                        if (opt.textContent.trim() === '2.0x' || opt.textContent.trim() === '4.0x') {
                                            opt.textContent = '4.0x';
                                            speedOptions.forEach(o => o.classList.remove('bg-slate-600'));
                                            opt.classList.add('bg-slate-600');
                                            opt.click();
                                        }
                                    });
                                }"""
                                )
                                slow_progress_count = 0
                                # Don't update last_playback_secs - keep tracking from before reload
                                continue
                        else:
                            slow_progress_count = 0
                        last_playback_secs = current_secs

                # Final key flush
                pending_keys = await page.evaluate(
                    """() => {
                    const pending = window.__pendingKeyCaptures || [];
                    window.__pendingKeyCaptures = [];
                    return pending;
                }"""
                )
                for keys in pending_keys:
                    self.captured_data["segment_keys"].update(keys)

                final_uncovered = find_uncovered_segments(target_segments)
                covered_count = target_segments - len(final_uncovered)
                print(f"  Captured {len(self.captured_data['segment_keys'])} keys")
                print(f"  Coverage: {covered_count}/{target_segments} segments")

                # Get the current HAX URL - find the one that was loaded for this track
                # Look for new HAX URLs captured after we switched to this track
                if len(captured_hax_urls) > hax_count_before:
                    # Use the first new HAX URL (the one loaded when we switched tracks)
                    self.captured_data["hax_url"] = captured_hax_urls[hax_count_before]
                elif captured_hax_urls:
                    self.captured_data["hax_url"] = captured_hax_urls[-1]

                if self.captured_data["hax_url"]:
                    print(f"  HAX URL: {self.captured_data['hax_url'][:60]}...")

                # Get current track metadata
                track_meta = await page.evaluate(
                    """() => {
                    const titleEl = document.querySelector('#player-title');
                    const progressEl = document.querySelector('#player-progress-text');
                    let duration = null;
                    if (progressEl) {
                        const parts = progressEl.textContent.split('/');
                        if (parts.length === 2) {
                            const [min, sec] = parts[1].trim().split(':').map(Number);
                            duration = min * 60 + sec;
                        }
                    }
                    return {
                        title: titleEl?.textContent.trim(),
                        duration: duration
                    };
                }"""
                )
                self.captured_data["metadata"] = track_meta

                if not self.captured_data["hax_url"]:
                    print(f"  ERROR: No HAX URL captured for track {i}")
                    results.append({"error": "No HAX URL", "track": track_info})
                    continue

                if not self.captured_data["segment_keys"]:
                    print(f"  ERROR: No keys captured for track {i}")
                    results.append({"error": "No keys", "track": track_info})
                    continue

                # Download and decrypt this track
                try:
                    track_result = await self._download_and_decrypt_track(
                        output_dir, track_basename, url, track_info, track_hax_data
                    )
                    track_result["trackIndex"] = i
                    track_result["trackTitle"] = track_title
                    track_result["tid"] = tid
                    results.append(track_result)
                    print(f"  ✓ Track {i + 1} extracted successfully")
                except Exception as e:
                    print(f"  ERROR extracting track {i}: {e}")
                    results.append({"error": str(e), "track": track_info})

            # Build final result
            final_result = {
                "isCYOA": True,
                "pageTitle": page_title,
                "author": author,
                "sourceUrl": url,
                "trackCount": len(tracks),
                "extractedCount": sum(1 for r in results if "error" not in r),
                "tracks": results,
                "extractedAt": datetime.now(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
            }

            # Save multi-track metadata
            multi_json_path.write_text(
                json.dumps(final_result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            print(f"\n{'=' * 60}")
            print("Multi-Track Extraction Complete")
            print(f"{'=' * 60}")
            print(f"Total tracks: {len(tracks)}")
            print(f"Successfully extracted: {final_result['extractedCount']}")
            print(f"Metadata saved: {multi_json_path}")

            return final_result

        finally:
            await browser.close()
            await playwright.stop()

    async def _download_and_decrypt_track(
        self,
        output_dir: Path,
        basename: str,
        source_url: str,
        track_info: dict,
        hax_data: tuple[bytes, dict, list[dict]] | None = None,
    ) -> dict:
        """Download and decrypt a single track using captured data.

        Args:
            output_dir: Directory to save output files
            basename: Base filename for output
            source_url: Original source URL
            track_info: Track metadata
            hax_data: Optional pre-downloaded (hax_buffer, metadata, segments) tuple
        """
        segment_keys = self.captured_data["segment_keys"]

        # Use pre-downloaded data or download now
        if hax_data:
            hax_buffer, metadata, segments = hax_data
        else:
            hax_buffer, metadata, segments = self._download_and_parse_hax(
                self.captured_data["hax_url"]
            )

        codec = (
            metadata["codec"].decode("utf-8")
            if isinstance(metadata["codec"], bytes)
            else metadata["codec"]
        )

        # Decrypt segments
        print(f"  Decrypting {len(segments)} segments...")
        key_tree = KeyTree(segment_keys)
        decrypted_segments = []

        for i, seg in enumerate(segments):
            if seg["size"] == 0:
                continue
            try:
                seg_key = key_tree.get_segment_key(i, metadata["segmentCount"])
                ciphertext = hax_buffer[seg["offset"] : seg["offset"] + seg["size"]]
                nonce = bytes(12)
                cipher = ChaCha20Poly1305(seg_key)
                decrypted = cipher.decrypt(nonce, ciphertext, None)
                decrypted_segments.append(decrypted)
            except Exception as e:
                print(f"  Warning: Segment {i} failed: {e}")
                break

        total_segments = len(segments)
        print(f"  Decrypted {len(decrypted_segments)}/{total_segments} segments")

        # Require 100% segment decryption - partial extractions are failures
        if len(decrypted_segments) < total_segments:
            print(
                f"  ERROR: Track extraction incomplete "
                f"({len(decrypted_segments)}/{total_segments} segments). "
                f"Missing {total_segments - len(decrypted_segments)} segments."
            )
            return {
                "success": False,
                "error": f"Incomplete extraction: {len(decrypted_segments)}/{total_segments} segments",
                "platformData": {
                    "segmentCount": total_segments,
                    "decryptedSegments": len(decrypted_segments),
                },
            }

        # Save audio file
        output_path = output_dir / f"{basename}.m4a"
        full_audio = b"".join(decrypted_segments)
        output_path.write_bytes(full_audio)

        # Save track metadata
        json_path = output_dir / f"{basename}.json"
        track_result = {
            "audio": {
                "sourceUrl": source_url,
                "downloadUrl": self.captured_data["hax_url"],
                "filePath": str(output_path),
                "format": "m4a",
                "fileSize": len(full_audio),
                "checksum": {"sha256": sha256_hex(full_audio)},
            },
            "metadata": {
                "title": track_info.get("title") or basename,
                "author": self.captured_data.get("metadata", {}).get("artist"),
                "duration": metadata["durationMs"] / 1000,
                "platform": {"name": "hotaudio", "url": "https://hotaudio.net"},
            },
            "platformData": {
                "codec": codec,
                "segmentCount": total_segments,
                "decryptedSegments": len(decrypted_segments),
                "tid": track_info.get("tid"),
            },
            "backupFiles": {"metadata": str(json_path)},
            "success": True,
        }

        json_path.write_text(
            json.dumps(track_result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print(f"  Saved: {output_path}")
        return track_result

    def extract(self, url: str, target_path: dict) -> dict:
        """
        Extract content from HotAudio URL (sync wrapper).

        Args:
            url: HotAudio URL to extract
            target_path: Dict with 'dir' and 'basename' keys

        Returns:
            Platform-agnostic metadata dict
        """
        return asyncio.run(self._extract_async(url, target_path))

    async def _extract_async(self, url: str, target_path: dict) -> dict:
        """
        Extract content from HotAudio URL (async implementation).

        Args:
            url: HotAudio URL to extract
            target_path: Dict with 'dir' and 'basename' keys

        Returns:
            Platform-agnostic metadata dict
        """
        self.ensure_rate_limit()

        output_dir, output_name, verify = self._parse_target_path(target_path)
        final_output_name = output_name or self._extract_slug_from_url(url)
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{final_output_name}.json"

        cached = self._check_cache(json_path, url)
        if cached:
            return cached

        self._reset_captured_data()
        verify_data = self._init_verify_data(url, verify)

        print("HotAudio Extractor")
        print("==================\n")
        print(f"URL: {url}\n")

        playwright, browser, _context, page = await self._setup_browser()

        try:
            await self._navigate_and_start_playback(page, url)
            target_segments, duration = await self._determine_segment_count(page)
            await self._collect_keys_during_playback(page, target_segments, duration)
            await self._validate_captured_data(page)
            await self._close_browser(browser, playwright)

            hax_buffer, metadata, segments = self._download_and_parse_hax(
                self.captured_data["hax_url"]
            )
            codec = self._decode_codec(metadata)

            if verify_data:
                self._collect_hax_verification(verify_data, hax_buffer, metadata, codec)

            decrypted_segments = self._decrypt_segments(
                hax_buffer, metadata, segments, verify_data
            )

            if len(decrypted_segments) < len(segments):
                return self._build_failure_result(decrypted_segments, segments)

            full_audio = b"".join(decrypted_segments)
            output_path = output_dir / f"{final_output_name}.m4a"
            output_path.write_bytes(full_audio)

            if verify_data:
                self._collect_output_verification(verify_data, output_path, full_audio)

            result = self._build_success_result(
                url, output_path, json_path, full_audio, metadata, codec,
                decrypted_segments, verify_data
            )
            json_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            self._print_summary(output_path, full_audio, metadata, verify_data)
            return result

        except Exception as error:
            print(f"\nError: {error}")
            raise

        finally:
            await self._cleanup_browser(browser, playwright)

    def _parse_target_path(self, target_path: dict) -> tuple[Path, str | None, bool]:
        """Parse target path options into output directory, name, and verify flag."""
        if "dir" in target_path:
            return (
                Path(target_path["dir"]),
                target_path.get("basename"),
                False,
            )
        return (
            Path(target_path.get("outputDir", "./data/hotaudio")),
            target_path.get("outputName"),
            target_path.get("verify", False),
        )

    def _extract_slug_from_url(self, url: str) -> str:
        """Extract audio slug from URL for output filename."""
        url_parts = url.rstrip("/").split("/")
        return url_parts[-1] or "audio"

    def _check_cache(self, json_path: Path, url: str) -> dict | None:
        """Check if extraction is already cached."""
        if json_path.exists():
            try:
                cached = json.loads(json_path.read_text(encoding="utf-8"))
                print(f"  Using cached extraction for: {url}")
                return cached
            except json.JSONDecodeError:
                pass
        return None

    def _reset_captured_data(self) -> None:
        """Reset captured data for a new extraction."""
        self.captured_data = {
            "hax_url": None,
            "segment_keys": {},
            "metadata": None,
            "segment_count": None,
        }

    def _init_verify_data(self, url: str, verify: bool) -> dict | None:
        """Initialize verification data collector if verify mode is enabled."""
        if not verify:
            return None
        return {
            "url": url,
            "hax": {},
            "metadata": {},
            "tree_keys": {},
            "segments": [],
            "output": {},
        }

    async def _setup_browser(self):
        """Launch browser with key capture hooks installed."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        await context.add_init_script(script=self._get_key_capture_script())
        page = await context.new_page()
        await page.route("**/*", self._create_route_handler())
        return playwright, browser, context, page

    def _get_key_capture_script(self) -> str:
        """Return JavaScript to hook JSON.parse for key capture."""
        return """
            window.__pendingKeyCaptures = window.__pendingKeyCaptures || [];
            window.__pendingMetadataCaptures = window.__pendingMetadataCaptures || [];
            window.__hookInstalled = true;
            window.__jsonParseCallCount = 0;

            const originalJSONParse = JSON.parse.bind(JSON);
            JSON.parse = function(text) {
                window.__jsonParseCallCount = (window.__jsonParseCallCount || 0) + 1;
                const result = originalJSONParse(text);

                if (result && typeof result === 'object') {
                    if (result.keys && typeof result.keys === 'object' && !result.tracks) {
                        window.__pendingKeyCaptures.push(result.keys);
                    }
                    if (result.tracks && Array.isArray(result.tracks)) {
                        const track = result.tracks[0];
                        window.__pendingMetadataCaptures.push({
                            title: track?.title,
                            artist: track?.artist,
                            duration: track?.duration,
                            pid: result.pid
                        });
                    }
                }
                return result;
            };
        """

    def _create_route_handler(self):
        """Create route handler to capture HAX URL from network requests."""
        async def handle_route(route, request):
            req_url = request.url
            is_hax_url = ".hax" in req_url or (
                "/a/" in req_url and "cdn.hotaudio" in req_url
            )
            if is_hax_url and self.captured_data["hax_url"] != req_url:
                self.captured_data["hax_url"] = req_url
                print(f"Captured HAX URL: {req_url[:60]}...")
            await route.continue_()
        return handle_route

    async def _navigate_and_start_playback(self, page, url: str) -> None:
        """Navigate to page and start audio playback."""
        print("Navigating to page...")
        await page.goto(url, wait_until="networkidle", timeout=60000)

        hook_status = await page.evaluate(
            """() => ({
                hookInstalled: window.__hookInstalled,
                jsonParseCallCount: window.__jsonParseCallCount,
                pendingKeys: (window.__pendingKeyCaptures || []).length
            })"""
        )
        print(f"Hook status: {hook_status}")

        await self._flush_captured_keys(page)
        await self._flush_captured_metadata(page)

        try:
            await page.wait_for_selector("#player-playpause", timeout=10000)
            print("Player found")
        except Exception:
            print("Player not found, continuing...")

        await page.evaluate('document.querySelector("#player-volume").value = 0')

        print("Clicking play to trigger key exchange...")
        play_button = await page.query_selector("#player-playpause")
        if play_button:
            await play_button.click()
            await page.wait_for_timeout(2000)
            await self._set_playback_speed(page, 4.0)
            await self._flush_captured_keys(page)
            await self._flush_captured_metadata(page)

    async def _determine_segment_count(self, page) -> tuple[int, int | None]:
        """Determine target segment count from HAX file or duration estimate."""
        actual_segment_count = None
        if self.captured_data["hax_url"]:
            try:
                _, hax_metadata, _ = self._download_and_parse_hax(
                    self.captured_data["hax_url"]
                )
                actual_segment_count = hax_metadata["segmentCount"]
            except Exception as e:
                print(f"  Warning: Early HAX download failed: {e}")

        duration = await page.evaluate(
            """() => {
            const progressText = document.querySelector('#player-progress-text');
            if (progressText) {
                const parts = progressText.textContent.split('/');
                if (parts.length === 2) {
                    const [min, sec] = parts[1].trim().split(':').map(Number);
                    return min * 60 + sec;
                }
            }
            return null;
        }"""
        )

        if actual_segment_count:
            target_segments = actual_segment_count
            print(f"Using actual segment count: {target_segments}")
        elif duration:
            target_segments = math.ceil(duration)
            print(f"Using estimated segment count: {target_segments}")
        else:
            target_segments = 200

        if duration:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            print(f"Total duration: {minutes}:{seconds:02d}")

        print(f"Collecting keys for {target_segments} segments...")
        return target_segments, duration

    async def _collect_keys_during_playback(
        self, page, target_segments: int, duration: int | None
    ) -> None:
        """Play audio at 4x speed and collect encryption keys."""
        playback_speed = 4.0
        print(f"  Letting audio play at {playback_speed}x speed...")
        if duration:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            print(f"  Audio duration: {minutes}:{seconds:02d}")

        play_button = await page.query_selector("#player-playpause")
        if play_button:
            await play_button.click()
            await page.wait_for_timeout(1000)
            await self._set_playback_speed(page, playback_speed)

        start_time = time.time()
        last_playback_secs = 0
        slow_progress_count = 0
        reload_attempts = 0
        max_reload_attempts = 3

        while True:
            await page.wait_for_timeout(10000)
            await self._flush_captured_keys(page)

            current_keys = len(self.captured_data["segment_keys"])
            uncovered = self._find_uncovered_segments(target_segments)
            elapsed = int(time.time() - start_time)

            time_info = await page.evaluate(
                """() => {
                const progressText = document.querySelector('#player-progress-text');
                return progressText ? progressText.textContent : 'unknown';
            }"""
            )

            covered_count = target_segments - len(uncovered)
            print(
                f"  {elapsed}s: {time_info} - {current_keys} keys, "
                f"{covered_count}/{target_segments} covered"
            )

            if not uncovered:
                print("  All segments covered!")
                break

            parsed = self._parse_time_info(time_info)
            if parsed:
                current_secs, total_secs = parsed

                if current_secs >= total_secs:
                    print("  Playback ended, waiting 10s for final keys...")
                    await page.wait_for_timeout(10000)
                    await self._flush_captured_keys(page)
                    print("  Playback completed")
                    break

                progress = current_secs - last_playback_secs
                if progress < 10:
                    slow_progress_count += 1
                    should_break = await self._handle_slow_progress(
                        page, slow_progress_count, reload_attempts,
                        max_reload_attempts, playback_speed
                    )
                    if should_break is True:
                        break
                    if should_break == "reloaded":
                        reload_attempts += 1
                        slow_progress_count = 0
                        continue
                else:
                    slow_progress_count = 0
                last_playback_secs = current_secs

        final_uncovered = self._find_uncovered_segments(target_segments)
        print(f"Collected {len(self.captured_data['segment_keys'])} tree node keys")
        covered_count = target_segments - len(final_uncovered)
        print(f"Coverage: {covered_count}/{target_segments} segments")

        await self._flush_captured_keys(page)
        await self._flush_captured_metadata(page)

    async def _handle_slow_progress(
        self, page, slow_progress_count: int, reload_attempts: int,
        max_reload_attempts: int, playback_speed: float
    ) -> bool | str | None:
        """Handle slow playback progress with resume attempts and page reloads."""
        if slow_progress_count == 2:
            print("  Slow progress detected, attempting to resume...")
            play_button = await page.query_selector("#player-playpause")
            if play_button:
                await play_button.click()
                await page.wait_for_timeout(1000)
                await play_button.click()
        elif slow_progress_count >= 5:
            if reload_attempts >= max_reload_attempts:
                print(f"  Extraction failed after {max_reload_attempts} reload attempts")
                return True
            print(f"  Reloading page (attempt {reload_attempts + 1}/{max_reload_attempts})...")
            await page.reload(wait_until="networkidle", timeout=60000)
            await page.wait_for_selector("#player-playpause", timeout=10000)
            await page.evaluate('document.querySelector("#player-volume").value = 0')
            play_button = await page.query_selector("#player-playpause")
            if play_button:
                await play_button.click()
                await page.wait_for_timeout(1000)
                await self._set_playback_speed(page, playback_speed)
            return "reloaded"
        return None

    def _find_uncovered_segments(self, segment_count: int) -> list[int]:
        """Find segments not covered by captured keys."""
        tree_depth = math.ceil(math.log2(segment_count))
        segment_key_base = 1 + (1 << (tree_depth + 1))
        keys = [int(k) for k in self.captured_data["segment_keys"]]

        uncovered = []
        for seg in range(segment_count):
            node = segment_key_base + seg
            n = int(math.log2(node))
            covered = False
            for d in range(n + 1):
                ancestor = node >> (n - d)
                if ancestor in keys:
                    covered = True
                    break
            if not covered:
                uncovered.append(seg)
        return uncovered

    def _parse_time_info(self, time_str: str) -> tuple[int, int] | None:
        """Parse 'MM:SS / MM:SS' format to (current_secs, total_secs)."""
        if " / " not in time_str:
            return None
        try:
            current_str, total_str = time_str.split(" / ")
            current_parts = current_str.strip().split(":")
            total_parts = total_str.strip().split(":")
            current_secs = int(current_parts[0]) * 60 + int(current_parts[1])
            total_secs = int(total_parts[0]) * 60 + int(total_parts[1])
            return current_secs, total_secs
        except (ValueError, IndexError):
            return None

    async def _flush_captured_keys(self, page) -> None:
        """Flush any keys stored in window.__pendingKeyCaptures."""
        try:
            pending = await page.evaluate(
                """() => {
                const pending = window.__pendingKeyCaptures || [];
                window.__pendingKeyCaptures = [];
                return pending;
            }"""
            )
            for keys in pending:
                new_keys = [
                    k for k in keys if k not in self.captured_data["segment_keys"]
                ]
                self.captured_data["segment_keys"].update(keys)
                if new_keys:
                    key_nums = sorted([int(k) for k in new_keys])
                    key_preview = ",".join(str(k) for k in key_nums[:5])
                    if len(key_nums) > 5:
                        key_preview += "..."
                    total = len(self.captured_data["segment_keys"])
                    print(
                        f"Captured {len(new_keys)} new tree node keys: "
                        f"{key_preview} (total: {total})"
                    )
        except Exception:
            pass

    async def _flush_captured_metadata(self, page) -> None:
        """Flush any metadata stored in window.__pendingMetadataCaptures."""
        try:
            pending = await page.evaluate(
                """() => {
                const pending = window.__pendingMetadataCaptures || [];
                window.__pendingMetadataCaptures = [];
                return pending;
            }"""
            )
            for metadata in pending:
                if metadata:
                    self.captured_data["metadata"] = metadata
                    print(f"Captured metadata: {metadata.get('title', 'untitled')}")
        except Exception:
            pass

    async def _set_playback_speed(self, page, speed: float = 4.0) -> bool:
        """Set audio playback speed via HotAudio's speed menu."""
        try:
            result = await page.evaluate(
                f"""() => {{
                const speedOptions = document.querySelectorAll('.speed-option');
                let clicked = false;
                speedOptions.forEach(opt => {{
                    if (opt.textContent.trim() === '2.0x' || opt.textContent.trim() === '4.0x') {{
                        opt.textContent = '{speed}x';
                        speedOptions.forEach(o => o.classList.remove('bg-slate-600'));
                        opt.classList.add('bg-slate-600');
                        opt.click();
                        clicked = true;
                    }}
                }});
                return clicked ? {speed} : null;
            }}"""
            )
            if result:
                print(f"  Set playback speed to {result}x")
                return True
            return False
        except Exception:
            return False

    async def _validate_captured_data(self, page) -> None:
        """Validate that all required data was captured."""
        if not self.captured_data["segment_keys"]:
            raise ValueError("Failed to capture segment keys")

        if not self.captured_data["hax_url"]:
            hax_url = await page.evaluate(
                """() => {
                if (window.__ha_state?.tracks?.[0]?.src) {
                    return window.__ha_state.tracks[0].src;
                }
                return null;
            }"""
            )
            if hax_url:
                self.captured_data["hax_url"] = hax_url
                print(f"Extracted HAX URL from page: {hax_url[:60]}...")
            else:
                raise ValueError("Failed to capture HAX URL")

    async def _close_browser(self, browser, playwright) -> None:
        """Close browser after successful data capture."""
        await browser.close()
        await playwright.stop()

    async def _cleanup_browser(self, browser, playwright) -> None:
        """Cleanup browser resources in finally block."""
        try:
            await browser.close()
        except Exception:
            pass
        try:
            await playwright.stop()
        except Exception:
            pass

    def _decode_codec(self, metadata: dict) -> str:
        """Decode codec from metadata."""
        codec = metadata["codec"]
        if isinstance(codec, bytes):
            return codec.decode("utf-8")
        return codec

    def _collect_hax_verification(
        self, verify_data: dict, hax_buffer: bytes, metadata: dict, codec: str
    ) -> None:
        """Collect HAX file verification data."""
        verify_data["hax"] = {
            "url": self.captured_data["hax_url"],
            "size_bytes": len(hax_buffer),
            "sha256": sha256_hex(hax_buffer),
            "header_hex": hax_buffer[:16].hex(),
        }
        base_key = metadata.get("baseKey", b"")
        orig_hash = metadata.get("origHash")
        verify_data["metadata"] = {
            "base_key_hex": base_key.hex() if base_key else None,
            "codec": codec,
            "duration_ms": metadata["durationMs"],
            "segment_count": metadata["segmentCount"],
            "orig_hash_hex": orig_hash.hex() if orig_hash else None,
        }
        verify_data["tree_keys"] = dict(self.captured_data["segment_keys"])

    def _decrypt_segments(
        self, hax_buffer: bytes, metadata: dict, segments: list[dict],
        verify_data: dict | None
    ) -> list[bytes]:
        """Decrypt all segments using captured keys."""
        print("\nDecrypting segments...")
        key_preview = sorted([int(k) for k in self.captured_data["segment_keys"]])[:20]
        print(f"Key nodes available: {', '.join(str(k) for k in key_preview)}...")

        key_tree = KeyTree(self.captured_data["segment_keys"])
        decrypted_segments = []

        for i, seg in enumerate(segments):
            if seg["size"] == 0:
                continue

            try:
                seg_key = key_tree.get_segment_key(i, metadata["segmentCount"])
                ciphertext = hax_buffer[seg["offset"] : seg["offset"] + seg["size"]]

                nonce = bytes(12)
                cipher = ChaCha20Poly1305(seg_key)
                decrypted = cipher.decrypt(nonce, ciphertext, None)
                decrypted_segments.append(decrypted)

                if verify_data:
                    verify_data["segments"].append({
                        "index": i,
                        "offset": seg["offset"],
                        "size": seg["size"],
                        "encrypted_sha256": sha256_hex(ciphertext),
                        "decrypted_sha256": sha256_hex(decrypted),
                    })

                if i == 0 or i == len(segments) - 1:
                    print(f"  Segment {i}: {len(decrypted)} bytes")
                elif i == 1:
                    print(f"  ... decrypting {len(segments) - 2} more segments ...")

            except Exception as e:
                failed_node = 4097 + i
                print(f"  Segment {i} failed (node {failed_node}): {e}")
                ancestors = [n for n in [1, 2, 4, 8, 16, 32, 64, 128] if n < failed_node]
                print(f"  Looking for ancestors: {', '.join(str(a) for a in ancestors)}")
                key_sample = list(self.captured_data["segment_keys"].keys())[:20]
                print(f"  We have: {', '.join(key_sample)}...")
                break

        total_segments = len(segments)
        print(f"\nDecrypted {len(decrypted_segments)}/{total_segments} segments")
        return decrypted_segments

    def _build_failure_result(
        self, decrypted_segments: list[bytes], segments: list[dict]
    ) -> dict:
        """Build result dict for incomplete extraction."""
        total_segments = len(segments)
        print(
            f"ERROR: Extraction incomplete "
            f"({len(decrypted_segments)}/{total_segments} segments). "
            f"Missing {total_segments - len(decrypted_segments)} segments."
        )
        return {
            "success": False,
            "error": f"Incomplete extraction: {len(decrypted_segments)}/{total_segments} segments",
            "platformData": {
                "segmentCount": total_segments,
                "decryptedSegments": len(decrypted_segments),
            },
        }

    def _collect_output_verification(
        self, verify_data: dict, output_path: Path, full_audio: bytes
    ) -> None:
        """Collect output file verification data."""
        verify_data["output"] = {
            "path": str(output_path),
            "size_bytes": len(full_audio),
            "sha256": sha256_hex(full_audio),
        }

    def _build_success_result(
        self, url: str, output_path: Path, json_path: Path, full_audio: bytes,
        metadata: dict, codec: str, decrypted_segments: list[bytes],
        verify_data: dict | None
    ) -> dict:
        """Build result dict for successful extraction."""
        audio_checksum = sha256_hex(full_audio)
        final_output_name = output_path.stem

        return {
            "audio": {
                "sourceUrl": url,
                "downloadUrl": self.captured_data["hax_url"],
                "filePath": str(output_path),
                "format": "m4a",
                "fileSize": len(full_audio),
                "checksum": {"sha256": audio_checksum},
            },
            "metadata": {
                "title": (
                    (self.captured_data.get("metadata") or {}).get("title")
                    or final_output_name
                ),
                "author": (self.captured_data.get("metadata") or {}).get("artist"),
                "description": "",
                "tags": [],
                "duration": metadata["durationMs"] / 1000,
                "platform": {"name": "hotaudio", "url": "https://hotaudio.net"},
            },
            "platformData": {
                "codec": codec,
                "segmentCount": metadata["segmentCount"],
                "decryptedSegments": len(decrypted_segments),
                "pid": (self.captured_data.get("metadata") or {}).get("pid"),
                "extractedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            "backupFiles": {"metadata": str(json_path)},
            "success": True,
            "outputPath": str(output_path),
            "duration": metadata["durationMs"] / 1000,
            "size": len(full_audio),
            "segments": len(decrypted_segments),
            "verifyData": verify_data,
        }

    def _print_summary(
        self, output_path: Path, full_audio: bytes, metadata: dict,
        verify_data: dict | None
    ) -> None:
        """Print extraction summary."""
        print(f"\nSaved: {output_path}")
        print(f"Size: {len(full_audio) / 1024:.1f} KB")
        print(f"Duration: {metadata['durationMs'] / 1000:.1f}s")

        if verify_data:
            print("\n--- VERIFICATION DATA ---")
            print(json.dumps(verify_data, indent=2))


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract audio content from HotAudio URLs"
    )
    parser.add_argument("url", nargs="?", help="HotAudio URL to extract")
    parser.add_argument(
        "output_name",
        nargs="?",
        help="Output filename (without extension)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./data/hotaudio",
        help="Output directory (default: ./data/hotaudio)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Output detailed verification JSON with checksums",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract ALL tracks from CYOA pages (multi-track support)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Only discover tracks on the page without extracting",
    )

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        print("\nExamples:")
        print(
            "  uv run python hotaudio_extractor.py https://hotaudio.net/u/User/Audio-Title"
        )
        print(
            "  uv run python hotaudio_extractor.py https://hotaudio.net/u/User/CYOA-Audio --all"
        )
        print(
            "  uv run python hotaudio_extractor.py https://hotaudio.net/u/User/Audio --discover"
        )
        return 1

    # Load environment variables
    load_dotenv()

    extractor = HotAudioExtractor()

    # Discovery mode - just list tracks
    if args.discover:
        try:
            tracks = extractor.discover_tracks(args.url)
            print(f"\nDiscovered {len(tracks)} tracks on page:\n")
            for t in tracks:
                print(f"  [{t['index']}] tid={t['tid']}")
                print(f"      Title: {t['title']}")
                print(f"      Tag: {t['tag']}")
                print()
            if len(tracks) > 1:
                print("This is a CYOA page. Use --all to extract all tracks.")
            return 0
        except Exception as e:
            print(f"\n  Error: {e}")
            return 1

    # Extract basename from URL if not provided
    basename = args.output_name
    if not basename:
        url_parts = args.url.rstrip("/").split("/")
        basename = url_parts[-1] or "audio"

    target_path = {
        "dir": args.output_dir,
        "basename": basename,
    }

    # For old-style options compatibility
    if args.verify:
        target_path = {
            "outputDir": args.output_dir,
            "outputName": basename,
            "verify": True,
        }

    try:
        if args.all:
            # Multi-track extraction for CYOA pages
            result = extractor.extract_all(args.url, target_path)
            print("\n  Multi-track extraction complete!")
            print(f"  Total tracks: {result.get('trackCount', 0)}")
            print(f"  Extracted: {result.get('extractedCount', 0)}")
            if result.get("tracks"):
                for t in result["tracks"]:
                    if "error" not in t:
                        print(f"    - {t.get('audio', {}).get('filePath', 'unknown')}")
        else:
            # Single track extraction
            result = extractor.extract(args.url, target_path)
            print("\n  Extraction complete!")
            print(f"  Audio: {result['audio']['filePath']}")
            print(f"  Metadata: {result['backupFiles']['metadata']}")
        return 0
    except Exception as e:
        print(f"\n  Error: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
